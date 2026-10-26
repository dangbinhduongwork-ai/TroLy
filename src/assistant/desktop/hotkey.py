"""Quản lý phím tắt toàn cục Windows (Global Hotkey / Spotlight Mode).

Nguyên tắc & Thiết kế:
- Sử dụng module chuẩn `ctypes` gọi Windows API `RegisterHotKey` và `UnregisterHotKey`.
- Phím tắt mặc định: Ctrl + Shift + Space.
- Khi người dùng bấm phím tắt ở bất cứ đâu trên Windows:
  1. Đưa cửa sổ ứng dụng Trợ Lý lên trên cùng (Bring to Front / SetForegroundWindow).
  2. Tự động đặt con trỏ vào ô nhập liệu chat (Focus input).
- Hỗ trợ bật/tắt động thông qua REST API và màn hình Cài đặt Web UI.
- Tuân thủ Nguyên tắc 11: 100% Python ctypes chuẩn, không cài thêm thư viện bàn phím nặng (như keyboard hay pynput vốn yêu cầu root/hook phức tạp).
"""

import ctypes
from ctypes import wintypes
import logging
import sys
import threading
from typing import Callable

from assistant.desktop.window import activate_spotlight_mode

logger = logging.getLogger(__name__)

# Các hằng số cờ phím bổ trợ Win32 API
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Hằng số thông điệp Windows
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
HOTKEY_ID = 9001
VK_SPACE = 0x20


class GlobalHotkeyManager:
    """Quản lý tiến trình ngầm lắng nghe phím tắt toàn cục trên Windows."""

    def __init__(
        self,
        port: int = 8000,
        session_token: str = "",
        on_trigger: Callable[[], None] | None = None,
    ) -> None:
        self.port = port
        self.session_token = session_token
        self.on_trigger = on_trigger
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._running = False
        self._is_registered = False

    def is_enabled(self) -> bool:
        """Kiểm tra phím tắt toàn cục đang được bật hay không."""
        return self._running

    def set_enabled(self, enabled: bool) -> bool:
        """Bật hoặc tắt phím tắt toàn cục theo yêu cầu."""
        if enabled:
            return self.start()
        else:
            self.stop()
            return True

    def start(self) -> bool:
        """Bắt đầu lắng nghe phím tắt toàn cục trong luồng nền."""
        if sys.platform != "win32":
            logger.info("Phím tắt toàn cục chỉ hỗ trợ trên nền tảng Windows.")
            return False

        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="GlobalHotkeyThread",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Dừng lắng nghe phím tắt toàn cục và giải phóng tài nguyên Win32."""
        if not self._running:
            return

        self._running = False
        if self._thread_id and sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception as exc:
                logger.debug("Lỗi khi gửi WM_QUIT tới luồng hotkey: %s", exc)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        self._thread = None
        self._thread_id = None
        self._is_registered = False

    def _run_loop(self) -> None:
        """Vòng lặp thông điệp Windows (Message Loop) cho luồng phím tắt."""
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._thread_id = kernel32.GetCurrentThreadId()

            # Đăng ký phím tắt: Ctrl + Shift + Space
            modifiers = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
            success = user32.RegisterHotKey(None, HOTKEY_ID, modifiers, VK_SPACE)
            if not success:
                logger.warning(
                    "Không thể đăng ký phím tắt toàn cục (Ctrl+Shift+Space). Có thể bị trùng với ứng dụng khác."
                )
                self._running = False
                return

            self._is_registered = True
            logger.info("Đã đăng ký phím tắt toàn cục Ctrl + Shift + Space thành công.")

            msg = wintypes.MSG()
            while self._running:
                # Chờ thông điệp trong hàng đợi của luồng
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res <= 0:  # WM_QUIT hoặc lỗi
                    break

                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    logger.info("Phím tắt toàn cục (Ctrl+Shift+Space) được kích hoạt!")
                    try:
                        # 1. Kích hoạt cửa sổ Trợ Lý lên trên cùng
                        activate_spotlight_mode(self.port, self.session_token)

                        # 2. Phát tín hiệu WebSocket để giao diện tự động đặt con trỏ vào ô chat
                        try:
                            from assistant.server.ws import notify_focus_input
                            notify_focus_input()
                        except Exception:
                            pass

                        # 3. Gọi callback bổ trợ tuỳ chỉnh nếu có
                        if self.on_trigger:
                            self.on_trigger()
                    except Exception as exc:
                        logger.error("Lỗi khi xử lý Spotlight Mode: %s", exc)

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        except Exception as exc:
            logger.error("Lỗi trong vòng lặp thông điệp phím tắt: %s", exc)
        finally:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            except Exception:
                pass
            self._is_registered = False
            self._running = False
            logger.info("Đã hủy đăng ký phím tắt toàn cục.")


_hotkey_instance: GlobalHotkeyManager | None = None


def get_hotkey_manager(port: int = 8000, session_token: str = "") -> GlobalHotkeyManager:
    """Lấy hoặc khởi tạo đối tượng GlobalHotkeyManager duy nhất (Singleton)."""
    global _hotkey_instance
    if _hotkey_instance is None:
        _hotkey_instance = GlobalHotkeyManager(port=port, session_token=session_token)
    else:
        if port != 8000:
            _hotkey_instance.port = port
        if session_token:
            _hotkey_instance.session_token = session_token
    return _hotkey_instance
