"""Cấu hình trung tâm cho ứng dụng Trợ Lý AI.

Đọc tham số mặc định từ config/settings.toml và hỗ trợ ghi đè bằng biến môi trường.
Tự động tạo các thư mục cần thiết (workspace_dir, data_dir, data_dir/logs).
"""

from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tomllib
from typing import Any


@dataclass(frozen=True)
class Config:
    """Đối tượng cấu hình bất biến của ứng dụng."""

    workspace_dir: Path
    data_dir: Path
    timezone: str
    gemini_model: str
    local_model: str
    ollama_host: str
    daily_soft_limit: int
    max_context_tokens: int
    network_cache_seconds: int
    ui_port: int
    log_level: str
    telegram_chat_id: str = ""
    embedding_model: str = "nomic-embed-text"


# Bí danh cho Config để tương thích thuận nghịch
AppConfig = Config


def _get_default_data_dir() -> Path:
    """Xác định thư mục dữ liệu mặc định trong %APPDATA%\\AIAssistant."""
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "AIAssistant"
    return Path.home() / "AppData" / "Roaming" / "AIAssistant"


def _load_env_file_if_present(env_path: Path) -> None:
    """Nạp biến môi trường từ file .env đơn giản (không cần thư viện ngoài)."""
    if not env_path.is_file():
        return
    try:
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        # Không làm gián đoạn nếu file .env lỗi định dạng
        pass


def load_config(
    settings_file: Path | None = None,
    create_dirs: bool = True,
) -> Config:
    """Tải cấu hình từ settings.toml kết hợp ghi đè bằng biến môi trường.

    Args:
        settings_file: Đường dẫn file toml (nếu None, mặc định tìm config/settings.toml).
        create_dirs: Tự động tạo thư mục workspace và data nếu chưa có.

    Returns:
        Đối tượng Config chứa toàn bộ tham số đã kiểm tra.
    """
    # Tìm thư mục gốc của dự án hoặc môi trường đóng gói PyInstaller
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        meipass_dir = Path(getattr(sys, "_MEIPASS", exe_dir))
        if (exe_dir / "config" / "settings.toml").is_file():
            root_dir = exe_dir
        elif (meipass_dir / "config" / "settings.toml").is_file():
            root_dir = meipass_dir
        else:
            root_dir = exe_dir
        # Tải biến môi trường từ .env nếu có cạnh exe hoặc trong bundle
        _load_env_file_if_present(exe_dir / ".env")
        if meipass_dir != exe_dir:
            _load_env_file_if_present(meipass_dir / ".env")
    else:
        root_dir = Path(__file__).resolve().parent.parent.parent
        _load_env_file_if_present(root_dir / ".env")

    # Đường dẫn file toml mặc định
    if settings_file is None:
        settings_file = root_dir / "config" / "settings.toml"
        if getattr(sys, "frozen", False) and not settings_file.is_file():
            if (exe_dir / "config" / "settings.toml").is_file():
                settings_file = exe_dir / "config" / "settings.toml"
            elif (meipass_dir / "config" / "settings.toml").is_file():
                settings_file = meipass_dir / "config" / "settings.toml"

    toml_data: dict[str, Any] = {}
    if settings_file.is_file():
        try:
            with settings_file.open("rb") as f:
                toml_data = tomllib.load(f)
        except Exception:
            toml_data = {}

    general_sec = toml_data.get("general", {})
    models_sec = toml_data.get("models", {})
    server_sec = toml_data.get("server", {})
    notifications_sec = toml_data.get("notifications", {})

    # 1. workspace_dir
    ws_raw = os.getenv("WORKSPACE_DIR") or general_sec.get("workspace_dir") or "C:\\AI_Workspace"
    workspace_path = Path(ws_raw).resolve()

    # 2. data_dir
    data_raw = os.getenv("DATA_DIR") or general_sec.get("data_dir")
    if data_raw and str(data_raw).strip():
        data_path = Path(str(data_raw)).resolve()
    else:
        data_path = _get_default_data_dir().resolve()

    # 3. timezone
    timezone = os.getenv("TIMEZONE") or general_sec.get("timezone") or "Asia/Ho_Chi_Minh"

    # 4. models
    gemini_model = (
        os.getenv("GEMINI_MODEL") or models_sec.get("gemini_model") or "gemini-2.5-flash"
    )
    local_model = os.getenv("LOCAL_MODEL") or models_sec.get("local_model") or "qwen2.5:14b"
    ollama_host = (
        os.getenv("OLLAMA_HOST") or models_sec.get("ollama_host") or "http://127.0.0.1:11434"
    )

    try:
        daily_soft_limit = int(
            os.getenv("DAILY_SOFT_LIMIT") or models_sec.get("daily_soft_limit") or 1000
        )
    except (ValueError, TypeError):
        daily_soft_limit = 1000

    try:
        max_context_tokens = int(
            os.getenv("MAX_CONTEXT_TOKENS") or models_sec.get("max_context_tokens") or 4000
        )
    except (ValueError, TypeError):
        max_context_tokens = 4000

    try:
        network_cache_seconds = int(
            os.getenv("NETWORK_CACHE_SECONDS") or models_sec.get("network_cache_seconds") or 10
        )
    except (ValueError, TypeError):
        network_cache_seconds = 10

    # 5. ui_port
    port_raw = os.getenv("UI_PORT") or server_sec.get("ui_port") or 8000
    try:
        ui_port = int(port_raw)
    except (ValueError, TypeError):
        ui_port = 8000

    # 6. log_level
    log_level = (os.getenv("LOG_LEVEL") or general_sec.get("log_level") or "INFO").upper()

    # 7. telegram_chat_id
    telegram_chat_id = str(
        os.getenv("TELEGRAM_CHAT_ID") or notifications_sec.get("telegram_chat_id") or ""
    ).strip()

    # 8. embedding_model
    embedding_model = str(
        os.getenv("EMBEDDING_MODEL")
        or models_sec.get("embedding_model")
        or "nomic-embed-text"
    ).strip()

    config = Config(
        workspace_dir=workspace_path,
        data_dir=data_path,
        timezone=timezone,
        gemini_model=gemini_model,
        local_model=local_model,
        ollama_host=ollama_host,
        daily_soft_limit=daily_soft_limit,
        max_context_tokens=max_context_tokens,
        network_cache_seconds=network_cache_seconds,
        ui_port=ui_port,
        log_level=log_level,
        telegram_chat_id=telegram_chat_id,
        embedding_model=embedding_model,
    )


    if create_dirs:
        try:
            config.workspace_dir.mkdir(parents=True, exist_ok=True)
            config.data_dir.mkdir(parents=True, exist_ok=True)
            (config.data_dir / "logs").mkdir(parents=True, exist_ok=True)
        except Exception as err:
            # Ghi nhận nhưng không crash ứng dụng nếu là môi trường test hạn chế quyền
            print(f"[CẢNH BÁO] Không thể tạo thư mục cấu hình: {err}")

    return config
