"""Kiểm thử tự động cho module cấu hình (config.py) và bảo mật log."""

from pathlib import Path
import pytest

from assistant.config import Config, load_config
from assistant.logging_setup import SecretFilter, setup_logging
from assistant.main import check_gemini_key


def test_default_config_loading(tmp_path: Path) -> None:
    """Kiểm tra đọc cấu hình toml mẫu với các giá trị mặc định."""
    sample_toml = tmp_path / "settings.toml"
    sample_toml.write_text(
        """
[general]
workspace_dir = "C:\\\\CustomWorkspace"
timezone = "Asia/Ho_Chi_Minh"
log_level = "DEBUG"

[models]
gemini_model = "gemini-2.5-flash"
local_model = "qwen2.5:7b"

[server]
ui_port = 8888
""",
        encoding="utf-8",
    )

    config = load_config(settings_file=sample_toml, create_dirs=False)

    assert isinstance(config, Config)
    assert config.timezone == "Asia/Ho_Chi_Minh"
    assert config.gemini_model == "gemini-2.5-flash"
    assert config.local_model == "qwen2.5:7b"
    assert config.ui_port == 8888
    assert config.log_level == "DEBUG"
    assert config.workspace_dir == Path("C:/CustomWorkspace").resolve()


def test_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra biến môi trường ghi đè thành công giá trị toml."""
    sample_toml = tmp_path / "settings.toml"
    sample_toml.write_text(
        """
[general]
workspace_dir = "C:\\\\FromToml"
log_level = "INFO"

[server]
ui_port = 8000
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "OverriddenWorkspace"))
    monkeypatch.setenv("UI_PORT", "9999")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    config = load_config(settings_file=sample_toml, create_dirs=False)

    assert config.ui_port == 9999
    assert config.log_level == "WARNING"
    assert config.workspace_dir == (tmp_path / "OverriddenWorkspace").resolve()


def test_create_directories(tmp_path: Path) -> None:
    """Kiểm tra tính năng tự động tạo thư mục workspace và data_dir."""
    ws = tmp_path / "new_ws"
    data = tmp_path / "new_data"

    sample_toml = tmp_path / "settings.toml"
    sample_toml.write_text(
        f"""
[general]
workspace_dir = "{str(ws).replace(chr(92), '/')}"
data_dir = "{str(data).replace(chr(92), '/')}"
""",
        encoding="utf-8",
    )

    assert not ws.exists()
    assert not data.exists()

    config = load_config(settings_file=sample_toml, create_dirs=True)

    assert config.workspace_dir.exists()
    assert config.data_dir.exists()
    assert (config.data_dir / "logs").exists()


def test_check_gemini_key_zero_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra check_gemini_key không bao giờ in hay trả về chuỗi khóa thực tế."""
    # Khi không có key
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    status_no_key = check_gemini_key()
    assert "Không" in status_no_key

    # Khi có key bí mật
    secret_value = "AIzaSyFakeSecretKeyForTestingPurpose12345"
    monkeypatch.setenv("GEMINI_API_KEY", secret_value)
    status_with_key = check_gemini_key()

    assert "Có" in status_with_key
    # Đảm bảo giá trị thực tế không bị trả về
    assert secret_value not in status_with_key


def test_secret_filter_masks_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra bộ lọc log che giấu các khóa bí mật."""
    fake_key = "AIzaSyFakeSecretKeyForTestingPurpose12345"
    monkeypatch.setenv("GEMINI_API_KEY", fake_key)

    filter_obj = SecretFilter()
    import logging

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"Kết nối tới Gemini bằng key={fake_key}",
        args=(),
        exc_info=None,
    )

    filter_obj.filter(record)
    assert fake_key not in record.msg
    assert "[BÍ_MẬT" in record.msg
