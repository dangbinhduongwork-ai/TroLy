"""Bộ công cụ thao tác tập tin và thư mục (Files Tools).

Tất cả các đường dẫn đều được resolve và kiểm tra an toàn qua safety/paths.py.
Mỗi công cụ trả về cấu trúc chuẩn: {"ok": bool, "data": Any, "error": str | None, "truncated": bool}.
"""

from datetime import datetime
from pathlib import Path
import shutil
from typing import Any
import send2trash

from assistant.safety.paths import resolve_in_workspace
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import register_tool


@register_tool(
    name="list_dir",
    description="Liệt kê danh sách tập tin và thư mục con bên trong một thư mục trong workspace.",
    permission_level=PermissionLevel.READ,
)
def list_dir(path: str = ".") -> dict[str, Any]:
    """Liệt kê các mục trong thư mục."""
    try:
        resolved = resolve_in_workspace(path)
        if not resolved.exists():
            return {"ok": False, "data": None, "error": f"Thư mục không tồn tại: {path}", "truncated": False}
        if not resolved.is_dir():
            return {"ok": False, "data": None, "error": f"Đường dẫn không phải thư mục: {path}", "truncated": False}

        entries = []
        for item in sorted(resolved.iterdir()):
            entries.append(
                {
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size_bytes": item.stat().st_size if item.is_file() else None,
                }
            )

        return {"ok": True, "data": entries, "error": None, "truncated": False}
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="read_text_file",
    description="Đọc nội dung văn bản từ một tập tin trong workspace với giới hạn dung lượng và tự nhận mã hoá.",
    permission_level=PermissionLevel.READ,
    is_external_content=True,
)
def read_text_file(path: str, max_bytes: int = 65536) -> dict[str, Any]:
    """Đọc file văn bản với các bảng mã UTF-8, CP1258 (tiếng Việt), UTF-16."""
    try:
        resolved = resolve_in_workspace(path)
        if not resolved.exists():
            return {"ok": False, "data": None, "error": f"Không tìm thấy file: {path}", "truncated": False}
        if not resolved.is_file():
            return {"ok": False, "data": None, "error": f"Đường dẫn không phải tập tin: {path}", "truncated": False}

        raw_bytes = resolved.read_bytes()
        truncated = False
        if len(raw_bytes) > max_bytes:
            raw_bytes = raw_bytes[:max_bytes]
            truncated = True

        # Tự động nhận diện bảng mã
        text: str = ""
        for encoding in ("utf-8", "utf-8-sig", "cp1258", "utf-16", "latin-1"):
            try:
                text = raw_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        return {"ok": True, "data": text, "error": None, "truncated": truncated}
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="write_file",
    description="Tạo mới hoặc ghi nội dung vào một tập tin trong workspace.",
    permission_level=PermissionLevel.WRITE_SAFE,
)
def write_file(path: str, content: str) -> dict[str, Any]:
    """Tạo hoặc ghi nội dung vào file."""
    try:
        resolved = resolve_in_workspace(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "ok": True,
            "data": f"Đã ghi thành công {len(content)} ký tự vào {resolved.name}",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="append_file",
    description="Ghi thêm nội dung vào cuối một tập tin trong workspace.",
    permission_level=PermissionLevel.WRITE_SAFE,
)
def append_file(path: str, content: str) -> dict[str, Any]:
    """Nối thêm dữ liệu vào cuối file."""
    try:
        resolved = resolve_in_workspace(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("a", encoding="utf-8") as f:
            f.write(content)
        return {
            "ok": True,
            "data": f"Đã nối thêm {len(content)} ký tự vào {resolved.name}",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="make_dir",
    description="Tạo một thư mục mới trong workspace.",
    permission_level=PermissionLevel.WRITE_SAFE,
)
def make_dir(path: str) -> dict[str, Any]:
    """Tạo thư mục mới."""
    try:
        resolved = resolve_in_workspace(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "data": f"Đã tạo thư mục: {resolved.name}", "error": None, "truncated": False}
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="move_path",
    description="Di chuyển tập tin hoặc thư mục từ vị trí nguồn sang vị trí đích trong workspace.",
    permission_level=PermissionLevel.CONFIRM,
)
def move_path(src: str, dst: str) -> dict[str, Any]:
    """Di chuyển file/thư mục."""
    try:
        res_src = resolve_in_workspace(src)
        res_dst = resolve_in_workspace(dst)
        if not res_src.exists():
            return {"ok": False, "data": None, "error": f"Nguồn không tồn tại: {src}", "truncated": False}
        res_dst.parent.mkdir(parents=True, exist_ok=True)
        res_src.rename(res_dst)
        return {"ok": True, "data": f"Đã di chuyển {src} tới {dst}", "error": None, "truncated": False}
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="rename_path",
    description="Đổi tên một tập tin hoặc thư mục trong workspace.",
    permission_level=PermissionLevel.CONFIRM,
)
def rename_path(path: str, new_name: str) -> dict[str, Any]:
    """Đổi tên file/thư mục."""
    try:
        resolved = resolve_in_workspace(path)
        if not resolved.exists():
            return {"ok": False, "data": None, "error": f"Không tìm thấy: {path}", "truncated": False}
        target = resolved.parent / new_name
        res_target = resolve_in_workspace(target)
        resolved.rename(res_target)
        return {"ok": True, "data": f"Đã đổi tên thành {new_name}", "error": None, "truncated": False}
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


