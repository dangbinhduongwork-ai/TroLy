"""Module công cụ thao tác hệ thống (files, apps, commands, web).

Tự động nạp toàn bộ các công cụ đã đăng ký.
"""

from assistant.tools.apps import open_app, open_path, open_url
from assistant.tools.files import (
    append_file,
    delete_path,
    list_dir,
    make_dir,
    move_path,
    read_text_file,
    rename_path,
    search_files,
    write_file,
)
from assistant.tools.memory_tools import forget_memory, recall_memories, remember_fact
from assistant.tools.registry import default_tool_registry, register_tool
from assistant.tools.reminder_tools import (
    cancel_reminder,
    create_reminder,
    list_reminders,
    snooze_reminder,
)
from assistant.tools.shell import run_command
from assistant.tools.system import get_system_info

__all__ = [
    "default_tool_registry",
    "register_tool",
    "list_dir",
    "read_text_file",
    "write_file",
    "append_file",
    "make_dir",
    "move_path",
    "rename_path",
    "search_files",
    "delete_path",
    "open_path",
    "open_url",
    "open_app",
    "run_command",
    "get_system_info",
    "remember_fact",
    "recall_memories",
    "forget_memory",
    "create_reminder",
    "list_reminders",
    "cancel_reminder",
    "snooze_reminder",
]


