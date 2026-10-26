"""Quản lý biểu tượng khay hệ thống Windows (System Tray Manager).

Tuân thủ:
- Tự vẽ biểu tượng 64x64 bằng Pillow (PIL) với chấm trạng thái trực tuyến/cục bộ linh hoạt.
- Menu chuột phải 100% bằng tiếng Việt với các tính năng:
  + Mở lại cửa sổ giao diện Microsoft Edge (--app).
  + Đổi chế độ Model (Tự động / Gemini / Ollama).
  + Bật/tắt tự khởi động cùng Windows (dấu tick checked).
  + Mở nhanh thư mục làm việc trong File Explorer.
  + Thoát hoàn toàn ứng dụng và giải phóng tài nguyên.
- Hiển thị Toast thông báo khi ứng dụng chạy ngầm ở khay hệ thống.
"""

from collections.abc import Callable
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any

from assistant.desktop.autostart import is_autostart_enabled, toggle_autostart
from assistant.desktop.single_instance import release_instance
from assistant.desktop.window import launch_desktop_window
from assistant.reminders.notifier import show_windows_toast

logger = logging.getLogger("assistant.desktop.tray")

# Kiểm tra thư viện đồ hoạ và khay hệ thống
try:
    from PIL import Image, ImageDraw
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False


