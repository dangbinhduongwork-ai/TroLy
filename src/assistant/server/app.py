"""Ứng dụng máy chủ FastAPI và hệ thống REST API cho Trợ Lý AI (Server Application).

Nguyên tắc an toàn & bảo mật:
- Chỉ lắng nghe trên 127.0.0.1 (localhost).
- Tạo Session Token ngẫu nhiên (secrets.token_urlsafe) khi khởi động để ngăn chặn các website
  bên ngoài trình duyệt gọi lậu vào API nội bộ (Chống CSRF / SSRF cục bộ).
- Xác thực Session Token trên mọi endpoint /api/* và kết nối WebSocket /ws/chat.
- Phục vụ giao diện tĩnh (HTML/CSS/JS) chạy hoàn toàn ngoại tuyến không cần mạng internet.
"""

from contextlib import asynccontextmanager
import json
from pathlib import Path
import re
import secrets
import sys
from typing import Any


from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from fastapi.staticfiles import StaticFiles

from assistant.config import Config, load_config
from assistant.core.router import ModelRouter
from assistant.memory.store import MemoryStore
from assistant.reminders.scheduler import ReminderScheduler
from assistant.reminders.store import ReminderStore
from assistant.server.schemas import (
    AutostartUpdateRequest,
    ConversationCreate,
    ConversationItem,
    ConversationUpdate,
    DiagnosticsResponse,
    FileUploadResponse,
    GeminiKeyCreateRequest,
    GeminiKeyItem,
    GeminiKeysResponse,
    GeminiKeyTestRequest,
    GeminiKeyUpdateRequest,
    HotkeyUpdateRequest,
    KeyUpdateRequest,
    MemoryCreate,
    MemoryItem,
    MemoryUpdate,
    MessageItem,
    ModelModeUpdateRequest,
    ReminderCreate,
    ReminderItem,
    ReminderSnooze,
    StatusResponse,
)
from assistant.logging_setup import SecretFilter
from assistant.server.ws import ChatWebSocketManager

def _load_or_create_session_token() -> str:
    """Nạp session token từ file dữ liệu bảo mật hoặc sinh mới nếu chưa có."""
    from assistant.config import _get_default_data_dir

    data_dir = _get_default_data_dir()
    token_file = data_dir / "session.token"
    try:
        if token_file.is_file():
            stored = token_file.read_text(encoding="utf-8").strip()
            if len(stored) >= 32:
                return stored
    except Exception:
        pass

    new_token = secrets.token_urlsafe(32)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        token_file.write_text(new_token, encoding="utf-8")
    except Exception:
        pass
    return new_token


_session_token: str = _load_or_create_session_token()
SecretFilter.register_secret(_session_token)


def get_current_session_token() -> str:
    """Lấy Session Token hiện hành của phiên làm việc."""
    global _session_token
    return _session_token


def set_current_session_token(token: str) -> None:
    """Thiết lập Session Token mới (dùng cho khởi động hoặc kiểm thử)."""
    global _session_token
    _session_token = token
    SecretFilter.register_secret(token)
    try:
        from assistant.config import _get_default_data_dir

        data_dir = _get_default_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "session.token").write_text(token, encoding="utf-8")
    except Exception:
        pass



def verify_session_token(token: str) -> bool:
    """Kiểm tra Session Token có khớp với phiên đang chạy không."""
    if not token:
        return False
    return secrets.compare_digest(token, get_current_session_token())


# Định nghĩa cơ chế xác thực qua Header hoặc Query Parameter
token_header = APIKeyHeader(name="X-Session-Token", auto_error=False)
token_query = APIKeyQuery(name="token", auto_error=False)


def require_session_token(
    header_val: str | None = Security(token_header),
    query_val: str | None = Security(token_query),
) -> str:
    """Dependency bắt buộc Session Token hợp lệ trên tất cả các REST API."""
    token = header_val or query_val
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu Session Token xác thực.",
        )
    if not verify_session_token(token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session Token không hợp lệ hoặc đã hết hạn.",
        )
    return token


