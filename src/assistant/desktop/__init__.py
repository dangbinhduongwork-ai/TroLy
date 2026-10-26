"""Module desktop window, khay hệ thống (System Tray) và tích hợp hệ thống Windows."""

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
from assistant.desktop.hotkey import GlobalHotkeyManager, get_hotkey_manager
from assistant.desktop.tray import SystemTrayManager, create_tray_image
from assistant.desktop.window import (
    activate_spotlight_mode,
    bring_window_to_front,
    find_assistant_window,
    find_edge_executable,
    launch_desktop_window,
)

__all__ = [
    "find_edge_executable",
    "launch_desktop_window",
    "find_assistant_window",
    "bring_window_to_front",
    "activate_spotlight_mode",
    "create_tray_image",
    "SystemTrayManager",
    "is_autostart_enabled",
    "enable_autostart",
    "disable_autostart",
    "toggle_autostart",
    "get_autostart_command",
    "check_or_acquire_instance",
    "get_instance_info",
    "release_instance",
    "GlobalHotkeyManager",
    "get_hotkey_manager",
]
