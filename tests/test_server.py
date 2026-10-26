"""Kiểm thử tự động cho hệ thống máy chủ FastAPI, REST API và WebSocket (tests/test_server.py).

Kiểm tra:
1. Xác thực bảo mật Session Token (Chống CSRF/SSRF cục bộ):
   - Chặn 401 khi thiếu token.
   - Chặn 403 khi token không hợp lệ.
   - Cho phép 200 khi có token hợp lệ.
2. Vòng đời REST API:
   - Conversations: Tạo mới, danh sách, tin nhắn, xoá.
   - Memories: Thêm, tìm kiếm, sửa, xoá.
   - Reminders: Tạo, hoãn nhắc (snooze), huỷ.
   - Status: Kiểm tra các trường trạng thái.
3. Kênh truyền WebSocket /ws/chat:
   - Từ chối kết nối khi token sai.
   - Streaming text_delta và turn_done.
   - Luồng duyệt quyền bất đồng bộ (approval_required -> approval_response).
4. Khởi chạy cửa sổ Desktop (window.py).
"""

from collections.abc import AsyncIterator
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from assistant.config import Config
from assistant.core.router import ModelRouter
from assistant.desktop.window import find_edge_executable, launch_desktop_window
from assistant.llm.base import LLMProvider, Message, StreamEvent, ToolCall
from assistant.memory.store import MemoryStore
from assistant.reminders.scheduler import ReminderScheduler
from assistant.reminders.store import ReminderStore
from assistant.server.app import create_app


class MockServerProvider(LLMProvider):
    """Provider giả lập dùng cho kiểm thử WebSocket Server."""

    def __init__(self, response_text: str = "Xin chào từ Mock Server!", tool_calls: list[ToolCall] | None = None) -> None:
        self.response_text = response_text
        self.tool_calls = tool_calls or []
        self.default_model = "mock-server-model"

    @property
    def provider_name(self) -> str:
        return "mock"

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        for tc in self.tool_calls:
            yield StreamEvent(type="tool_call", content=tc)
        if self.response_text:
            yield StreamEvent(type="text_delta", content=self.response_text)

    async def list_models(self) -> list[str]:
        return ["mock-server-model"]