IGNORE_DIRS: set[str] = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "dist",
    "build",
}


@register_tool(
    name="search_files",
    description="Tìm kiếm tập tin trong workspace theo tên hoặc theo nội dung bên trong file.",
    permission_level=PermissionLevel.READ,
    is_external_content=True,
)
def search_files(query: str, search_content: bool = False, max_results: int = 50) -> dict[str, Any]:
    """Tìm kiếm file theo tên hoặc nội dung."""
    try:
        ws = resolve_in_workspace(".")
        results: list[dict[str, Any]] = []
        query_lower = query.lower()

        for item in ws.rglob("*"):
            if len(results) >= max_results:
                break

            # Bỏ qua các thư mục hệ thống/phát triển nặng khi quét để tránh nghẽn I/O đĩa
            if any(part in IGNORE_DIRS for part in item.parts):
                continue

            if item.is_file():
                # 1. Tìm theo tên
                if query_lower in item.name.lower():
                    rel_path = item.relative_to(ws)
                    results.append({"path": str(rel_path), "match_type": "name"})
                    continue

                # 2. Tìm theo nội dung văn bản nếu được yêu cầu
                if search_content and item.stat().st_size <= 500_000:
                    try:
                        content = item.read_text(encoding="utf-8", errors="ignore")
                        if query_lower in content.lower():
                            rel_path = item.relative_to(ws)
                            results.append({"path": str(rel_path), "match_type": "content"})
                    except Exception:
                        pass

        truncated = len(results) >= max_results
        return {"ok": True, "data": results, "error": None, "truncated": truncated}
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


@register_tool(
    name="delete_path",
    description="Xóa tập tin hoặc thư mục bằng cách đưa vào Thùng rác Windows (Recycle Bin).",
    permission_level=PermissionLevel.CONFIRM,
)
def delete_path(path: str) -> dict[str, Any]:
    """Xóa file an toàn qua send2trash."""
    try:
        resolved = resolve_in_workspace(path)
        if not resolved.exists():
            return {"ok": False, "data": None, "error": f"Không tìm thấy để xoá: {path}", "truncated": False}

        # Dùng send2trash để đưa vào Thùng rác Windows, bảo toàn khả năng phục hồi
        send2trash.send2trash(str(resolved))
        return {
            "ok": True,
            "data": f"Đã chuyển '{resolved.name}' vào Thùng rác Windows an toàn.",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}


