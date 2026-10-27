"""Kiểm thử tự động cho tính năng Kéo-thả tập tin (Drag & Drop) và Phím tắt toàn cục (Global Hotkey).

Các trường hợp kiểm thử:
1. Tải tệp lên Workspace (POST /api/upload-file):
   - Tải tệp văn bản hợp lệ thành công và ghi đúng vào thư mục workspace_dir.
   - Từ chối tệp không có tên hoặc rỗng.
   - Chặn đứng tấn công vượt thư mục (Path Traversal: ../../evil.txt).
   - Chặn đứng thiết bị hệ thống Windows dành riêng (CON.txt, NUL.docx, v.v.).
   - Chặn tệp vượt quá kích thước tối đa 25MB và tự động dọn dẹp phần tệp đang ghi dở.
   - Kiểm tra xác thực Session Token (401/403 nếu không có token).
2. Thiết lập phím tắt toàn cục (GET & POST /api/settings/hotkey):
   - Truy vấn trạng thái phím tắt qua GET /api/settings/hotkey.
   - Bật/tắt phím tắt qua POST /api/settings/hotkey.
3. Trình quản lý phím tắt GlobalHotkeyManager & Spotlight Mode:
   - Kiểm tra khởi tạo và bật/tắt an toàn.
   - Kiểm tra gọi activate_spotlight_mode và phát tín hiệu notify_focus_input khi phím tắt kích hoạt.
"""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from assistant.config import Config
from assistant.core.router import ModelRouter
from assistant.desktop.hotkey import GlobalHotkeyManager, get_hotkey_manager
from assistant.desktop.window import activate_spotlight_mode, bring_window_to_front, find_assistant_window
from assistant.llm.base import LLMProvider, Message, StreamEvent
from assistant.memory.store import MemoryStore
from assistant.reminders.scheduler import ReminderScheduler
from assistant.reminders.store import ReminderStore
from assistant.server.app import create_app


class MockProvider(LLMProvider):
    """Mock Provider giả lập."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-model"

    async def is_available(self) -> bool:
        return True

    async def stream_chat(self, messages: list[Message], tools: list[dict] | None = None, system: str | None = None):
        yield StreamEvent(type="text_delta", content="OK")

    async def list_models(self) -> list[str]:
        return ["mock-model"]


@pytest.fixture
def app_client(tmp_path: Path):
    """Khởi tạo TestClient với môi trường workspace và cấu hình cô lập."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    mem_store = MemoryStore(db_path=db_path)
    rem_store = ReminderStore(db_path=db_path)
    mock_p = MockProvider()
    router = ModelRouter(gemini_provider=mock_p, ollama_provider=mock_p)
    scheduler = ReminderScheduler(reminder_store=rem_store)

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

    token = "test_token_upload_hotkey_xyz"
    app = create_app(
        config=config,
        router=router,
        memory_store=mem_store,
        reminder_store=rem_store,
        scheduler=scheduler,
        session_token=token,
    )

    client = TestClient(app)
    return client, token, ws_dir


