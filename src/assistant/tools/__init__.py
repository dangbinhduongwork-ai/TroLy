"""Module công cụ thao tác hệ thống (files, apps, commands, web).

Tự động nạp toàn bộ các công cụ đã đăng ký.
"""

from assistant.tools.apps import open_app, open_path, open_url
from assistant.tools.docs import (
    create_docx,
    create_excel,
    read_docx,
    read_excel,
    read_pdf,
)
from assistant.tools.files import (
    append_file,
    delete_path,
    list_dir,
    make_dir,
    move_path,
    organize_directory,
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
from assistant.tools.web import fetch_webpage


def __getattr__(name: str):
    """Nạp trễ delegate_to_agent khi được truy cập để ngăn chặn triệt để circular import."""
    if name == "delegate_to_agent":
        from assistant.agents.orchestrator import delegate_to_agent
        return delegate_to_agent
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


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
    "organize_directory",
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
    "read_pdf",
    "read_docx",
    "read_excel",
    "create_docx",
    "create_excel",
    "fetch_webpage",
    "delegate_to_agent",
]