def create_tray_image(is_local_only: bool = False) -> Any:
    """Tự vẽ biểu tượng 64x64 pixel cho khay hệ thống bằng Pillow."""
    if not HAS_PILLOW:
        return None

    # Tạo ảnh RGBA trong suốt
    size = (64, 64)
    img = Image.new("RGBA", size, color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Vẽ nền bo góc màu xanh đen hiện đại (Fluent dark slate)
    bg_color = (26, 32, 44, 255)
    border_color = (59, 130, 246, 255)
    draw.rounded_rectangle([2, 2, 61, 61], radius=14, fill=bg_color, outline=border_color, width=2)

    # 2. Vẽ biểu tượng robot cách điệu ở trung tâm
    # Đầu robot
    draw.rounded_rectangle([16, 16, 47, 44], radius=6, fill=(45, 55, 72, 255), outline=(147, 197, 253, 255), width=2)
    # Ăng-ten
    draw.line([32, 8, 32, 16], fill=(147, 197, 253, 255), width=2)
    draw.ellipse([30, 6, 34, 10], fill=(59, 130, 246, 255))
    # Mắt robot (Cyan)
    eye_color = (56, 189, 248, 255)
    draw.ellipse([21, 24, 27, 30], fill=eye_color)
    draw.ellipse([36, 24, 42, 30], fill=eye_color)
    # Miệng robot
    draw.line([25, 36, 38, 36], fill=(203, 213, 225, 255), width=2)

    # 3. Vẽ chấm tròn trạng thái (Status dot) ở góc dưới bên phải
    # Xanh lá nếu Online Gemini, Vàng nếu Local/Offline
    dot_color = (245, 158, 11, 255) if is_local_only else (16, 185, 129, 255)
    draw.ellipse([46, 46, 58, 58], fill=dot_color, outline=(255, 255, 255, 255), width=1)

    return img


class SystemTrayManager:
    """Quản lý hiển thị và tương tác của biểu tượng khay hệ thống."""

    def __init__(
        self,
        port: int,
        session_token: str,
        workspace_dir: Path,
        data_dir: Path,
        on_exit: Callable[[], None] | None = None,
        on_mode_change: Callable[[str], None] | None = None,
        get_current_mode: Callable[[], str] | None = None,
    ) -> None:
        self.port = port
        self.session_token = session_token
        self.workspace_dir = workspace_dir
        self.data_dir = data_dir
        self.on_exit_callback = on_exit
        self.on_mode_change = on_mode_change
        self.get_current_mode = get_current_mode or (lambda: "auto")

        self.icon: Any = None
        self._thread: threading.Thread | None = None
        self._is_local_only: bool = False
        self._has_shown_minimize_toast: bool = False

    def is_available(self) -> bool:
        """Kiểm tra môi trường có đủ thư viện pystray và Pillow hay không."""
        return HAS_PILLOW and HAS_PYSTRAY

    def _create_menu(self) -> Any:
        """Tạo menu chuột phải với các tùy chọn tiếng Việt."""
        if not HAS_PYSTRAY:
            return None

        def _action_open_window(icon, item):
            launch_desktop_window(self.port, self.session_token)

        def _action_open_workspace(icon, item):
            try:
                if hasattr(os, "startfile"):
                    os.startfile(str(self.workspace_dir))
                else:
                    subprocess.Popen(["explorer.exe", str(self.workspace_dir)])
            except Exception as err:
                logger.error("Không thể mở workspace: %s", err)

        def _action_toggle_autostart(icon, item):
            toggle_autostart(minimized=True)

        def _action_set_mode(mode_name: str):
            def _handler(icon, item):
                if self.on_mode_change:
                    self.on_mode_change(mode_name)
                self.update_status(is_local_only=(mode_name == "local"))
            return _handler

        def _action_exit(icon, item):
            logger.info("Người dùng chọn Thoát hoàn toàn từ khay hệ thống.")
            self.stop()
            release_instance(self.data_dir)
            if self.on_exit_callback:
                try:
                    self.on_exit_callback()
                except Exception:
                    pass
            sys.exit(0)

        # Xây dựng menu con chọn chế độ mô hình
        mode_menu = pystray.Menu(
            pystray.MenuItem(
                "Tự động (Auto)",
                _action_set_mode("auto"),
                checked=lambda item: self.get_current_mode() == "auto",
                radio=True,
            ),
            pystray.MenuItem(
                "Ưu tiên Gemini (Cloud)",
                _action_set_mode("gemini"),
                checked=lambda item: self.get_current_mode() == "gemini",
                radio=True,
            ),
            pystray.MenuItem(
                "Chỉ dùng Cục bộ (Ollama)",
                _action_set_mode("local"),
                checked=lambda item: self.get_current_mode() == "local",
                radio=True,
            ),
        )

        menu = pystray.Menu(
            pystray.MenuItem("💬 Mở cửa sổ Trợ lý", _action_open_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🤖 Chế độ Model", mode_menu),
            pystray.MenuItem(
                "🔄 Khởi động cùng Windows",
                _action_toggle_autostart,
                checked=lambda item: is_autostart_enabled(),
            ),
            pystray.MenuItem("📁 Mở thư mục làm việc (Workspace)", _action_open_workspace),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🚪 Thoát hoàn toàn", _action_exit),
        )
        return menu

    def start(self) -> bool:
        """Khởi động biểu tượng khay hệ thống trên một luồng nền riêng."""
        if not self.is_available():
            logger.warning("Không thể hiển thị Khay hệ thống: thiếu thư viện pystray hoặc Pillow.")
            return False

        image = create_tray_image(is_local_only=self._is_local_only)
        menu = self._create_menu()

        self.icon = pystray.Icon(
            name="TroLyAI",
            icon=image,
            title="Trợ Lý AI - Windows",
            menu=menu,
        )

        self._thread = threading.Thread(target=self.icon.run, daemon=True, name="SystemTrayThread")
        self._thread.start()
        logger.info("Khay hệ thống đã được khởi chạy thành công.")
        return True

    def update_status(self, is_local_only: bool) -> None:
        """Cập nhật lại icon chấm trạng thái (Online/Offline)."""
        self._is_local_only = is_local_only
        if self.icon and self.is_available():
            try:
                new_image = create_tray_image(is_local_only=is_local_only)
                self.icon.icon = new_image
            except Exception as err:
                logger.debug("Lỗi cập nhật icon khay: %s", err)

    def show_minimized_toast_once(self) -> None:
        """Hiện thông báo Toast nhắc nhở Trợ lý vẫn đang chạy ngầm (chỉ hiện 1 lần)."""
        if not self._has_shown_minimize_toast:
            self._has_shown_minimize_toast = True
            show_windows_toast(
                title="Trợ Lý AI",
                message="Trợ lý vẫn đang chạy ngầm ở khay hệ thống để nhắc việc đúng giờ.",
            )

    def stop(self) -> None:
        """Dừng biểu tượng khay hệ thống."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception as err:
                logger.debug("Lỗi dừng icon khay: %s", err)
            self.icon = None
