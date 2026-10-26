"""Bộ công cụ mở file, trang web và khởi chạy ứng dụng Windows (Apps Tools).

Tuân thủ:
- open_url: chỉ chấp nhận giao thức http:// và https://.
- open_app: lập chỉ mục Start Menu và ứng dụng hệ thống, mở bằng os.startfile hoặc subprocess không qua shell.
"""

import os
from pathlib import Path
import re
import subprocess
from typing import Any


from assistant.safety.paths import resolve_in_workspace
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import register_tool

# Danh sách ứng dụng hệ thống thông dụng cài sẵn trên Windows
STANDARD_WINDOWS_APPS: dict[str, str] = {
    "notepad": "notepad.exe",
    "soan thao": "notepad.exe",
    "ghi chu": "notepad.exe",
    "calculator": "calc.exe",
    "may tinh": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "thu muc": "explorer.exe",
    "paint": "mspaint.exe",
    "ve": "mspaint.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "edge": "msedge.exe",
    "trinh duyet": "msedge.exe",
    "cmd": "cmd.exe",
}


def _get_start_menu_shortcuts() -> list[dict[str, str]]:
    """Quét toàn bộ phím tắt (.lnk, .exe) trong Start Menu người dùng và hệ thống."""
    shortcuts: list[dict[str, str]] = []
    scan_dirs: list[Path] = []

    appdata = os.getenv("APPDATA")
    if appdata:
        scan_dirs.append(
            Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        )

    programdata = os.getenv("PROGRAMDATA")
    if programdata:
        scan_dirs.append(
            Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        )

    for base_dir in scan_dirs:
        if base_dir.is_dir():
            try:
                for p in base_dir.rglob("*.lnk"):
                    shortcuts.append({"name": p.stem, "path": str(p)})
            except Exception:
                pass

    return shortcuts


@register_tool(
    name="open_path",
    description="Mở một tập tin hoặc thư mục bằng ứng dụng mặc định của Windows.",
    permission_level=PermissionLevel.READ,
)
def open_path(path: str) -> dict[str, Any]:
    """Mở file/thư mục qua ứng dụng mặc định."""
    try:
        resolved = resolve_in_workspace(path)
        if not resolved.exists():
            return {"ok": False, "data": None, "error": f"Không tìm thấy: {path}", "truncated": False}

        os.startfile(str(resolved))
        return {
            "ok": True,
            "data": f"Đã mở '{resolved.name}' bằng ứng dụng mặc định của Windows.",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="open_url",
    description="Mở một trang web trên trình duyệt mặc định. Chỉ chấp nhận liên kết http:// hoặc https://.",
    permission_level=PermissionLevel.READ,
)
def open_url(url: str) -> dict[str, Any]:
    """Mở liên kết web an toàn."""
    try:
        url_clean = url.strip()
        if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
            return {
                "ok": False,
                "data": None,
                "error": "Chỉ cho phép mở các liên kết web có giao thức http:// hoặc https://",
                "truncated": False,
            }

        os.startfile(url_clean)
        return {
            "ok": True,
            "data": f"Đã mở liên kết web: {url_clean}",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="open_app",
    description="Tìm kiếm và mở phần mềm/ứng dụng trên máy Windows theo tên.",
    permission_level=PermissionLevel.READ,
)
def open_app(app_name: str) -> dict[str, Any]:
    """Khởi động ứng dụng theo tên khớp gần đúng."""
    query = app_name.strip().lower()
    if not query:
        return {"ok": False, "data": None, "error": "Tên ứng dụng không được để trống.", "truncated": False}

    # 1. Kiểm tra khớp chính xác tuyệt đối trong danh bạ ứng dụng chuẩn
    for alias, exe_name in STANDARD_WINDOWS_APPS.items():
        if query == alias:
            try:
                subprocess.Popen([exe_name], shell=False)
                return {
                    "ok": True,
                    "data": f"Đã mở ứng dụng hệ thống: {exe_name}",
                    "error": None,
                    "truncated": False,
                }
            except Exception as err:
                return {"ok": False, "data": None, "error": f"Không thể mở {exe_name}: {err}", "truncated": False}

    # 2. Kiểm tra khớp theo ranh giới từ hoàn chỉnh (tránh "developer" khớp nhầm "ve")
    for alias, exe_name in STANDARD_WINDOWS_APPS.items():
        pattern = r"(?:\b|^)" + re.escape(alias) + r"(?:\b|$)"
        if re.search(pattern, query, re.IGNORECASE):
            try:
                subprocess.Popen([exe_name], shell=False)
                return {
                    "ok": True,
                    "data": f"Đã mở ứng dụng hệ thống: {exe_name}",
                    "error": None,
                    "truncated": False,
                }
            except Exception as err:
                return {"ok": False, "data": None, "error": f"Không thể mở {exe_name}: {err}", "truncated": False}


    # 2. Tìm kiếm trong các shortcut của Start Menu
    shortcuts = _get_start_menu_shortcuts()
    matches: list[dict[str, str]] = []
    for item in shortcuts:
        name_lower = item["name"].lower()
        if query in name_lower:
            matches.append(item)

    if not matches:
        return {
            "ok": False,
            "data": None,
            "error": f"Không tìm thấy ứng dụng nào khớp với tên '{app_name}' trên máy tính.",
            "truncated": False,
        }

    # 3. Nếu tìm thấy nhiều ứng dụng -> yêu cầu chỉ rõ
    if len(matches) > 1:
        names = [m["name"] for m in matches[:5]]
        return {
            "ok": False,
            "data": {"candidates": names},
            "error": f"Tìm thấy nhiều ứng dụng phù hợp ({', '.join(names)}). Vui lòng chỉ định tên cụ thể hơn.",
            "truncated": False,
        }

    # 4. Tìm thấy đúng 1 ứng dụng -> mở bằng os.startfile
    target = matches[0]
    try:
        os.startfile(target["path"])
        return {
            "ok": True,
            "data": f"Đã mở ứng dụng: {target['name']}",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": f"Lỗi khi khởi chạy {target['name']}: {err}", "truncated": False}
