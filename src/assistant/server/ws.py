"""Bộ xử lý WebSocket thời gian thực cho tính năng Chat (WebSocket Handler).

Tuân thủ:
- Xác thực Session Token khi bắt tay kết nối (Handshake).
- Truyền sự kiện (stream) thời gian thực: text_delta, tool_start, approval_required,
  tool_result, model_switched, turn_done, error.
- Quản lý luồng duyệt quyền bất đồng bộ (Asynchronous Approval Flow) với timeout 120s.
- Hỗ trợ nút ngắt câu trả lời (Cancel).
- Lưu vết toàn bộ hội thoại vào SQLite và kích hoạt trích xuất trí nhớ dài hạn.
"""

import asyncio
import json
import logging
from typing import Any, Callable
import uuid


from fastapi import WebSocket, WebSocketDisconnect

from assistant.agents.orchestrator import set_orchestrator_approval_callback
from assistant.config import Config, load_config
from assistant.core.agent_loop import AgentLoop
from assistant.core.context import ConversationContext
from assistant.core.prompts import get_system_prompt
from assistant.core.router import ModelRouter
from assistant.llm.base import Message
from assistant.memory.extractor import extract_and_save_memories
from assistant.memory.store import MemoryStore
from assistant.tools.registry import default_tool_registry


logger = logging.getLogger("assistant.server.ws")

_global_ws_manager: Any = None


def notify_focus_input() -> None:
    """Gọi từ luồng bất kỳ để thông báo cho Web UI đặt con trỏ vào ô nhập chat."""
    global _global_ws_manager
    if _global_ws_manager and getattr(_global_ws_manager, "active_websockets", None):
        try:
            # Tìm loop hiện tại hoặc chạy coroutine threadsafe
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_global_ws_manager.broadcast_focus_input(), loop)
        except Exception as exc:
            logger.debug("Không thể phát sự kiện focus_input: %s", exc)


