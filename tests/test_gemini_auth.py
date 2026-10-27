import json
import os
from unittest.mock import MagicMock, patch
import pytest
from starlette.testclient import TestClient

from assistant.llm.base import ProviderError
from assistant.llm.gemini_provider import (
    GeminiProvider,
    add_gemini_api_key,
    classify_gemini_error,
    delete_gemini_api_key,
    get_gemini_api_key,
    get_gemini_api_keys,
    mask_api_key,
    save_gemini_api_keys,
    set_active_gemini_api_key,
    test_gemini_api_key_connectivity,
)
from assistant.safety.secrets import get_secret, save_secret


def test_get_gemini_api_key_strips_quotes_and_spaces() -> None:
    """Tái hiện và kiểm tra: get_gemini_api_key phải tự động lọc bỏ dấu ngoặc kép và khoảng trắng."""
    # 1. Trường hợp lưu trong keyring có dấu ngoặc kép hoặc đơn
    with patch("keyring.get_password", return_value='  "AIzaSyTestKeyWithDoubleQuotes123456"  '):
        key = get_gemini_api_key()
        assert key == "AIzaSyTestKeyWithDoubleQuotes123456"

    with patch("keyring.get_password", return_value="  'AIzaSyTestKeyWithSingleQuotes123456'  "):
        key = get_gemini_api_key()
        assert key == "AIzaSyTestKeyWithSingleQuotes123456"

    # 2. Trường hợp đọc từ biến môi trường có dấu ngoặc kép
    with patch("keyring.get_password", return_value=None):
        with patch.dict(os.environ, {"GEMINI_API_KEY": '"AIzaSyFromEnvWithQuotes"'}):
            key = get_gemini_api_key()
            assert key == "AIzaSyFromEnvWithQuotes"


def test_classify_gemini_error_actionable_messages() -> None:
    """Kiểm tra phân loại lỗi xác thực và cấp quyền chi tiết từ Google Gemini."""
    # 1. Khóa không hợp lệ (400 API_KEY_INVALID)
    err_invalid = Exception("400 Bad Request: API_KEY_INVALID. API key not valid. Please pass a valid API key.")
    res = classify_gemini_error(err_invalid)
    assert res.kind == "auth"
    assert "https://aistudio.google.com/app/apikey" in res.message or "assistant set-key" in res.message

    # 2. Chưa bật Generative Language API trên Google Cloud
    err_disabled = Exception(
        "403 Forbidden: PERMISSION_DENIED. Generative Language API has not been used in project 123456 before or it is disabled."
    )
    res = classify_gemini_error(err_disabled)
    assert res.kind == "auth"
    assert "Generative Language API" in res.message

    # 3. Khóa bị giới hạn referrer/IP
    err_restricted = Exception("403 Forbidden: Requests from this client are blocked by API key restrictions.")
    res = classify_gemini_error(err_restricted)
    assert res.kind == "auth"
    assert "giới hạn" in res.message or "restrictions" in res.message.lower()


def test_gemini_provider_client_default_v1beta() -> None:
    """Kiểm tra GeminiProvider sử dụng client chuẩn v1beta mặc định để hỗ trợ gemini-2.0-flash."""
    with patch("assistant.llm.gemini_provider.get_gemini_api_key", return_value="AIzaSyValidDummyKey"):
        provider = GeminiProvider()
        assert provider.default_model == "gemini-2.0-flash" or "gemini" in provider.default_model
        with patch("google.genai.Client") as mock_client_cls:
            provider._get_client()
            mock_client_cls.assert_called_once_with(api_key="AIzaSyValidDummyKey")


def test_safety_secrets_strip_quotes() -> None:
    """Kiểm tra module safety.secrets loại bỏ dấu ngoặc kép khi lưu và lấy khóa bí mật."""
    with patch("keyring.set_password") as mock_set:
        save_secret("TEST_KEY", '  "my_secret_token"  ')
        mock_set.assert_called_once_with("TroLyAI", "TEST_KEY", "my_secret_token")

    with patch("keyring.get_password", return_value="'my_secret_token'"):
        val = get_secret("TEST_KEY")
        assert val == "my_secret_token"


