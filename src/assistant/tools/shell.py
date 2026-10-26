"""Công cụ thực thi lệnh shell an toàn trên Windows (Shell Tool).

Tuân thủ:
- Nguyên tắc 4: Tuyệt đối không dùng `shell=True`. Truyền danh sách tham số.
- Mức quyền CONFIRM: Luôn yêu cầu người dùng duyệt trước khi chạy.
- Chạy bên trong workspace, timeout mặc định 30 giây, không tương tác (stdin=DEVNULL), cắt bớt đầu ra.
"""

import subprocess
from typing import Any

from assistant.config import load_config
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import register_tool


@register_tool(
    name="run_command",
    description="Thực thi một câu lệnh trên terminal PowerShell hoặc CMD trong thư mục workspace. Luôn cần người dùng xác nhận.",
    permission_level=PermissionLevel.CONFIRM,
)
def run_command(command: str, shell_type: str = "powershell") -> dict[str, Any]:
    """Chạy lệnh shell an toàn với timeout và giới hạn dung lượng đầu ra."""
    cmd_clean = command.strip()
    if not cmd_clean:
        return {"ok": False, "data": None, "error": "Câu lệnh không được để trống.", "truncated": False}

    workspace = load_config(create_dirs=False).workspace_dir.resolve()

    # Chuẩn bị danh sách tham số không qua shell
    if shell_type.lower() == "cmd":
        process_args = ["cmd.exe", "/c", cmd_clean]
    else:
        # Mặc định sử dụng PowerShell với cờ không tương tác
        process_args = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            cmd_clean,
        ]

    try:
        result = subprocess.run(
            process_args,
            shell=False,  # Tuân thủ Nguyên tắc 4
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        output = result.stdout or ""
        stderr = result.stderr or ""

        combined = output
        if stderr:
            combined = f"{output}\n[STDERR]: {stderr}".strip()

        truncated = False
        if len(combined) > 4000:
            combined = combined[:3990] + "\n...[ĐẦU RA BỊ CẮT BỚT]"
            truncated = True

        return {
            "ok": result.returncode == 0,
            "data": combined,
            "error": stderr if result.returncode != 0 else None,
            "truncated": truncated,
        }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "data": None,
            "error": "Lệnh chạy quá thời gian chờ tối đa (30 giây) và đã bị hệ thống buộc dừng.",
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": f"Lỗi khi thực thi lệnh: {err}", "truncated": False}
