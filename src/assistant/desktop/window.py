"""Khởi chạy giao diện Desktop trong cửa sổ ứng dụng riêng biệt bằng Microsoft Edge (Desktop Window Launcher).

Nguyên tắc:
- Mở Microsoft Edge ở chế độ cửa sổ ứng dụng riêng biệt không thanh địa chỉ (--app=http://127.0.0.1:<port>/?token=<token>).
- Nếu không tìm thấy Microsoft Edge, tự động fallback sang trình duyệt mặc định của hệ thống.
- Tuyệt đối KHÔNG dùng shell=True (Nguyên tắc 4), luôn truyền danh sách tham số dạng list.
"""

import logging
import os
from pathlib import Path
import shutil
import subprocess
import webbrowser

logger = logging.getLogger("assistant.desktop.window")


def find_edge_executable() -> str | None:
    """Tìm đường dẫn tệp thực thi Microsoft Edge trên Windows."""
    # 1. Thử tìm qua PATH hệ thống
    which_path = shutil.which("msedge")
    if which_path and Path(which_path).is_file():
        return which_path

    # 2. Quét các thư mục cài đặt tiêu chuẩn trên Windows
    candidate_dirs = [
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("LocalAppData", ""),
    ]

    for base_dir in candidate_dirs:
        if not base_dir:
            continue
        edge_path = Path(base_dir) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if edge_path.is_file():
            return str(edge_path)

    return None


def launch_desktop_window(
    port: int,
    session_token: str,
    width: int = 1200,
    height: int = 800,
) -> bool:
    """Mở giao diện Trợ Lý AI trong cửa sổ ứng dụng độc lập."""
    target_url = f"http://127.0.0.1:{port}/?token={session_token}"

    edge_exe = find_edge_executable()
    if edge_exe:
        logger.info("Khởi chạy giao diện qua Microsoft Edge: %s", edge_exe)
        try:
            # Chạy Edge ở chế độ App riêng biệt (không thanh địa chỉ, không bookmark)
            args = [
                edge_exe,
                f"--app={target_url}",
                f"--window-size={width},{height}",
                "--new-window",
            ]
            subprocess.Popen(args)
            return True
        except Exception as err:
            logger.warning("Không thể mở Edge dạng app: %s. Chuyển sang fallback.", err)

    # Fallback: Mở bằng trình duyệt mặc định của hệ thống
    logger.info("Mở giao diện qua trình duyệt mặc định: %s", target_url)
    try:
        webbrowser.open(target_url)
        return True
    except Exception as err:
        logger.error("Lỗi khi mở trình duyệt: %s", err)
        return False


def find_assistant_window() -> int | None:
    """Tìm handle (HWND) của cửa sổ giao diện Trợ Lý AI đang chạy trên Windows."""
    import sys
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found_hwnd: int | None = None

        def enum_proc(hwnd: int, lparam: int) -> bool:
            nonlocal found_hwnd
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                # So khớp các tiêu đề có thể của cửa sổ giao diện
                if (
                    "Trợ Lý AI" in title
                    or "Tro Ly" in title
                    or "AIAssistant" in title
                    or "127.0.0.1:" in title
                ):
                    found_hwnd = hwnd
                    return False  # Dừng quét khi tìm thấy
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
        return found_hwnd
    except Exception as exc:
        logger.debug("Lỗi tìm kiếm cửa sổ Trợ Lý: %s", exc)
        return None


def bring_window_to_front(hwnd: int) -> bool:
    """Kích hoạt và đưa cửa sổ chỉ định lên vị trí trên cùng (Bring to Front)."""
    import sys
    if sys.platform != "win32" or not hwnd:
        return False

    try:
        import ctypes

        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd):
            return False

        # Nếu đang minimize thì khôi phục lại (SW_RESTORE = 9), nếu không thì hiển thị (SW_SHOW = 5)
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        else:
            user32.ShowWindow(hwnd, 5)

        # Gắn thread input để vượt qua cơ chế chặn SetForegroundWindow của Windows
        fore_hwnd = user32.GetForegroundWindow()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
        cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()

        if fore_thread != cur_thread:
            user32.AttachThreadInput(fore_thread, cur_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
            user32.AttachThreadInput(fore_thread, cur_thread, False)
        else:
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        return True
    except Exception as exc:
        logger.debug("Lỗi đưa cửa sổ lên trên cùng: %s", exc)
        return False


def activate_spotlight_mode(port: int, session_token: str) -> bool:
    """Kích hoạt Spotlight Mode: Đưa cửa sổ lên trên cùng hoặc mở mới nếu chưa có."""
    hwnd = find_assistant_window()
    if hwnd:
        logger.info("Tìm thấy cửa sổ Trợ Lý (HWND: %s), đang đưa lên trên cùng...", hwnd)
        return bring_window_to_front(hwnd)

    logger.info("Chưa tìm thấy cửa sổ mở sẵn, đang khởi chạy cửa sổ mới...")
    return launch_desktop_window(port=port, session_token=session_token)