def test_mask_api_key() -> None:
    """Kiểm tra che giấu API key an toàn để hiển thị trên giao diện."""
    assert mask_api_key("") == ""
    assert mask_api_key("AIzaSy1234567890abcdef1234567890abcdef") == "AIzaSy12...cdef"
    assert mask_api_key("short") == "sho...rt"


def test_multi_key_crud_lifecycle() -> None:
    """Kiểm tra vòng đời thêm, liệt kê, kích hoạt và xóa nhiều API keys."""
    mock_storage: dict[str, str] = {}

    def fake_get_password(service: str, key_name: str) -> str | None:
        return mock_storage.get(f"{service}:{key_name}")

    def fake_set_password(service: str, key_name: str, val: str) -> None:
        mock_storage[f"{service}:{key_name}"] = val

    with patch("keyring.get_password", side_effect=fake_get_password), \
         patch("keyring.set_password", side_effect=fake_set_password):

        # 1. Danh sách ban đầu trống
        assert get_gemini_api_keys() == []

        # 2. Thêm key 1 (tự động thành active)
        k1 = add_gemini_api_key("AIzaSyKeyOne1111111111111111111111111", "Khóa AI Studio 1")
        assert k1["name"] == "Khóa AI Studio 1"
        assert k1["is_active"] is True
        assert get_gemini_api_key() == "AIzaSyKeyOne1111111111111111111111111"

        # 3. Thêm key 2 (dự phòng, is_active=False)
        k2 = add_gemini_api_key("AIzaSyKeyTwo2222222222222222222222222", "Khóa Dự Phòng 2")
        assert k2["is_active"] is False
        all_keys = get_gemini_api_keys()
        assert len(all_keys) == 2

        # 4. Kích hoạt key 2
        assert set_active_gemini_api_key(k2["id"]) is True
        assert get_gemini_api_key() == "AIzaSyKeyTwo2222222222222222222222222"

        # 5. Xóa key 2 -> key 1 tự động được kích hoạt trở lại
        assert delete_gemini_api_key(k2["id"]) is True
        rem_keys = get_gemini_api_keys()
        assert len(rem_keys) == 1
        assert rem_keys[0]["id"] == k1["id"]
        assert rem_keys[0]["is_active"] is True
        assert get_gemini_api_key() == "AIzaSyKeyOne1111111111111111111111111"


def test_gemini_key_connectivity_success() -> None:
    """Kiểm tra test_gemini_api_key_connectivity khi Google phản hồi thành công."""
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.get.return_value = MagicMock(name="models/gemini-2.0-flash")

        ok, msg = test_gemini_api_key_connectivity("AIzaSyValidDummyKey123")
        assert ok is True
        assert "hoạt động rất tốt" in msg


def test_gemini_key_connectivity_failure() -> None:
    """Kiểm tra test_gemini_api_key_connectivity khi Google báo lỗi API_KEY_INVALID."""
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.get.side_effect = Exception("400 Bad Request: API_KEY_INVALID")

        ok, msg = test_gemini_api_key_connectivity("AIzaSyBadKey")
        assert ok is False
        assert "không hợp lệ" in msg