@pytest.fixture
def test_app_client(tmp_path: Path):
    """Khởi tạo TestClient với database và workspace cô lập trong tmp_path."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)

    db_path = tmp_path / "test_assistant.db"
    mem_store = MemoryStore(db_path=db_path)
    rem_store = ReminderStore(db_path=db_path)

    config = Config(
        workspace_dir=ws_dir,
        data_dir=tmp_path,
        timezone="Asia/Ho_Chi_Minh",
        gemini_model="gemini-2.5-flash",
        local_model="qwen2.5:7b",
        ollama_host="http://127.0.0.1:11434",
        daily_soft_limit=1000,
        max_context_tokens=4000,
        network_cache_seconds=10,
        ui_port=8000,
        log_level="INFO",
    )

    mock_provider = MockServerProvider(response_text="Tôi là Trợ Lý AI giả lập.")
    router = ModelRouter(gemini_provider=mock_provider, ollama_provider=mock_provider)
    scheduler = ReminderScheduler(reminder_store=rem_store)

    test_token = "valid_test_session_token_12345"
    app = create_app(
        config=config,
        router=router,
        memory_store=mem_store,
        reminder_store=rem_store,
        scheduler=scheduler,
        session_token=test_token,
    )

    client = TestClient(app)
    return client, test_token, mem_store, rem_store


def test_auth_token_protection(test_app_client) -> None:
    """Kiểm tra lớp phòng vệ Session Token ngăn truy cập lậu từ ngoài."""
    client, valid_token, _, _ = test_app_client

    # 1. Không truyền token -> 401 Unauthorized
    resp_no_token = client.get("/api/status")
    assert resp_no_token.status_code == 401

    # 2. Truyền token sai -> 403 Forbidden
    resp_wrong_token = client.get("/api/status", headers={"X-Session-Token": "invalid_token_999"})
    assert resp_wrong_token.status_code == 403

    # 3. Truyền token đúng qua Header -> 200 OK
    resp_header = client.get("/api/status", headers={"X-Session-Token": valid_token})
    assert resp_header.status_code == 200
    data = resp_header.json()
    assert "workspace_dir" in data
    assert "gemini_model" in data

    # 4. Truyền token đúng qua Query Parameter -> 200 OK
    resp_query = client.get(f"/api/status?token={valid_token}")
    assert resp_query.status_code == 200


def test_conversations_rest_api(test_app_client) -> None:
    """Kiểm tra vòng đời quản lý cuộc trò chuyện qua REST API."""
    client, token, mem_store, _ = test_app_client
    headers = {"X-Session-Token": token}

    # 1. Tạo mới cuộc trò chuyện
    create_res = client.post(
        "/api/conversations",
        headers=headers,
        json={"title": "Hội thoại thử nghiệm", "is_sensitive": False},
    )
    assert create_res.status_code == 200
    conv_data = create_res.json()
    conv_id = conv_data["id"]
    assert conv_data["title"] == "Hội thoại thử nghiệm"

    # 2. Lấy danh sách hội thoại
    list_res = client.get("/api/conversations", headers=headers)
    assert list_res.status_code == 200
    all_convs = list_res.json()
    assert any(c["id"] == conv_id for c in all_convs)

    # 3. Lấy tin nhắn
    mem_store.add_message(conv_id, role="user", content="Tin nhắn thử")
    msgs_res = client.get(f"/api/conversations/{conv_id}/messages", headers=headers)
    assert msgs_res.status_code == 200
    msgs = msgs_res.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Tin nhắn thử"

    # 4. Xoá cuộc trò chuyện
    del_res = client.delete(f"/api/conversations/{conv_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["ok"] is True


def test_memories_rest_api(test_app_client) -> None:
    """Kiểm tra các endpoint quản lý trí nhớ dài hạn (Memories API)."""
    client, token, _, _ = test_app_client
    headers = {"X-Session-Token": token}

    # 1. Thêm trí nhớ
    add_res = client.post(
        "/api/memories",
        headers=headers,
        json={"category": "project", "content": "Dự án Trợ Lý AI phiên bản 1.0"},
    )
    assert add_res.status_code == 200
    mem_id = add_res.json()["id"]

    # 2. Lấy danh sách trí nhớ
    list_res = client.get("/api/memories", headers=headers)
    assert list_res.status_code == 200
    memories = list_res.json()
    assert any(m["id"] == mem_id for m in memories)

    # 3. Tìm kiếm trí nhớ
    search_res = client.get("/api/memories?query=phiên bản", headers=headers)
    assert search_res.status_code == 200
    search_results = search_res.json()
    assert len(search_results) >= 1
    assert "Trợ Lý AI" in search_results[0]["content"]

    # 4. Cập nhật trí nhớ
    update_res = client.put(
        f"/api/memories/{mem_id}",
        headers=headers,
        json={"content": "Dự án Trợ Lý AI đã hoàn thành Phase 6"},
    )
    assert update_res.status_code == 200

    # 5. Xoá trí nhớ
    del_res = client.delete(f"/api/memories/{mem_id}", headers=headers)
    assert del_res.status_code == 200


def test_reminders_rest_api(test_app_client) -> None:
    """Kiểm tra các endpoint quản lý nhắc việc (Reminders API)."""
    client, token, _, _ = test_app_client
    headers = {"X-Session-Token": token}

    # 1. Tạo lời nhắc việc
    create_res = client.post(
        "/api/reminders",
        headers=headers,
        json={
            "message": "Kiểm tra kết quả kiểm thử",
            "trigger_at": "2026-10-27T09:00:00+07:00",
        },
    )
    assert create_res.status_code == 200
    rem_id = create_res.json()["id"]

    # 2. Liệt kê lời nhắc
    list_res = client.get("/api/reminders", headers=headers)
    assert list_res.status_code == 200
    reminders = list_res.json()
    assert any(r["id"] == rem_id for r in reminders)

    # 3. Hoãn lời nhắc (snooze 10 phút)
    snooze_res = client.post(
        f"/api/reminders/{rem_id}/snooze",
        headers=headers,
        json={"minutes": 10},
    )
    assert snooze_res.status_code == 200
    assert snooze_res.json()["ok"] is True

    # 4. Huỷ lời nhắc
    del_res = client.delete(f"/api/reminders/{rem_id}", headers=headers)
    assert del_res.status_code == 200


def test_static_index_serving(test_app_client) -> None:
    """Kiểm tra phục vụ trang tĩnh index.html."""
    client, _, _, _ = test_app_client
    res = client.get("/")
    assert res.status_code == 200
    assert "Trợ Lý AI" in res.text


def test_websocket_chat_streaming(test_app_client) -> None:
    """Kiểm tra luồng WebSocket chat và streaming sự kiện text_delta."""
    client, token, _, _ = test_app_client

    # 1. Thử kết nối với token sai -> từ chối
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/chat?token=wrong_token"):
            pass

    # 2. Kết nối với token đúng
    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        # Gửi tin nhắn người dùng
        ws.send_text(
            json.dumps({
                "type": "user_message",
                "message": "Xin chào Trợ lý!",
                "mode": "auto",
            })
        )

        received_types: list[str] = []
        received_text: list[str] = []

        # Đọc các sự kiện trả về
        for _ in range(5):
            raw = ws.receive_text()
            data = json.loads(raw)
            evt_type = data.get("type")
            received_types.append(evt_type)
            if evt_type == "text_delta":
                received_text.append(data["data"].get("content", ""))
            elif evt_type == "turn_done":
                break

        assert "text_delta" in received_types
        assert "turn_done" in received_types
        full_text = "".join(received_text)
        assert "Trợ Lý AI" in full_text


def test_websocket_approval_flow(tmp_path: Path) -> None:
    """Kiểm tra luồng phê duyệt bất đồng bộ (approval_required -> approval_response) trên WebSocket."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    target_file = ws_dir / "can_xoa.txt"
    target_file.write_text("Dữ liệu thử")

    db_path = tmp_path / "test_approval.db"
    mem_store = MemoryStore(db_path=db_path)
    rem_store = ReminderStore(db_path=db_path)

    config = Config(
        workspace_dir=ws_dir,
        data_dir=tmp_path,
        timezone="Asia/Ho_Chi_Minh",
        gemini_model="gemini-2.5-flash",
        local_model="qwen2.5:7b",
        ollama_host="http://127.0.0.1:11434",
        daily_soft_limit=1000,
        max_context_tokens=4000,
        network_cache_seconds=10,
        ui_port=8000,
        log_level="INFO",
    )

    # Provider giả lập sinh tool_call delete_path (mức CONFIRM)
    delete_call = ToolCall(
        id="call_del_1",
        name="delete_path",
        arguments={"path": "can_xoa.txt"},
    )
    mock_provider = MockServerProvider(response_text="Đã hoàn tất thao tác xoá.", tool_calls=[delete_call])
    router = ModelRouter(gemini_provider=mock_provider, ollama_provider=mock_provider)

    test_token = "token_approval_test"
    app = create_app(
        config=config,
        router=router,
        memory_store=mem_store,
        reminder_store=rem_store,
        session_token=test_token,
    )
    client = TestClient(app)

    with client.websocket_connect(f"/ws/chat?token={test_token}") as ws:
        # Gửi yêu cầu xoá file
        ws.send_text(
            json.dumps({
                "type": "user_message",
                "message": "Hãy xoá file can_xoa.txt",
                "mode": "auto",
            })
        )

        approval_req_id = None
        for _ in range(10):
            raw = ws.receive_text()
            data = json.loads(raw)
            if data.get("type") == "approval_required":
                approval_req_id = data["data"]["request_id"]
                assert data["data"]["tool_name"] == "delete_path"
                break

        assert approval_req_id is not None, "Không nhận được sự kiện approval_required từ máy chủ"

        # Gửi phản hồi đồng ý duyệt (approve = True)
        ws.send_text(
            json.dumps({
                "type": "approval_response",
                "request_id": approval_req_id,
                "approved": True,
            })
        )

        # Đọc tiếp cho đến khi hoàn thành
        received_done = False
        for _ in range(10):
            raw = ws.receive_text()
            data = json.loads(raw)
            if data.get("type") == "turn_done":
                received_done = True
                break

        assert received_done is True


