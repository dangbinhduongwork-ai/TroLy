"""Quản lý tự khởi động cùng Windows cho Trợ Lý AI (Autostart Manager).

Nguyên tắc an toàn & bảo mật:
- Sử dụng Registry của người dùng hiện tại: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
- Tuyệt đối KHÔNG yêu cầu quyền Admin (UAC).
- Sử dụng pythonw.exe (nếu có) khi chạy chế độ development để không làm bật cửa sổ console đen khi Windows khởi động.
- Thêm cờ `--minimized` khi khởi động cùng hệ thống để chạy ngầm ở khay hệ thống mà không tự bung cửa sổ chat làm phiền người dùng.
"""

import logging
from pathlib import Path
import sys

logger = logging.getLogger("assistant.desktop.autostart")

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "TroLyAI"


def _get_winreg():
    """Lấy module winreg (hỗ trợ môi trường Windows)."""
    try:
        import winreg
        return winreg
    except ImportError:
        return None


def get_autostart_command(minimized: bool = True) -> str:
    """Tạo chuỗi câu lệnh để ghi vào Registry khởi động cùng Windows."""
    # 1. Nếu là ứng dụng đã đóng gói thành file .exe (PyInstaller/cx_Freeze)
    if getattr(sys, "frozen", False):
        exe_path = sys.executable
        flags = "ui --minimized" if minimized else "ui"
        return f'"{exe_path}" {flags}'

    # 2. Chế độ chạy qua mã nguồn Python:
    # Tìm pythonw.exe cùng thư mục với python.exe để chạy ngầm không hiện console
    python_dir = Path(sys.executable).parent
    pythonw_exe = python_dir / "pythonw.exe"
    exe_to_use = str(pythonw_exe) if pythonw_exe.is_file() else sys.executable

    flags = "ui --minimized" if minimized else "ui"
    return f'"{exe_to_use}" -m assistant {flags}'


def is_autostart_enabled() -> bool:
    """Kiểm tra tính năng tự khởi động cùng Windows có đang được bật hay không."""
    winreg = _get_winreg()
    if not winreg:
        return False

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception as err:
        logger.debug("Lỗi đọc Registry Autostart: %s", err)
        return False


def enable_autostart(minimized: bool = True) -> bool:
    """Bật tính năng tự khởi động cùng Windows cho người dùng hiện tại (HKCU)."""
    winreg = _get_winreg()
    if not winreg:
        logger.warning("Không thể cấu hình Autostart: Hệ thống không hỗ trợ winreg.")
        return False

    command = get_autostart_command(minimized=minimized)
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, command)
            logger.info("Đã bật tự khởi động cùng Windows: %s", command)
            return True
    except Exception as err:
        logger.error("Không thể ghi Registry Autostart: %s", err)
        return False


def disable_autostart() -> bool:
    """Tắt tính năng tự khởi động cùng Windows."""
    winreg = _get_winreg()
    if not winreg:
        return False

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, APP_REG_NAME)
            logger.info("Đã tắt tự khởi động cùng Windows.")
            return True
    except FileNotFoundError:
        # Mục đã không tồn tại -> coi như đã tắt
        return True
    except Exception as err:
        logger.error("Không thể xoá Registry Autostart: %s", err)
        return False


def toggle_autostart(minimized: bool = True) -> bool:
    """Chuyển đổi trạng thái Bật/Tắt tự khởi động cùng Windows."""
    if is_autostart_enabled():
        disable_autostart()
        return False
    else:
        enable_autostart(minimized=minimized)
        return True
