"""Công cụ truy vấn thông tin hệ thống (System Info Tool).

Cung cấp thông tin:
- Giờ hiện tại hệ thống.
- Dung lượng ổ đĩa trống tại phân vùng chứa workspace.
- Dung lượng RAM tổng và RAM còn trống trên Windows.
"""

import ctypes
import shutil
from typing import Any

from assistant.config import load_config
from assistant.core.prompts import get_current_time_str
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import register_tool


class MEMORYSTATUSEX(ctypes.Structure):
    """Cấu trúc dữ liệu truy vấn bộ nhớ RAM qua Windows API."""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _get_ram_info() -> dict[str, Any]:
    """Lấy thông số RAM qua hàm Win32 GlobalMemoryStatusEx bằng ctypes."""
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_gb = round(stat.ullTotalPhys / (1024**3), 2)
            avail_gb = round(stat.ullAvailPhys / (1024**3), 2)
            used_gb = round(total_gb - avail_gb, 2)
            return {
                "total_gb": total_gb,
                "available_gb": avail_gb,
                "used_gb": used_gb,
                "usage_percent": stat.dwMemoryLoad,
            }
    except Exception:
        pass
    return {"total_gb": "N/A", "available_gb": "N/A", "usage_percent": "N/A"}


@register_tool(
    name="get_system_info",
    description="Lấy thông tin hệ thống máy tính hiện tại: giờ hệ thống, dung lượng ổ đĩa trống và bộ nhớ RAM.",
    permission_level=PermissionLevel.READ,
)
def get_system_info() -> dict[str, Any]:
    """Truy vấn thông số hệ thống Windows."""
    try:
        config = load_config(create_dirs=False)
        time_str = get_current_time_str(config.timezone)

        # 1. Dung lượng ổ đĩa tại phân vùng Workspace
        workspace = config.workspace_dir
        disk = shutil.disk_usage(workspace if workspace.exists() else ".")
        disk_total_gb = round(disk.total / (1024**3), 2)
        disk_free_gb = round(disk.free / (1024**3), 2)
        disk_used_gb = round(disk.used / (1024**3), 2)

        # 2. Thông số RAM
        ram_info = _get_ram_info()

        return {
            "ok": True,
            "data": {
                "current_time": time_str,
                "workspace_disk": {
                    "total_gb": disk_total_gb,
                    "free_gb": disk_free_gb,
                    "used_gb": disk_used_gb,
                },
                "ram": ram_info,
            },
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}
