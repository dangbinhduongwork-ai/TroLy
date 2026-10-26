"""Kiểm thử tự động cho tính năng Khay hệ thống, Autostart và Single Instance (tests/test_tray_autostart.py).

Kiểm tra:
1. Bật/tắt tự khởi động cùng Windows qua Registry HKCU bằng mock winreg (không can thiệp máy thật).
2. Tự vẽ biểu tượng khay hệ thống (System Tray Icon) 64x64 bằng Pillow.
3. Cơ chế khoá tiến trình duy nhất (Single Instance Lock) và tái kích hoạt cửa sổ.
4. Trình quản lý menu khay hệ thống tiếng Việt (SystemTrayManager).
5. Lệnh chẩn đoán assistant doctor báo cáo chính xác thông tin.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from assistant.desktop.autostart import (
    disable_autostart,
    enable_autostart,
    get_autostart_command,
    is_autostart_enabled,
    toggle_autostart,
)
from assistant.desktop.single_instance import (
    check_or_acquire_instance,
    get_instance_info,
    release_instance,
)
from assistant.desktop.tray import (
    HAS_PILLOW,
    HAS_PYSTRAY,
    SystemTrayManager,
    create_tray_image,
)
from assistant.main import run_doctor


def test_autostart_command_string() -> None:
    """Kiểm tra chuỗi câu lệnh khởi động chứa cờ --minimized."""
    cmd_minimized = get_autostart_command(minimized=True)
    assert "--minimized" in cmd_minimized
    assert "assistant" in cmd_minimized

    cmd_normal = get_autostart_command(minimized=False)
    assert "--minimized" not in cmd_normal
    assert "ui" in cmd_normal


def test_autostart_enable_disable_mock_winreg() -> None:
    """Kiểm tra logic ghi/xoá Registry HKCU thông qua mock winreg."""
    registry_store: dict[str, str] = {}

    mock_winreg = MagicMock()
    mock_winreg.HKEY_CURRENT_USER = "HKCU"
    mock_winreg.KEY_READ = 1
    mock_winreg.KEY_SET_VALUE = 2
    mock_winreg.REG_SZ = 1

    def mock_open_key(root, subkey, reserved, access):
        class MockKeyContext:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return MockKeyContext()

    def mock_set_value_ex(key, name, reserved, reg_type, val):
        registry_store[name] = val

    def mock_query_value_ex(key, name):
        if name in registry_store:
            return registry_store[name], 1
        raise FileNotFoundError("Không tìm thấy key")

    def mock_delete_value(key, name):
        if name in registry_store:
            del registry_store[name]
        else:
            raise FileNotFoundError("Không tìm thấy key")

    mock_winreg.OpenKey = mock_open_key
    mock_winreg.SetValueEx = mock_set_value_ex
    mock_winreg.QueryValueEx = mock_query_value_ex
    mock_winreg.DeleteValue = mock_delete_value

    with patch("assistant.desktop.autostart._get_winreg", return_value=mock_winreg):
        # 1. Ban đầu chưa bật
        assert is_autostart_enabled() is False

        # 2. Bật autostart
        ok = enable_autostart(minimized=True)
        assert ok is True
        assert is_autostart_enabled() is True
        assert "TroLyAI" in registry_store
        assert "--minimized" in registry_store["TroLyAI"]

        # 3. Toggle autostart (đang bật -> chuyển sang tắt)
        new_state = toggle_autostart(minimized=True)
        assert new_state is False
        assert is_autostart_enabled() is False
        assert "TroLyAI" not in registry_store

        # 4. Toggle autostart lại (đang tắt -> chuyển sang bật)
        new_state_2 = toggle_autostart(minimized=True)
        assert new_state_2 is True
        assert is_autostart_enabled() is True

        # 5. Tắt bằng disable_autostart
        ok_dis = disable_autostart()
        assert ok_dis is True
        assert is_autostart_enabled() is False


def test_tray_image_generation() -> None:
    """Kiểm tra hàm create_tray_image tạo ảnh PIL Image 64x64 pixel."""
    if not HAS_PILLOW:
        return

    # Ảnh chế độ Online (Gemini)
    img_online = create_tray_image(is_local_only=False)
    assert img_online is not None
    assert img_online.size == (64, 64)
    assert img_online.mode == "RGBA"

    # Ảnh chế độ Cục bộ (Ollama)
    img_local = create_tray_image(is_local_only=True)
    assert img_local is not None
    assert img_local.size == (64, 64)
    assert img_local.mode == "RGBA"


def test_single_instance_lifecycle(tmp_path: Path) -> None:
    """Kiểm tra vòng đời quản lý Single Instance Lock."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Tiến trình thứ nhất khởi động thành công
    is_primary = check_or_acquire_instance(
        data_dir=data_dir,
        port=8000,
        session_token="test_token_inst_1",
        open_window_if_running=False,
    )
    assert is_primary is True
    info = get_instance_info(data_dir)
    assert info is not None
    assert info["port"] == 8000
    assert info["token"] == "test_token_inst_1"

    # 2. Giả lập tiến trình thứ hai khởi động trong khi server thứ nhất đang sống
    with patch("assistant.desktop.single_instance._is_server_alive", return_value=True), patch("assistant.desktop.single_instance.launch_desktop_window") as mock_launch:
        is_second_primary = check_or_acquire_instance(
            data_dir=data_dir,
            port=8000,
            session_token="token_of_second_process",
            open_window_if_running=True,
        )
        assert is_second_primary is False
        # Đảm bảo đã gọi kích hoạt lại cửa sổ cho tiến trình cũ với token cũ
        mock_launch.assert_called_once_with(port=8000, session_token="test_token_inst_1")

    # 3. Giải phóng instance lock
    release_instance(data_dir)
    assert not (data_dir / "instance.json").exists()


def test_system_tray_manager_menu_and_callbacks(tmp_path: Path) -> None:
    """Kiểm tra khởi tạo SystemTrayManager và các hàm chuyển đổi trạng thái."""
    current_mode_val = "auto"

    def get_mode():
        return current_mode_val

    def set_mode(m):
        nonlocal current_mode_val
        current_mode_val = m

    tray_mgr = SystemTrayManager(
        port=8000,
        session_token="test_token_tray",
        workspace_dir=tmp_path / "ws",
        data_dir=tmp_path / "data",
        on_mode_change=set_mode,
        get_current_mode=get_mode,
    )

    if not tray_mgr.is_available():
        return

    # Tạo menu thành công
    menu = tray_mgr._create_menu()
    assert menu is not None

    # Kiểm tra cập nhật trạng thái online / offline
    tray_mgr.update_status(is_local_only=True)
    assert tray_mgr._is_local_only is True

    tray_mgr.update_status(is_local_only=False)
    assert tray_mgr._is_local_only is False


def test_doctor_command_reports_autostart_and_tray(capsys) -> None:
    """Kiểm tra lệnh assistant doctor in đầy đủ thông tin Autostart, Khay hệ thống và Single Instance."""
    code = run_doctor()
    assert code == 0

    captured = capsys.readouterr().out
    assert "Khởi động cùng Windows" in captured
    assert "Khay hệ thống (Tray)" in captured
    assert "Tiến trình Single Instance" in captured
