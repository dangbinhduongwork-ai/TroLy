"""Vòng lặp Agent điều phối thực thi công cụ an toàn (Agent Loop).

Quy trình:
1. Gửi ngữ cảnh và danh sách schema công cụ cho Model.
2. Nhận phản hồi: nếu là text thì stream cho người dùng; nếu là tool_call thì xử lý.
3. Kiểm tra phân quyền an toàn qua safety/permissions.py:
   - ALLOW: Tự động chạy.
   - NEEDS_APPROVAL: In rõ hành động, tham số và yêu cầu người dùng duyệt (y/N) trong terminal.
   - DENY: Từ chối cứng các lệnh nguy hiểm.
4. Bọc dữ liệu đọc từ bên ngoài trong <untrusted_content> qua safety/injection.py.
5. Ghi nhật ký kiểm toán JSONL qua safety/audit.py.
6. Trả kết quả công cụ cho Model và tiếp tục vòng lặp cho đến khi Model trả lời bằng văn bản.
7. Giới hạn an toàn: tối đa 10 bước/lượt, phát hiện lặp lại (>=3 lần cùng công cụ + tham số), hỗ trợ huỷ.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
import json
from typing import Any

from assistant.core.context import ConversationContext
from assistant.core.router import ModelRouter
from assistant.llm.base import Message, StreamEvent, ToolCall
from assistant.safety.audit import AuditLogger
from assistant.safety.injection import TurnSecurityTracker, wrap_untrusted_content
from assistant.safety.paths import resolve_in_workspace
from assistant.safety.permissions import (
    PermissionDecision,
    PermissionLevel,
    evaluate_permission,
)
from assistant.tools.registry import ToolRegistry, default_tool_registry


def ask_terminal_approval(tool_name: str, args: dict[str, Any], reason: str) -> bool:
    """Hỏi phê duyệt từ người dùng trực tiếp trên giao diện dòng lệnh (terminal)."""
    print("\n" + "=" * 65)
    print(f"⚠️  [YÊU CẦU PHÊ DUYỆT TÁC VỤ: {tool_name}]")
    print(f"Lý do cần duyệt : {reason}")
    print(f"Tham số thực thi: {json.dumps(args, ensure_ascii=False, indent=2)}")
    print("=" * 65)

    try:
        choice = input("Bạn có đồng ý cho Trợ lý thực hiện tác vụ này không? (y/N): ").strip().lower()
        return choice in ("y", "yes", "co", "dong y", "ok")
    except (KeyboardInterrupt, EOFError):
        print("\n[Đã từ chối theo yêu cầu]")
        return False


class AgentLoop:
    """Bộ điều phối vòng lặp gọi công cụ của Agent."""

    def __init__(
        self,
        router: ModelRouter,
        registry: ToolRegistry | None = None,
        audit_logger: AuditLogger | None = None,
        approval_callback: Callable[[str, dict[str, Any], str], bool] | None = None,
        max_steps: int = 10,
        total_timeout: float = 120.0,
    ) -> None:
        self.router = router
        self.registry = registry or default_tool_registry
        self.audit_logger = audit_logger or AuditLogger()
        self.approval_callback = approval_callback or ask_terminal_approval
        self.security_tracker = TurnSecurityTracker()
        self.max_steps = max_steps
        self.total_timeout = total_timeout

    async def run_turn(
        self,
        context: ConversationContext,
        system_prompt: str,
        is_sensitive: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Thực thi một lượt trao đổi gồm nhiều bước gọi công cụ."""
        self.security_tracker.reset()
        tool_call_history: list[tuple[str, str]] = []

        for step in range(self.max_steps):
            step_text_chunks: list[str] = []
            step_tool_calls: list[ToolCall] = []

            # 1. Gửi ngữ cảnh và danh sách công cụ tới model
            tool_schemas = self.registry.get_schemas()
            messages_to_send = context.get_messages_for_llm()

            async for event in self.router.stream_chat(
                messages=messages_to_send,
                tools=tool_schemas,
                system=system_prompt,
                is_sensitive=is_sensitive,
            ):
                if event.type == "text_delta":
                    if isinstance(event.content, str):
                        step_text_chunks.append(event.content)
                    yield event
                elif event.type == "tool_call":
                    if isinstance(event.content, ToolCall):
                        step_tool_calls.append(event.content)
                elif event.type == "usage":
                    yield event

            # 2. Nếu model không gọi công cụ nào -> đã hoàn thành lượt trả lời
            if not step_tool_calls:
                full_text = "".join(step_text_chunks)
                if full_text.strip():
                    context.add_assistant_message(full_text)
                return

            # 3. Model yêu cầu gọi một hoặc nhiều công cụ
            # Lưu tin nhắn của assistant chứa các tool_calls vào ngữ cảnh
            context.add_message(
                Message(
                    role="assistant",
                    content="".join(step_text_chunks) or None,
                    tool_calls=step_tool_calls,
                )
            )

            for tc in step_tool_calls:
                # a) Kiểm tra chống lặp vô tận (cùng công cụ + cùng tham số >= 3 lần)
                sig = (tc.name, json.dumps(tc.arguments, sort_keys=True, ensure_ascii=False))
                prior_count = sum(1 for s in tool_call_history if s == sig)
                if prior_count >= 2:
                    loop_err = (
                        f"Phát hiện vòng lặp vô tận: công cụ '{tc.name}' được gọi với cùng tham số từ 3 lần. "
                        "Hệ thống đã dừng vòng lặp để đảm bảo an toàn."
                    )
                    yield StreamEvent(type="text_delta", content=f"\n[DỪNG AN TOÀN] {loop_err}\n")
                    context.add_message(
                        Message(role="tool", content=f"[LỖI AN TOÀN] {loop_err}", tool_call_id=tc.id)
                    )
                    return

                tool_call_history.append(sig)

                # b) Kiểm tra công cụ trong registry
                tool_def = self.registry.get(tc.name)
                if not tool_def:
                    err_msg = f"Không tìm thấy công cụ mang tên '{tc.name}' trong hệ thống."
                    yield StreamEvent(type="text_delta", content=f"\n[LỖI] {err_msg}\n")
                    context.add_message(
                        Message(role="tool", content=f"[LỖI] {err_msg}", tool_call_id=tc.id)
                    )
                    continue

                # c) Đánh giá phân quyền
                def _file_exists(p: str) -> bool:
                    try:
                        return resolve_in_workspace(p).exists()
                    except Exception:
                        return False

                decision, reason = evaluate_permission(
                    tool_name=tc.name,
                    declared_level=tool_def.permission_level,
                    args=tc.arguments,
                    file_exists_callback=_file_exists,
                )

                # Siết chặt an toàn nếu lượt này đã đọc dữ liệu không tin cậy
                if self.security_tracker.is_tainted() and decision == PermissionDecision.ALLOW:
                    if tool_def.permission_level != PermissionLevel.READ:
                        decision = PermissionDecision.NEEDS_APPROVAL
                        reason += " (Bắt buộc duyệt do lượt này đã đọc nội dung từ bên ngoài)"

                # d) Xử lý theo quyết định phân quyền
                if decision == PermissionDecision.DENY:
                    deny_summary = f"[BỊ TỪ CHỐI CỨNG] {reason}"
                    self.audit_logger.log_call(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        decision="DENY",
                        result_summary=deny_summary,
                        is_error=True,
                    )
                    yield StreamEvent(type="text_delta", content=f"\n[TỪ CHỐI CỨNG] {reason}\n")
                    context.add_message(
                        Message(role="tool", content=deny_summary, tool_call_id=tc.id)
                    )
                    continue

                decision_log = "ALLOW"
                if decision == PermissionDecision.NEEDS_APPROVAL:
                    # Chờ phê duyệt từ người dùng
                    approved = self.approval_callback(tc.name, tc.arguments, reason)
                    if not approved:
                        reject_summary = "[NGƯỜI DÙNG TỪ CHỐI DUYỆT TÁC VỤ]"
                        self.audit_logger.log_call(
                            tool_name=tc.name,
                            arguments=tc.arguments,
                            decision="REJECTED",
                            result_summary=reject_summary,
                            is_error=True,
                        )
                        yield StreamEvent(
                            type="text_delta",
                            content=f"\n[Hệ thống] Bạn đã từ chối thực hiện công cụ '{tc.name}'.\n",
                        )
                        context.add_message(
                            Message(role="tool", content=reject_summary, tool_call_id=tc.id)
                        )
                        continue
                    decision_log = "APPROVED"

                # e) Thực thi công cụ
                yield StreamEvent(type="text_delta", content=f"\n[Đang chạy: {tc.name}...] ")
                execution_res = tool_def.execute(**tc.arguments)

                is_ok = execution_res.get("ok", False)
                raw_data = execution_res.get("data") if is_ok else execution_res.get("error")

                # f) Xử lý dữ liệu không tin cậy nếu có
                if tool_def.is_external_content:
                    self.security_tracker.mark_external_content_read()
                    tool_content = wrap_untrusted_content(raw_data, source_label=tc.name)
                else:
                    tool_content = str(raw_data)

                # g) Ghi nhật ký kiểm toán
                self.audit_logger.log_call(
                    tool_name=tc.name,
                    arguments=tc.arguments,
                    decision=decision_log,
                    result_summary=raw_data,
                    is_error=not is_ok,
                )

                yield StreamEvent(type="text_delta", content="Xong.\n")

                # h) Lưu kết quả vào ngữ cảnh để gửi lại cho Model
                context.add_message(
                    Message(role="tool", content=tool_content, tool_call_id=tc.id)
                )

        yield StreamEvent(
            type="text_delta",
            content="\n[CẢNH BÁO] Đã đạt giới hạn tối đa 10 bước công cụ trong một lượt.\n",
        )