class ChatWebSocketManager:
    """Quản lý các kết nối WebSocket và điều phối hội thoại tương tác."""

    def __init__(
        self,
        router: ModelRouter,
        memory_store: MemoryStore,
        token_verifier: Callable[[str], bool],
        config: Config | None = None,
    ) -> None:
        self.router = router
        self.memory_store = memory_store
        self.verify_token = token_verifier
        self.config = config or load_config(create_dirs=False)
        # Bản đồ lưu các yêu cầu duyệt quyền đang chờ: request_id -> asyncio.Future[bool]
        self.pending_approvals: dict[str, asyncio.Future[bool]] = {}
        # Task đang chạy của mỗi kết nối WebSocket
        self.active_tasks: dict[WebSocket, asyncio.Task[Any]] = {}
        # Danh sách kết nối WebSocket đang hoạt động
        self.active_websockets: set[WebSocket] = set()

        global _global_ws_manager
        _global_ws_manager = self

    async def broadcast_focus_input(self) -> None:
        """Gửi sự kiện yêu cầu giao diện Web đặt con trỏ vào ô nhập chat (Spotlight Mode)."""
        dead: list[WebSocket] = []
        for ws in list(self.active_websockets):
            try:
                await self._send_event(ws, "focus_input", {})
            except Exception:
                dead.append(ws)
        for d in dead:
            self.active_websockets.discard(d)

    async def handle_connection(self, websocket: WebSocket) -> None:
        """Xử lý vòng đời của một kết nối WebSocket."""
        # 1. Xác thực Session Token từ query param hoặc header
        token = websocket.query_params.get("token") or websocket.headers.get("x-session-token", "")
        if not self.verify_token(token):
            logger.warning("Từ chối kết nối WebSocket do Session Token không hợp lệ.")
            await websocket.close(code=1008, reason="Forbidden: Invalid Session Token")
            return

        await websocket.accept()
        self.active_websockets.add(websocket)
        logger.info("Client đã kết nối thành công tới WebSocket /ws/chat")

        try:
            while True:
                raw_text = await websocket.receive_text()
                try:
                    payload = json.loads(raw_text)
                except Exception:
                    await self._send_event(websocket, "error", {"error": "Dữ liệu JSON không hợp lệ."})
                    continue

                msg_type = payload.get("type")

                # a) Người dùng phản hồi phê duyệt (approve / deny)
                if msg_type == "approval_response":
                    req_id = payload.get("request_id")
                    approved = bool(payload.get("approved", False))
                    if req_id and req_id in self.pending_approvals:
                        fut = self.pending_approvals[req_id]
                        if not fut.done():
                            fut.set_result(approved)
                    continue

                # b) Người dùng bấm nút Huỷ / Dừng lại (Cancel)
                if msg_type == "cancel":
                    if websocket in self.active_tasks:
                        task = self.active_tasks[websocket]
                        if not task.done():
                            task.cancel()
                            await self._send_event(
                                websocket,
                                "text_delta",
                                {"content": "\n\n[Đã dừng câu trả lời theo yêu cầu người dùng]"},
                            )
                    await self._send_event(
                        websocket,
                        "turn_done",
                        {"tools_called": [], "cancelled": True},
                    )
                    continue

                # c) Người dùng gửi tin nhắn trò chuyện mới
                if msg_type == "user_message":
                    user_text = payload.get("message", "").strip()
                    if not user_text:
                        continue

                    conv_id = payload.get("conversation_id")
                    mode = payload.get("mode", "auto")
                    is_sensitive = bool(payload.get("is_sensitive", False))
                    user_name = payload.get("user_name")
                    assistant_name = payload.get("assistant_name")

                    # Nếu đang có lượt cũ chạy trên websocket này, huỷ trước khi chạy mới
                    if websocket in self.active_tasks and not self.active_tasks[websocket].done():
                        self.active_tasks[websocket].cancel()

                    task = asyncio.create_task(
                        self._process_user_turn(
                            websocket=websocket,
                            user_text=user_text,
                            conv_id=conv_id,
                            mode=mode,
                            is_sensitive=is_sensitive,
                            user_name=user_name,
                            assistant_name=assistant_name,
                        )
                    )

                    def _on_task_finished(t: asyncio.Task) -> None:
                        try:
                            t.result()
                        except asyncio.CancelledError:
                            pass
                        except Exception as exc:
                            logger.error("Lỗi tác vụ chat ngầm: %s", exc)

                    task.add_done_callback(_on_task_finished)
                    self.active_tasks[websocket] = task

        except WebSocketDisconnect:
            logger.info("Client đã ngắt kết nối WebSocket.")
        except Exception as err:
            logger.error("Lỗi phiên WebSocket: %s", err)
        finally:
            self.active_websockets.discard(websocket)
            if websocket in self.active_tasks:
                task = self.active_tasks.pop(websocket)
                if not task.done():
                    task.cancel()
            # Giải phóng tất cả approvals đang chờ
            for fut in self.pending_approvals.values():
                if not fut.done():
                    fut.set_result(False)
            self.pending_approvals.clear()

    async def _send_event(self, websocket: WebSocket, event_type: str, data: dict[str, Any]) -> None:
        """Gửi gói tin sự kiện có cấu trúc xuống client."""
        try:
            msg = {"type": event_type, "data": data}
            await websocket.send_text(json.dumps(msg, ensure_ascii=False))
        except Exception as err:
            logger.debug("Không thể gửi sự kiện WebSocket: %s", err)

    async def _process_user_turn(
        self,
        websocket: WebSocket,
        user_text: str,
        conv_id: str | None,
        mode: str,
        is_sensitive: bool,
        user_name: str | None = None,
        assistant_name: str | None = None,
    ) -> None:
        """Xử lý một lượt hội thoại từ lúc nhận tin nhắn đến lúc hoàn tất."""
        # Phản hồi trạng thái tức thời cho client để hiển thị con trỏ kết nối
        await self._send_event(websocket, "text_delta", {"content": "..."})

        # 1. Đảm bảo có conversation_id hợp lệ
        if not conv_id:
            # Tạo cuộc hội thoại mới lấy 30 ký tự đầu làm tiêu đề
            title = user_text[:30] + ("..." if len(user_text) > 30 else "")
            conv_id = self.memory_store.create_conversation(title=title, is_sensitive=is_sensitive)
        else:
            # Kiểm tra cuộc hội thoại có tồn tại không
            conv = self.memory_store.get_conversation(conv_id)
            if not conv:
                conv_id = self.memory_store.create_conversation(title=user_text[:30], is_sensitive=is_sensitive)

        # 2. Lưu tin nhắn của người dùng vào SQLite
        self.memory_store.add_message(
            conversation_id=conv_id,
            role="user",
            content=user_text,
        )

        # 3. Nạp lịch sử hội thoại vào ConversationContext
        context = ConversationContext(max_tokens=3500)
        recent_messages = self.memory_store.get_messages(conv_id, limit=20)
        for m in recent_messages:
            context.add_message(Message(role=m.get("role", "user"), content=m.get("content") or ""))

        # 4. Thiết lập chế độ router tạm thời nếu được yêu cầu
        orig_mode = self.router.mode
        if mode in ("auto", "gemini", "local"):
            self.router.set_mode(mode)  # type: ignore

        # 5. Định nghĩa callback duyệt quyền bất đồng bộ qua WebSocket
        async def _websocket_approval(tool_name: str, args: dict[str, Any], reason: str) -> bool:
            req_id = str(uuid.uuid4())
            loop = asyncio.get_running_loop()
            future: asyncio.Future[bool] = loop.create_future()
            self.pending_approvals[req_id] = future

            is_dangerous = (
                tool_name in ("run_command", "delete_path")
                or "xoá" in reason.lower()
                or "lệnh" in reason.lower()
            )

            # Gửi yêu cầu xác nhận xuống giao diện
            await self._send_event(
                websocket,
                "approval_required",
                {
                    "request_id": req_id,
                    "tool_name": tool_name,
                    "arguments": args,
                    "reason": reason,
                    "is_dangerous": is_dangerous,
                },
            )

            try:
                # Chờ người dùng bấm duyệt trên giao diện trong tối đa 120 giây
                return await asyncio.wait_for(future, timeout=120.0)
            except asyncio.TimeoutError:
                logger.warning("Hết thời gian chờ duyệt quyền (120s). Tự động từ chối.")
                await self._send_event(
                    websocket,
                    "text_delta",
                    {"content": f"\n[Hết thời gian chờ duyệt tác vụ '{tool_name}' - Tự động từ chối]\n"},
                )
                return False
            finally:
                self.pending_approvals.pop(req_id, None)

        # Đăng ký callback duyệt quyền cho Orchestrator subagents trong lượt này
        set_orchestrator_approval_callback(_websocket_approval)

        # 6. Định nghĩa bộ lắng nghe sự kiện để truyền xuống WebSocket
        tools_called_in_turn: list[str] = []

        async def _on_event(event_name: str, payload: dict[str, Any]) -> None:
            if event_name == "tool_start":
                tname = payload.get("tool_name")
                if tname and tname not in tools_called_in_turn:
                    tools_called_in_turn.append(str(tname))
            elif event_name == "turn_done":
                for t in payload.get("tools_called", []):
                    if t and t not in tools_called_in_turn:
                        tools_called_in_turn.append(str(t))
            await self._send_event(websocket, event_name, payload)

        # 7. Lấy danh sách trí nhớ liên quan và khởi tạo System Prompt
        active_memories = await asyncio.to_thread(
            context.get_relevant_memories,
            self.memory_store,
            max_tokens=600,
            max_memories=15,
            query=user_text,
        )
        system_prompt = get_system_prompt(
            timezone_str=self.config.timezone,
            memories=active_memories,
            user_name=user_name,
            assistant_name=assistant_name,
        )
        agent_loop = AgentLoop(
            router=self.router,
            registry=default_tool_registry,
            approval_callback=_websocket_approval,
            max_steps=8,
        )

        accumulated_text: list[str] = []

        try:
            async for ev in agent_loop.run_turn(
                context=context,
                system_prompt=system_prompt,
                is_sensitive=is_sensitive,
                on_event=_on_event,
            ):
                if ev.type == "text_delta" and isinstance(ev.content, str):
                    accumulated_text.append(ev.content)
                elif ev.type == "usage":
                    pass

            full_response = "".join(accumulated_text).strip()
            model_used_name = getattr(self.router, "last_model_used", None) or self.router.mode

            # 8. Lưu câu trả lời của trợ lý vào SQLite
            if full_response:
                self.memory_store.add_message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_response,
                    model_used=str(model_used_name),
                )

            # 9. Gửi sự kiện turn_done thông báo kết thúc lượt
            await self._send_event(
                websocket,
                "turn_done",
                {
                    "conversation_id": conv_id,
                    "model_used": str(model_used_name),
                    "tools_called": tools_called_in_turn,
                },
            )

            # 10. Trích xuất trí nhớ dài hạn chạy ngầm nếu có dữ kiện mới
            if not is_sensitive and full_response:
                asyncio.create_task(
                    extract_and_save_memories(
                        user_message=user_text,
                        assistant_message=full_response,
                        conv_id=conv_id,
                        router=self.router,
                        memory_store=self.memory_store,
                        is_sensitive=is_sensitive,
                    )
                )

        except asyncio.CancelledError:
            logger.info("Lượt xử lý câu hỏi đã bị người dùng huỷ.")
            await self._send_event(websocket, "turn_done", {"conversation_id": conv_id or ""})
        except Exception as err:
            logger.error("Lỗi trong quá trình xử lý lượt chat: %s", err)
            await self._send_event(websocket, "error", {"error": f"Lỗi xử lý: {err}"})
            await self._send_event(websocket, "turn_done", {"conversation_id": conv_id or ""})
        finally:
            set_orchestrator_approval_callback(None)
            # Khôi phục lại chế độ router ban đầu
            self.router.set_mode(orig_mode)