EXTENSION_CATEGORIES: dict[str, str] = {
    # Tài liệu
    ".pdf": "Documents",
    ".docx": "Documents",
    ".doc": "Documents",
    ".xlsx": "Documents",
    ".xls": "Documents",
    ".pptx": "Documents",
    ".ppt": "Documents",
    ".txt": "Documents",
    ".csv": "Documents",
    ".md": "Documents",
    # Hình ảnh
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".webp": "Images",
    ".svg": "Images",
    ".bmp": "Images",
    ".ico": "Images",
    # Mã nguồn
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".html": "Code",
    ".css": "Code",
    ".json": "Code",
    ".toml": "Code",
    ".yaml": "Code",
    ".yml": "Code",
    ".bat": "Code",
    ".ps1": "Code",
    # Nén
    ".zip": "Archives",
    ".rar": "Archives",
    ".7z": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    # Media
    ".mp3": "Media",
    ".wav": "Media",
    ".mp4": "Media",
    ".mkv": "Media",
}


@register_tool(
    name="organize_directory",
    description=(
        "Quét và sắp xếp các file trong thư mục theo loại phần mở rộng (by_extension) "
        "hoặc theo tháng chỉnh sửa (by_date). Mặc định execute=False trả về kế hoạch di chuyển; "
        "khi execute=True mới thực hiện di chuyển file (mức CONFIRM)."
    ),
    permission_level=PermissionLevel.CONFIRM,
)
def organize_directory(
    directory_path: str = ".",
    strategy: str = "by_extension",
    execute: bool = False,
) -> dict[str, Any]:
    """Phân loại và sắp xếp các tập tin trong thư mục."""
    try:
        resolved = resolve_in_workspace(directory_path)
        if not resolved.exists() or not resolved.is_dir():
            return {
                "ok": False,
                "data": None,
                "error": f"Thư mục không tồn tại: {directory_path}",
                "truncated": False,
            }

        plan: list[dict[str, str]] = []
        files = [f for f in resolved.iterdir() if f.is_file()]

        for f in files:
            ext = f.suffix.lower()
            if strategy == "by_date":
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                subfolder = mtime.strftime("%Y-%m")
            else:
                subfolder = EXTENSION_CATEGORIES.get(ext, "Others")

            target_folder = resolved / subfolder
            target_file = target_folder / f.name

            plan.append({
                "file_name": f.name,
                "source": str(f.relative_to(resolved)),
                "target_folder": subfolder,
                "target_path": str(target_file.relative_to(resolved)),
            })

        if not execute:
            return {
                "ok": True,
                "data": {
                    "directory": directory_path,
                    "strategy": strategy,
                    "total_files": len(plan),
                    "plan": plan,
                    "summary": (
                        f"Kế hoạch sắp xếp {len(plan)} file trong '{directory_path}' "
                        f"theo chiến lược '{strategy}'. Hãy gọi lại với execute=True để thực thi."
                    ),
                },
                "error": None,
                "truncated": False,
            }

        # Thực thi kế hoạch di chuyển file
        moved_count = 0
        for item in plan:
            src_path = resolved / item["source"]
            dst_folder = resolved / item["target_folder"]
            dst_folder.mkdir(parents=True, exist_ok=True)
            dst_path = resolved / item["target_path"]

            # Tránh ghi đè nếu trùng tên
            if dst_path.exists() and dst_path != src_path:
                stem = dst_path.stem
                suffix = dst_path.suffix
                dst_path = dst_folder / f"{stem}_duplicate_{datetime.now().strftime('%H%M%S')}{suffix}"

            if src_path != dst_path:
                shutil.move(str(src_path), str(dst_path))
                moved_count += 1

        return {
            "ok": True,
            "data": f"Đã sắp xếp thành công {moved_count}/{len(plan)} file trong thư mục '{directory_path}'.",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}