@pytest.mark.asyncio
async def test_server_gemini_keys_rest_endpoints(tmp_path) -> None:
    """Kiểm tra toàn bộ các endpoint REST API: GET, POST, DELETE, ACTIVE, TEST."""
    from assistant.config import Config
    from assistant.memory.store import MemoryStore
    from assistant.reminders.store import ReminderStore
    from assistant.reminders.scheduler import ReminderScheduler
    from assistant.core.router import ModelRouter
    from assistant.server.app import create_app, set_current_session_token

    cfg = Config(workspace_dir=tmp_path / "ws", data_dir=tmp_path / "data")
    mem_store = MemoryStore(tmp_path / "mem.db")
    rem_store = ReminderStore(tmp_path / "rem.db")
    scheduler = ReminderScheduler(rem_store)
    router = ModelRouter(cfg)

    app = create_app(
        config=cfg,
        router=router,
        memory_store=mem_store,
        reminder_store=rem_store,
        reminder_scheduler=scheduler,
    )
    client = TestClient(app)
    set_current_session_token("test-secret-token")
    headers = {"X-Session-Token": "test-secret-token"}

    mock_db: dict[str, str] = {}
    with patch("keyring.get_password", side_effect=lambda s, k: mock_db.get(f"{s}:{k}")), \
         patch("keyring.set_password", side_effect=lambda s, k, v: mock_db.update({f"{s}:{k}": v})):

        # 1. Thêm key mới qua POST /api/settings/gemini-keys
        res = client.post(
            "/api/settings/gemini-keys",
            headers=headers,
            json={"api_key": "AIzaSyPrimary001", "name": "Key Số 1"},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True
        key1_id = res.json()["key_id"]

        # 2. Thêm key thứ hai
        res2 = client.post(
            "/api/settings/gemini-keys",
            headers=headers,
            json={"api_key": "AIzaSySecondary002", "name": "Key Số 2"},
        )
        assert res2.status_code == 200
        key2_id = res2.json()["key_id"]

        # 3. Lấy danh sách qua GET /api/settings/gemini-keys
        res_list = client.get("/api/settings/gemini-keys", headers=headers)
        assert res_list.status_code == 200
        data = res_list.json()
        assert len(data["keys"]) == 2
        assert data["active_id"] == key1_id

        # 4. Kích hoạt key 2
        res_act = client.post(f"/api/settings/gemini-keys/{key2_id}/active", headers=headers)
        assert res_act.status_code == 200
        assert res_act.json()["ok"] is True

        # 5. Sửa (PUT) key 2: Chỉ đổi tên (không truyền api_key) vẫn phải thành công
        res_put_name_only = client.put(
            f"/api/settings/gemini-keys/{key2_id}",
            headers=headers,
            json={"name": "Key Số 2 Chỉ Đổi Tên"},
        )
        assert res_put_name_only.status_code == 200
        assert res_put_name_only.json()["ok"] is True

        # 5b. Sửa (PUT) key 2: Cập nhật cả key mới
        res_put = client.put(
            f"/api/settings/gemini-keys/{key2_id}",
            headers=headers,
            json={"name": "Key Số 2 Đã Sửa", "api_key": "AIzaSyUpdatedKey002"},
        )
        assert res_put.status_code == 200
        assert res_put.json()["ok"] is True

        # 6. Kiểm tra test endpoint với key_id
        with patch("assistant.llm.gemini_provider.test_gemini_api_key_connectivity", return_value=(True, "Khóa tốt")):
            res_test = client.post(
                "/api/settings/gemini-keys/test",
                headers=headers,
                json={"key_id": key2_id},
            )
            assert res_test.status_code == 200
            assert res_test.json()["ok"] is True

        # 7. Xóa key 1
        res_del = client.delete(f"/api/settings/gemini-keys/{key1_id}", headers=headers)
        assert res_del.status_code == 200
        assert res_del.json()["ok"] is True


def test_dual_persistence_backup_fallback(tmp_path) -> None:
    """Kiểm tra cơ chế dự phòng kép: Nếu keyring mất hoặc trống, tự khôi phục từ file gemini_keys.json."""
    fake_backup = tmp_path / "gemini_keys.json"
    dummy_keys = [
        {"id": "key_bak_1", "name": "Khóa Dự Phòng File", "key": "AIzaSyBackupKey123", "is_active": True}
    ]
    fake_backup.write_text(json.dumps(dummy_keys, ensure_ascii=False), encoding="utf-8")

    with patch("assistant.llm.gemini_provider._get_keys_backup_path", return_value=fake_backup), \
         patch("keyring.get_password", return_value=None), \
         patch("keyring.set_password") as mock_set:

        keys = get_gemini_api_keys()
        assert len(keys) == 1
        assert keys[0]["id"] == "key_bak_1"
        assert keys[0]["name"] == "Khóa Dự Phòng File"
        # Đã tự động đồng bộ ngược lại vào keyring
        assert mock_set.called