def create_app(
    config: Config | None = None,
    router: ModelRouter | None = None,
    memory_store: MemoryStore | None = None,
    reminder_store: ReminderStore | None = None,
    scheduler: ReminderScheduler | None = None,
    session_token: str | None = None,
) -> FastAPI:
    """Khởi tạo và cấu hình ứng dụng FastAPI."""
    if session_token:
        set_current_session_token(session_token)

    app_config = config or load_config(create_dirs=True)
    app_router = router or ModelRouter()
    app_mem_store = memory_store or MemoryStore()
    app_rem_store = reminder_store or ReminderStore()
    app_scheduler = scheduler or ReminderScheduler(config=app_config, store=app_rem_store)


    ws_manager = ChatWebSocketManager(
        router=app_router,
        memory_store=app_mem_store,
        token_verifier=verify_session_token,
        config=app_config,
    )


    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Khởi động bộ lập lịch nhắc việc
        try:
            app_scheduler.start()
        except Exception:
            pass
        yield
        # Tắt bộ lập lịch khi shutdown
        try:
            app_scheduler.shutdown()
        except Exception:
            pass

    app = FastAPI(
        title="Trợ Lý AI - Windows Desktop Server",
        description="Backend API và WebSocket cục bộ cho Trợ Lý AI trên Windows",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Chỉ cho phép CORS từ localhost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1", "http://localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Lưu trữ các tham chiếu dùng chung
    app.state.config = app_config
    app.state.router = app_router
    app.state.mem_store = app_mem_store
    app.state.rem_store = app_rem_store
    app.state.scheduler = app_scheduler

    # =========================================================================
    # REST API: TRẠNG THÁI HỆ THỐNG
    # =========================================================================

    @app.get("/api/status", response_model=StatusResponse, dependencies=[Depends(require_session_token)])
    async def get_status() -> dict[str, Any]:
        """Lấy thông tin trạng thái kết nối và tài nguyên hệ thống."""
        # Kiểm tra nhanh Gemini API key
        gemini_configured = False
        try:
            from assistant.llm.gemini_provider import get_gemini_api_key
            gemini_configured = bool(get_gemini_api_key())
        except Exception:
            pass

        # Kiểm tra mạng tới Gemini
        gemini_reachable = False
        if gemini_configured:
            gemini_reachable = app_router.is_network_available()

        # Kiểm tra Ollama cục bộ
        ollama_running = False
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            # Ollama mặc định cổng 11434
            res = sock.connect_ex(("127.0.0.1", 11434))
            ollama_running = (res == 0)
            sock.close()
        except Exception:
            pass

        current_model_name = getattr(app_router, "last_model_used", None) or (
            app_config.gemini_model if app_router.mode == "gemini" else app_config.local_model
        )

        daily_count = app_router.usage_tracker.get_count() if hasattr(app_router, "usage_tracker") else 0

        return {
            "gemini_configured": gemini_configured,
            "gemini_reachable": gemini_reachable,
            "ollama_running": ollama_running,
            "current_model": current_model_name,
            "gemini_model": app_config.gemini_model,
            "local_model": app_config.local_model,
            "daily_requests_count": daily_count,
            "daily_soft_limit": app_config.daily_soft_limit,
            "workspace_dir": str(app_config.workspace_dir),
            "scheduler_running": bool(getattr(app_scheduler, "is_running", False)),
        }

    # =========================================================================
    # REST API: HỘI THOẠI (CONVERSATIONS)
    # =========================================================================

    @app.get("/api/conversations", response_model=list[ConversationItem], dependencies=[Depends(require_session_token)])
    async def list_conversations() -> list[dict[str, Any]]:
        """Lấy danh sách các cuộc trò chuyện."""
        convs = app_mem_store.list_conversations(limit=50)
        results: list[dict[str, Any]] = []
        for c in convs:
            # Lấy tin nhắn gần nhất
            msgs = app_mem_store.get_messages(c["id"], limit=1)
            last_msg = msgs[-1]["content"] if msgs else None
            results.append({
                "id": c["id"],
                "title": c["title"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                "is_sensitive": bool(c["is_sensitive"]),
                "last_message": last_msg,
            })
        return results

    @app.post("/api/conversations", response_model=ConversationItem, dependencies=[Depends(require_session_token)])
    async def create_conversation(req: ConversationCreate) -> dict[str, Any]:
        """Tạo một cuộc hội thoại mới."""
        cid = app_mem_store.create_conversation(title=req.title, is_sensitive=req.is_sensitive)
        c = app_mem_store.get_conversation(cid)
        if not c:
            raise HTTPException(status_code=500, detail="Không thể tạo cuộc trò chuyện.")
        return {
            "id": c["id"],
            "title": c["title"],
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
            "is_sensitive": bool(c["is_sensitive"]),
            "last_message": None,
        }

    @app.get("/api/conversations/{conv_id}/messages", response_model=list[MessageItem], dependencies=[Depends(require_session_token)])
    async def get_messages(conv_id: str) -> list[dict[str, Any]]:
        """Lấy toàn bộ tin nhắn của một cuộc hội thoại."""
        conv = app_mem_store.get_conversation(conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy cuộc trò chuyện {conv_id}.")
        return app_mem_store.get_messages(conv_id, limit=100)

    @app.delete("/api/conversations/{conv_id}", dependencies=[Depends(require_session_token)])
    async def delete_conversation(conv_id: str) -> dict[str, Any]:
        """Xoá một cuộc hội thoại."""
        ok = app_mem_store.delete_conversation(conv_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện để xoá.")
        return {"ok": True, "message": "Đã xoá cuộc trò chuyện thành công."}

    # =========================================================================
    # REST API: TRÍ NHỚ DÀI HẠN (MEMORIES)
    # =========================================================================

    @app.get("/api/memories", response_model=list[MemoryItem], dependencies=[Depends(require_session_token)])
    async def list_memories(
        category: str | None = Query(None),
        query: str | None = Query(None),
    ) -> list[dict[str, Any]]:
        """Lấy danh sách hoặc tìm kiếm trí nhớ dài hạn."""
        if query and query.strip():
            return app_mem_store.search_memories_hybrid(query.strip(), top_k=50)
        return app_mem_store.list_memories(category=category, limit=100)

    @app.post("/api/memories", response_model=dict[str, Any], dependencies=[Depends(require_session_token)])
    async def add_memory(req: MemoryCreate) -> dict[str, Any]:
        """Lưu một dữ kiện mới vào trí nhớ dài hạn."""
        mem_id = app_mem_store.add_memory(category=req.category, content=req.content)
        return {"ok": True, "id": mem_id}

    @app.put("/api/memories/{mem_id}", dependencies=[Depends(require_session_token)])
    async def update_memory(mem_id: str, req: MemoryUpdate) -> dict[str, Any]:
        """Chỉnh sửa nội dung hoặc danh mục của trí nhớ."""
        ok = app_mem_store.update_memory(
            memory_id=mem_id,
            content=req.content,
            category=req.category,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Không tìm thấy mục trí nhớ để sửa.")
        return {"ok": True, "message": "Đã cập nhật trí nhớ thành công."}

    @app.delete("/api/memories/{mem_id}", dependencies=[Depends(require_session_token)])
    async def delete_memory(mem_id: str) -> dict[str, Any]:
        """Xoá một mục trí nhớ."""
        ok = app_mem_store.delete_memory(mem_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Không tìm thấy mục trí nhớ để xoá.")
        return {"ok": True, "message": "Đã xoá mục trí nhớ thành công."}

    # =========================================================================
    # REST API: LỜI NHẮC VIỆC (REMINDERS)
    # =========================================================================

    @app.get("/api/reminders", response_model=list[ReminderItem], dependencies=[Depends(require_session_token)])
    async def list_reminders(status_filter: str | None = Query(None)) -> list[dict[str, Any]]:
        """Liệt kê danh sách các lời nhắc việc."""
        return app_rem_store.list_reminders(status=status_filter, limit=100)

    @app.post("/api/reminders", response_model=dict[str, Any], dependencies=[Depends(require_session_token)])
    async def create_reminder(req: ReminderCreate) -> dict[str, Any]:
        """Tạo một lời nhắc việc mới và đưa vào bộ lập lịch."""
        rem_id = app_rem_store.add_reminder(
            message=req.message,
            trigger_at=req.trigger_at,
            cron_expr=req.cron_expr,
        )
        rem = app_rem_store.get_reminder(rem_id)
        if rem and app_scheduler.is_running:
            app_scheduler.schedule_reminder(rem)
        return {"ok": True, "id": rem_id}

    @app.post("/api/reminders/{rem_id}/snooze", dependencies=[Depends(require_session_token)])
    async def snooze_reminder(rem_id: str, req: ReminderSnooze) -> dict[str, Any]:
        """Hoãn nhắc việc thêm N phút."""
        res = app_rem_store.snooze_reminder(rem_id, minutes=req.minutes)
        if not res:
            raise HTTPException(status_code=404, detail="Không tìm thấy lời nhắc để hoãn.")
        if app_scheduler.is_running:
            app_scheduler.schedule_reminder(res)
        return {"ok": True, "reminder": res}

    @app.delete("/api/reminders/{rem_id}", dependencies=[Depends(require_session_token)])
    async def cancel_reminder(rem_id: str) -> dict[str, Any]:
        """Huỷ bỏ hoặc xoá một lời nhắc việc."""
        ok = app_rem_store.delete_reminder(rem_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Không tìm thấy lời nhắc để huỷ.")
        return {"ok": True, "message": "Đã huỷ lời nhắc việc thành công."}

    # =========================================================================
    # REST API: CÀI ĐẶT & CHẨN ĐOÁN (SETTINGS & DIAGNOSTICS)
    # =========================================================================

    @app.get("/api/settings/diagnostics", response_model=DiagnosticsResponse, dependencies=[Depends(require_session_token)])
    async def get_diagnostics() -> dict[str, Any]:
        """Chẩn đoán toàn diện hệ thống: Gemini, Ollama, Autostart, Workspace."""
        from assistant.desktop.autostart import is_autostart_enabled
        from assistant.llm.gemini_provider import get_gemini_api_key

        gemini_key = get_gemini_api_key()
        gemini_configured = bool(gemini_key)
        gemini_key_source = "Không"
        if gemini_configured:
            import os
            gemini_key_source = "Biến môi trường" if os.getenv("GEMINI_API_KEY") else "Windows Credential Manager"

        gemini_reachable = False
        if gemini_configured:
            gemini_reachable = app_router.is_network_available()

        ollama_running = False
        ollama_models: list[str] = []
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            res = sock.connect_ex(("127.0.0.1", 11434))
            ollama_running = (res == 0)
            sock.close()
            if ollama_running:
                ollama_models = await app_router.ollama_provider.list_models()
        except Exception:
            pass

        gemini_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        if gemini_reachable and hasattr(app_router.gemini_provider, "list_models"):
            try:
                available = await app_router.gemini_provider.list_models()
                if available:
                    gemini_models = available
            except Exception:
                pass

        return {
            "gemini_configured": gemini_configured,
            "gemini_key_source": gemini_key_source,
            "gemini_reachable": gemini_reachable,
            "ollama_running": ollama_running,
            "ollama_models": ollama_models,
            "mode": app_router.mode,
            "gemini_model": app_config.gemini_model,
            "gemini_models": gemini_models,
            "local_model": app_config.local_model,
            "autostart_enabled": is_autostart_enabled(),
            "workspace_dir": str(app_config.workspace_dir),
            "timezone": app_config.timezone,
        }

    @app.get("/api/settings/gemini-keys", response_model=GeminiKeysResponse, dependencies=[Depends(require_session_token)])
    async def list_gemini_keys() -> dict[str, Any]:
        """Lấy danh sách các Gemini API Keys đã lưu dưới dạng đã che giấu."""
        from assistant.llm.gemini_provider import get_gemini_api_keys, mask_api_key

        keys = get_gemini_api_keys()
        masked_items: list[dict[str, Any]] = []
        active_id = None
        for k in keys:
            is_act = bool(k.get("is_active", False))
            if is_act:
                active_id = k.get("id")
            masked_items.append({
                "id": k.get("id", ""),
                "name": k.get("name", "Khóa"),
                "masked_key": mask_api_key(k.get("key", "")),
                "created_at": k.get("created_at", ""),
                "is_active": is_act,
            })
        return {"ok": True, "keys": masked_items, "active_id": active_id}

    @app.post("/api/settings/gemini-keys", dependencies=[Depends(require_session_token)])
    async def create_gemini_key(req: GeminiKeyCreateRequest) -> dict[str, Any]:
        """Thêm một Gemini API Key mới vào Windows Credential Manager."""
        from assistant.llm.gemini_provider import add_gemini_api_key

        clean_key = req.api_key.strip().strip("\"'")
        if not clean_key:
            raise HTTPException(status_code=400, detail="Khóa API Key không được để trống")

        try:
            item = add_gemini_api_key(clean_key, req.name or "")
            return {
                "ok": True,
                "message": f"Đã lưu thành công '{item['name']}' vào Windows Credential Manager!",
                "key_id": item["id"],
            }
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Lỗi lưu khóa: {err}")

    @app.put("/api/settings/gemini-keys/{key_id}", dependencies=[Depends(require_session_token)])
    async def update_gemini_key_endpoint(key_id: str, req: GeminiKeyUpdateRequest) -> dict[str, Any]:
        """Cập nhật tên hoặc giá trị của khóa Gemini API đã lưu."""
        from assistant.llm.gemini_provider import update_gemini_api_key

        try:
            item = update_gemini_api_key(key_id, api_key=req.api_key, name=req.name)
            return {
                "ok": True,
                "message": f"Đã cập nhật khóa '{item['name']}' thành công!",
                "key_id": item["id"],
            }
        except Exception as err:
            raise HTTPException(status_code=400, detail=str(err))

    @app.post("/api/settings/gemini-keys/{key_id}/active", dependencies=[Depends(require_session_token)])
    async def set_active_key(key_id: str) -> dict[str, Any]:
        """Chọn một khóa làm khóa hoạt động chính."""
        from assistant.llm.gemini_provider import set_active_gemini_api_key

        ok = set_active_gemini_api_key(key_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Không tìm thấy khóa được chỉ định")
        return {"ok": True, "message": "Đã chuyển sang sử dụng khóa này thành công!"}

    @app.delete("/api/settings/gemini-keys/{key_id}", dependencies=[Depends(require_session_token)])
    async def remove_gemini_key(key_id: str) -> dict[str, Any]:
        """Xóa một Gemini API Key khỏi danh sách."""
        from assistant.llm.gemini_provider import delete_gemini_api_key

        ok = delete_gemini_api_key(key_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Không tìm thấy khóa để xóa")
        return {"ok": True, "message": "Đã xóa khóa thành công!"}

    @app.post("/api/settings/gemini-keys/test", dependencies=[Depends(require_session_token)])
    async def test_key_endpoint(req: GeminiKeyTestRequest) -> dict[str, Any]:
        """Kiểm tra xem khóa Gemini API có hoạt động với Google hay không."""
        from assistant.llm.gemini_provider import (
            get_gemini_api_keys,
            test_gemini_api_key_connectivity,
        )

        target_key = ""
        if req.api_key and req.api_key.strip():
            target_key = req.api_key.strip().strip("\"'")
        elif req.key_id:
            keys = get_gemini_api_keys()
            for k in keys:
                if k.get("id") == req.key_id:
                    target_key = k.get("key", "")
                    break

        if not target_key:
            raise HTTPException(status_code=400, detail="Vui lòng cung cấp khóa API hoặc chọn khóa cần kiểm tra")

        success, msg = test_gemini_api_key_connectivity(target_key)
        return {"ok": success, "message": msg}

    @app.post("/api/settings/gemini-key", dependencies=[Depends(require_session_token)])
    async def set_gemini_key(req: KeyUpdateRequest) -> dict[str, Any]:
        """Lưu Gemini API Key an toàn vào Windows Credential Manager bằng keyring."""
        from assistant.llm.gemini_provider import add_gemini_api_key
        new_key = req.api_key.strip().strip("\"'")
        if not new_key:
            raise HTTPException(status_code=400, detail="Khóa API Key không được để trống")

        try:
            import keyring
            keyring.set_password("TroLyAI", "GEMINI_API_KEY", new_key)
            SecretFilter.register_secret(new_key)
            add_gemini_api_key(new_key, "Khóa chính")
            return {"ok": True, "message": "Đã lưu Gemini API Key an toàn vào Windows Credential Manager!"}
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Lỗi lưu trữ Windows Credential Manager: {err}")

    @app.post("/api/settings/model", dependencies=[Depends(require_session_token)])
    async def update_model_mode(req: ModelModeUpdateRequest) -> dict[str, Any]:
        """Cập nhật chế độ định tuyến model (auto / gemini / local)."""
        app_router.set_mode(req.mode)
        return {"ok": True, "mode": app_router.mode}

    @app.post("/api/settings/local-model", dependencies=[Depends(require_session_token)])
    async def update_local_model(req: dict[str, Any]) -> dict[str, Any]:
        """Cập nhật mô hình Ollama cục bộ đang hoạt động."""
        new_model = str(req.get("local_model", "")).strip()
        if not new_model:
            raise HTTPException(status_code=400, detail="Tên model không được để trống")

        try:
            object.__setattr__(app_config, "local_model", new_model)
        except Exception:
            pass
        if hasattr(app_router.ollama_provider, "set_model"):
            app_router.ollama_provider.set_model(new_model)

        # Cập nhật vào config/settings.toml nếu có để ghi nhớ
        try:
            candidate_paths = [
                Path("config/settings.toml"),
                Path(__file__).resolve().parent.parent.parent / "config" / "settings.toml",
            ]
            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).parent
                candidate_paths.insert(0, exe_dir / "config" / "settings.toml")

            for settings_path in candidate_paths:
                if settings_path.is_file():
                    content = settings_path.read_text(encoding="utf-8")
                    updated = re.sub(
                        r'local_model\s*=\s*["\'][^"\']*["\']',
                        f'local_model = "{new_model}"',
                        content,
                    )
                    settings_path.write_text(updated, encoding="utf-8")
                    break
        except Exception:
            pass

        return {"ok": True, "local_model": app_config.local_model}

    @app.post("/api/settings/gemini-model", dependencies=[Depends(require_session_token)])
    async def update_gemini_model(req: dict[str, Any]) -> dict[str, Any]:
        """Cập nhật mô hình Google Gemini đang hoạt động."""
        new_model = str(req.get("gemini_model", "")).strip()
        if not new_model:
            raise HTTPException(status_code=400, detail="Tên model Gemini không được để trống")

        try:
            object.__setattr__(app_config, "gemini_model", new_model)
        except Exception:
            pass
        if hasattr(app_router.gemini_provider, "set_model"):
            app_router.gemini_provider.set_model(new_model)

        # Cập nhật vào config/settings.toml nếu có để ghi nhớ
        try:
            candidate_paths = [
                Path("config/settings.toml"),
                Path(__file__).resolve().parent.parent.parent / "config" / "settings.toml",
            ]
            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).parent
                candidate_paths.insert(0, exe_dir / "config" / "settings.toml")

            for settings_path in candidate_paths:
                if settings_path.is_file():
                    content = settings_path.read_text(encoding="utf-8")
                    updated = re.sub(
                        r'gemini_model\s*=\s*["\'][^"\']*["\']',
                        f'gemini_model = "{new_model}"',
                        content,
                    )
                    settings_path.write_text(updated, encoding="utf-8")
                    break
        except Exception:
            pass

        return {"ok": True, "gemini_model": app_config.gemini_model}

    @app.post("/api/settings/autostart", dependencies=[Depends(require_session_token)])
    async def update_autostart(req: AutostartUpdateRequest) -> dict[str, Any]:
        """Bật hoặc tắt tính năng tự khởi động cùng Windows."""
        from assistant.desktop.autostart import disable_autostart, enable_autostart, is_autostart_enabled
        if req.enabled:
            success = enable_autostart(minimized=True)
        else:
            success = disable_autostart()
        return {"ok": success, "autostart_enabled": is_autostart_enabled()}

    @app.get("/api/settings/hotkey", dependencies=[Depends(require_session_token)])
    async def get_hotkey_settings() -> dict[str, Any]:
        """Lấy trạng thái cấu hình phím tắt toàn cục Spotlight Mode."""
        from assistant.desktop.hotkey import get_hotkey_manager
        mgr = get_hotkey_manager()
        return {
            "ok": True,
            "enabled": mgr.is_enabled(),
            "shortcut": "Ctrl+Shift+Space",
        }

    @app.post("/api/settings/hotkey", dependencies=[Depends(require_session_token)])
    async def update_hotkey_settings(req: HotkeyUpdateRequest) -> dict[str, Any]:
        """Bật hoặc tắt phím tắt toàn cục Spotlight Mode."""
        from assistant.desktop.hotkey import get_hotkey_manager
        mgr = get_hotkey_manager()
        mgr.set_enabled(req.enabled)
        return {
            "ok": True,
            "enabled": mgr.is_enabled(),
            "shortcut": "Ctrl+Shift+Space",
        }

    # =========================================================================
    # REST API: TẢI TỆP TIN LÊN WORKSPACE (FILE UPLOAD / DRAG & DROP)
    # =========================================================================

    @app.post("/api/upload-file", response_model=FileUploadResponse, dependencies=[Depends(require_session_token)])
    async def upload_file(request: Request) -> dict[str, Any]:
        """Tải tệp tin lên thư mục làm việc an toàn (Workspace) qua Kéo-Thả.

        - Hỗ trợ cả python-multipart (nếu có) và fallback thuần Python (email/MIME tiêu chuẩn).
        - Kiểm tra tên tệp an toàn, chống path traversal bằng resolve_in_workspace().
        - Giới hạn kích thước tối đa 25MB (25 * 1024 * 1024 bytes).
        - Ghi tệp an toàn vào workspace_dir.
        """
        from assistant.safety.paths import PathSecurityError, resolve_in_workspace

        max_bytes = 25 * 1024 * 1024
        filename: str | None = None
        file_bytes: bytes | None = None
        file_stream: Any = None

        # 1. Thử phân tích form data nếu thư viện python-multipart đã cài đặt
        try:
            form = await request.form()
            file_obj = form.get("file")
            if file_obj and hasattr(file_obj, "filename"):
                filename = file_obj.filename
                file_stream = file_obj
        except Exception:
            pass

        # 2. Fallback: Tự phân tích multipart/form-data thuần Python bằng thư viện chuẩn email
        if filename is None:
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" in content_type:
                raw_body = await request.body()
                if len(raw_body) > max_bytes + (64 * 1024):
                    raise HTTPException(
                        status_code=400,
                        detail="Dung lượng tệp vượt quá giới hạn tối đa cho phép (25MB).",
                    )
                import email

                header_bytes = f"Content-Type: {content_type}\r\n\r\n".encode("latin1", errors="replace")
                msg = email.message_from_bytes(header_bytes + raw_body)
                for part in msg.walk():
                    fn = part.get_filename()
                    if fn:
                        filename = fn
                        payload = part.get_payload(decode=True)
                        file_bytes = payload if isinstance(payload, bytes) else (payload.encode("utf-8") if payload else b"")
                        break
            elif request.headers.get("x-filename"):
                filename = request.headers.get("x-filename")
                file_bytes = await request.body()

        if not filename:
            raise HTTPException(status_code=400, detail="Tên tệp không được để trống hoặc không tìm thấy tệp tải lên.")

        # Lấy tên file gốc an toàn, loại bỏ tiền tố đường dẫn nguy hiểm
        raw_name = Path(filename).name.strip()
        if not raw_name:
            raise HTTPException(status_code=400, detail="Tên tệp không hợp lệ.")

        try:
            target_path = resolve_in_workspace(raw_name, workspace_dir=app_config.workspace_dir)
        except PathSecurityError as err:
            raise HTTPException(status_code=400, detail=f"Tên tệp vi phạm an toàn bảo mật: {err}")

        total_size = 0
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if file_bytes is not None:
            total_size = len(file_bytes)
            if total_size > max_bytes:
                raise HTTPException(
                    status_code=400,
                    detail="Dung lượng tệp vượt quá giới hạn tối đa cho phép (25MB).",
                )
            try:
                target_path.write_bytes(file_bytes)
            except Exception as exc:
                logger.error("Lỗi khi ghi tệp tải lên: %s", exc)
                raise HTTPException(status_code=500, detail=f"Lỗi ghi tệp lên đĩa: {exc}")
        elif file_stream is not None:
            try:
                with target_path.open("wb") as out_f:
                    while chunk := await file_stream.read(64 * 1024):
                        total_size += len(chunk)
                        if total_size > max_bytes:
                            out_f.close()
                            if target_path.is_file():
                                target_path.unlink(missing_ok=True)
                            raise HTTPException(
                                status_code=400,
                                detail="Dung lượng tệp vượt quá giới hạn tối đa cho phép (25MB).",
                            )
                        out_f.write(chunk)
            except HTTPException:
                raise
            except Exception as exc:
                logger.error("Lỗi khi ghi tệp tải lên: %s", exc)
                raise HTTPException(status_code=500, detail=f"Lỗi ghi tệp lên đĩa: {exc}")
        else:
            raise HTTPException(status_code=400, detail="Không tìm thấy dữ liệu tệp tải lên.")

        return {
            "ok": True,
            "filename": raw_name,
            "path": str(target_path),
            "size": total_size,
            "message": f"Đã tải tệp '{raw_name}' ({total_size} bytes) lên thư mục làm việc an toàn.",
        }

    # =========================================================================
    # REST API: NHẬT KÝ KIỂM TOÁN (AUDIT LOGS)
    # =========================================================================

    @app.get("/api/audit", dependencies=[Depends(require_session_token)])
    async def get_audit_logs(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
        """Lấy danh sách các sự kiện kiểm toán gần nhất từ audit.jsonl (được che bí mật)."""
        audit_file = app_config.data_dir / "audit.jsonl"
        if not audit_file.is_file():
            return []

        entries: list[dict[str, Any]] = []
        try:
            with open(audit_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        try:
                            entries.append(json.loads(line_str))
                        except Exception:
                            pass
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Không thể đọc nhật ký kiểm toán: {err}")

        # Trả về các dòng mới nhất lên đầu
        return entries[-limit:][::-1]

    # =========================================================================
    # WEBSOCKET CHAT
    # =========================================================================


    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket) -> None:
        """Kênh truyền WebSocket hai chiều cho hội thoại và phê duyệt quyền."""
        await ws_manager.handle_connection(websocket)

    # =========================================================================
    # PHỤC VỤ GIAO DIỆN TĨNH (STATIC UI)
    # =========================================================================

    static_dir = Path(__file__).resolve().parent.parent / "ui_static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def serve_index(request: Request):
            """Phục vụ trang chủ giao diện Trợ Lý AI."""
            index_path = static_dir / "index.html"
            if index_path.is_file():
                return FileResponse(index_path)
            return {"message": "Trợ Lý AI - Đang tải giao diện..."}

    return app