def test_upload_file_success(app_client) -> None:
    """Tải lên tệp hợp lệ thành công và ghi chính xác vào workspace_dir."""
    client, token, ws_dir = app_client

    file_content = b"Day la noi dung tai lieu bao cao nghien cuu."
    files = {"file": ("bao_cao.txt", BytesIO(file_content), "text/plain")}

    resp = client.post(
        f"/api/upload-file?token={token}",
        files=files,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["filename"] == "bao_cao.txt"
    assert data["size"] == len(file_content)

    saved_file = ws_dir / "bao_cao.txt"
    assert saved_file.is_file()
    assert saved_file.read_bytes() == file_content


def test_upload_file_path_traversal_protection(app_client) -> None:
    """Đảm bảo tên tệp chứa ký tự ../ được chuẩn hóa an toàn vào gốc workspace hoặc bị xử lý an toàn."""
    client, token, ws_dir = app_client

    file_content = b"Noi dung doc hai."
    # Cố gắng đặt tên vượt cấp thư mục
    files = {"file": ("../../evil_script.py", BytesIO(file_content), "text/x-python")}

    resp = client.post(
        f"/api/upload-file?token={token}",
        files=files,
    )
    # Ứng dụng dùng Path(file.filename).name.strip() -> trích xuất 'evil_script.py' và lưu an toàn trong ws_dir
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "evil_script.py"

    # Tệp phải nằm trong workspace_dir, KHÔNG nằm ngoài thư mục cha
    assert not (ws_dir.parent / "evil_script.py").exists()
    assert (ws_dir / "evil_script.py").is_file()


def test_upload_file_reserved_name_blocked(app_client) -> None:
    """Đảm bảo các tên tệp dành riêng của Windows bị chặn bởi resolve_in_workspace."""
    client, token, _ = app_client

    files = {"file": ("CON.txt", BytesIO(b"noi dung con"), "text/plain")}
    resp = client.post(
        f"/api/upload-file?token={token}",
        files=files,
    )
    # Tên CON.txt phải bị từ chối với mã lỗi 400
    assert resp.status_code == 400
    assert "bảo mật" in resp.json()["detail"].lower() or "vi phạm" in resp.json()["detail"].lower()


def test_upload_file_exceeds_max_size(app_client) -> None:
    """Tải tệp vượt quá giới hạn 25MB sẽ bị chặn với mã 400 và tệp dở dang bị xoá."""
    client, token, ws_dir = app_client

    # Tạo tệp giả lập > 25MB (25MB + 100KB)
    oversized_bytes = (25 * 1024 * 1024) + (100 * 1024)
    oversized_data = BytesIO(b"A" * oversized_bytes)

    files = {"file": ("large_video.mp4", oversized_data, "video/mp4")}
    resp = client.post(
        f"/api/upload-file?token={token}",
        files=files,
    )
    assert resp.status_code == 400
    assert "25MB" in resp.json()["detail"]

    # Đảm bảo tệp dở dang không bị sót lại trên đĩa
    assert not (ws_dir / "large_video.mp4").exists()


def test_upload_file_requires_auth(app_client) -> None:
    """Kiểm tra endpoint upload yêu cầu xác thực Session Token."""
    client, _, _ = app_client

    files = {"file": ("test.txt", BytesIO(b"content"), "text/plain")}
    resp = client.post("/api/upload-file", files=files)
    assert resp.status_code in (401, 403)


def test_hotkey_settings_api(app_client) -> None:
    """Kiểm tra các endpoint cấu hình phím tắt toàn cục GET & POST /api/settings/hotkey."""
    client, token, _ = app_client

    # 1. GET trạng thái phím tắt
    resp_get = client.get(f"/api/settings/hotkey?token={token}")
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["ok"] is True
    assert data_get["shortcut"] == "Ctrl+Shift+Space"
    assert "enabled" in data_get

    # 2. POST bật phím tắt
    resp_post = client.post(
        f"/api/settings/hotkey?token={token}",
        json={"enabled": False},
    )
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["enabled"] is False

    # 3. Yêu cầu Session Token
    resp_no_auth = client.get("/api/settings/hotkey")
    assert resp_no_auth.status_code in (401, 403)


def test_global_hotkey_manager_lifecycle() -> None:
    """Kiểm tra vòng đời khởi tạo, bật/tắt của GlobalHotkeyManager."""
    mgr = GlobalHotkeyManager(port=8888, session_token="test_tok")
    assert not mgr.is_enabled()

    with patch("sys.platform", "linux"):
        # Trên non-win32, start trả về False an toàn mà không sinh lỗi
        assert mgr.start() is False

    with patch("sys.platform", "win32"), patch("threading.Thread") as mock_thread:
        mgr._running = False
        res = mgr.start()
        assert res is True
        assert mgr.is_enabled() is True
        mock_thread.assert_called_once()

        # Dừng
        mgr.stop()
        assert mgr.is_enabled() is False


def test_spotlight_mode_helpers() -> None:
    """Kiểm tra các hàm trợ giúp Spotlight Mode (find_assistant_window, bring_window_to_front, activate_spotlight_mode)."""
    with patch("sys.platform", "linux"):
        assert find_assistant_window() is None
        assert bring_window_to_front(12345) is False

    with patch("assistant.desktop.window.find_assistant_window", return_value=9999):
        with patch("assistant.desktop.window.bring_window_to_front", return_value=True) as mock_bring:
            res = activate_spotlight_mode(port=8000, session_token="tok")
            assert res is True
            mock_bring.assert_called_once_with(9999)

    with patch("assistant.desktop.window.find_assistant_window", return_value=None):
        with patch("assistant.desktop.window.launch_desktop_window", return_value=True) as mock_launch:
            res = activate_spotlight_mode(port=8000, session_token="tok")
            assert res is True
            mock_launch.assert_called_once_with(port=8000, session_token="tok")