def test_desktop_window_utilities() -> None:
    """Kiểm tra module desktop/window.py tìm edge và mở ứng dụng không dùng shell=True."""
    # 1. find_edge_executable không ném lỗi
    edge_res = find_edge_executable()
    assert edge_res is None or isinstance(edge_res, str)

    # 2. launch_desktop_window với mock Popen
    with patch("subprocess.Popen") as mock_popen, patch("assistant.desktop.window.find_edge_executable", return_value="C:\\fake\\msedge.exe"):
        ok = launch_desktop_window(port=8000, session_token="token123")
        assert ok is True
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert isinstance(args, list)
        assert "--app=http://127.0.0.1:8000/?token=token123" in args


def test_settings_api_endpoints(test_app_client: tuple[TestClient, str]) -> None:
    """Kiểm tra các endpoint thiết lập và chẩn đoán bảo mật /api/settings/*."""
    client, token = test_app_client
    headers = {"X-Session-Token": token}

    # 1. GET /api/settings/diagnostics
    with patch("assistant.server.app.check_gemini_key", return_value=(True, "Key hợp lệ", "gemini-2.5-flash")):
        res = client.get("/api/settings/diagnostics", headers=headers)
        assert res.status_code == 200
        diag = res.json()
        assert "gemini_status" in diag
        assert "ollama_status" in diag
        assert "mode" in diag
        assert "is_autostart_enabled" in diag

    # 2. POST /api/settings/gemini-key
    with patch("assistant.main.store_gemini_key", return_value=True):
        res = client.post(
            "/api/settings/gemini-key",
            headers=headers,
            json={"api_key": "AIzaSyTestKeyValid1234567890"},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True

    # 3. POST /api/settings/model
    res = client.post(
        "/api/settings/model",
        headers=headers,
        json={"mode": "only_local"},
    )
    assert res.status_code == 200
    assert res.json()["mode"] == "only_local"

    # 4. POST /api/settings/autostart
    with patch("assistant.server.app.enable_autostart", return_value=True), patch("assistant.server.app.is_autostart_enabled", return_value=True):
        res = client.post(
            "/api/settings/autostart",
            headers=headers,
            json={"enabled": True},
        )
        assert res.status_code == 200
        assert res.json()["enabled"] is True

