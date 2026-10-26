"""Kiểm soát an toàn đường dẫn tập tin và thư mục trên Windows.

Tuân thủ nghiêm ngặt Nguyên tắc 5:
- Dùng `pathlib.Path`, resolve đường dẫn tuyệt đối.
- Xử lý và chặn đứng triệt để:
  1. Kỹ thuật vượt rào đường dẫn ("..", "../").
  2. Thoát khỏi workspace qua Symlink và Directory Junction.
  3. Tên thiết bị đặc biệt của Windows (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
  4. Đường dẫn mạng chia sẻ UNC (\\\\server\\share).
  5. Luồng dữ liệu thay thế NTFS (Alternate Data Streams ':').
"""

from pathlib import Path
import re

from assistant.config import load_config

# Danh sách tên thiết bị dành riêng của Windows (không phân biệt hoa thường)
RESERVED_DEVICE_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)


class PathSecurityError(PermissionError):
    """Ngoại lệ khi đường dẫn vi phạm chính sách an toàn hoặc thoát khỏi workspace."""

    pass


def _check_reserved_names_and_ads(path_str: str) -> None:
    """Kiểm tra đường dẫn không chứa tên thiết bị cấm hoặc luồng dữ liệu thay thế (ADS)."""
    # 1. Chặn đường dẫn mạng UNC (bắt đầu bằng \\ hoặc //)
    if path_str.startswith(("\\\\", "//")):
        raise PathSecurityError("Đường dẫn mạng UNC (\\\\server\\share) bị cấm vì lý do an toàn mạng.")

    # 2. Chặn tiền tố thiết bị hệ thống NT (\\?\, \??\)
    if path_str.startswith(("\\\\?\\", "\\??\\", "//?/")):
        raise PathSecurityError("Đường dẫn chứa tiền tố thiết bị hệ thống NT bị cấm.")

    # 3. Chặn luồng dữ liệu thay thế ADS (dấu hai chấm sau ký tự ổ đĩa)
    # Loại bỏ ổ đĩa chuẩn ví dụ "C:\" hoặc "D:/" trước khi kiểm tra
    stripped_drive = re.sub(r"^[a-zA-Z]:", "", path_str)
    if ":" in stripped_drive:
        raise PathSecurityError(
            f"Đường dẫn '{path_str}' chứa ký tự ':' (Alternate Data Streams) bị cấm."
        )

    # 4. Chặn các ký tự điều khiển và ký tự cấm trong tên file Windows (< > " | ? *)
    invalid_chars = set('<>"|?*')
    for ch in invalid_chars:
        if ch in stripped_drive:
            raise PathSecurityError(f"Đường dẫn chứa ký tự cấm của Windows: '{ch}'")

    # 5. Chặn tên thiết bị đặc biệt của Windows
    normalized = path_str.replace("/", "\\")
    segments = [s for s in normalized.split("\\") if s]
    for seg in segments:
        # Tách phần mở rộng (ví dụ "con.txt" -> "CON", "NUL.dat" -> "NUL")
        base_name = seg.split(".")[0].strip().upper()
        if base_name in RESERVED_DEVICE_NAMES:
            raise PathSecurityError(
                f"Tên tập tin/thư mục '{seg}' là thiết bị hệ thống đặc biệt của Windows, bị cấm truy cập."
            )


def resolve_in_workspace(
    path: str | Path,
    workspace_dir: Path | None = None,
) -> Path:
    """Resolve đường dẫn an toàn bên trong thư mục workspace.

    Args:
        path: Đường dẫn tương đối hoặc tuyệt đối cần kiểm tra.
        workspace_dir: Thư mục gốc an toàn (nếu None, mặc định đọc từ config).

    Returns:
        Đối tượng Path đã resolve tuyệt đối và được xác nhận nằm trong workspace.

    Raises:
        PathSecurityError: Nếu đường dẫn vi phạm an toàn hoặc thoát khỏi workspace.
    """
    path_str = str(path).strip()
    if not path_str:
        raise PathSecurityError("Đường dẫn không được để trống.")

    # Kiểm tra chuỗi thô trước khi resolve
    _check_reserved_names_and_ads(path_str)

    if workspace_dir is None:
        workspace_dir = load_config(create_dirs=False).workspace_dir

    resolved_workspace = workspace_dir.resolve()

    target_path = Path(path_str)

    # Nếu truyền vào đường dẫn tương đối, ghép với workspace
    if not target_path.is_absolute():
        target_path = resolved_workspace / target_path

    # Resolve triệt để: xử lý toàn bộ "..", symlink và junction trỏ ra ngoài
    try:
        resolved_target = target_path.resolve()
    except Exception as err:
        raise PathSecurityError(f"Không thể resolve đường dẫn '{path_str}': {err}") from err

    # Kiểm tra lại tên các thành phần của đường dẫn sau khi đã resolve
    _check_reserved_names_and_ads(str(resolved_target))

    # Kiểm tra ranh giới workspace
    try:
        if not resolved_target.is_relative_to(resolved_workspace):
            raise PathSecurityError(
                f"Đường dẫn '{path_str}' đã vượt ra ngoài phạm vi thư mục làm việc cho phép! "
                f"(Mục tiêu: {resolved_target} | Workspace: {resolved_workspace})"
            )
    except ValueError as err:
        # Xảy ra khi khác ổ đĩa trên Windows (ví dụ C:\ và D:\)
        raise PathSecurityError(
            f"Đường dẫn '{path_str}' nằm trên ổ đĩa khác so với workspace! "
            f"(Mục tiêu: {resolved_target} | Workspace: {resolved_workspace})"
        ) from err

    return resolved_target


def is_safe_workspace_path(
    path: str | Path,
    workspace_dir: Path | None = None,
) -> bool:
    """Kiểm tra đường dẫn có hợp lệ trong workspace hay không mà không ném ngoại lệ."""
    try:
        resolve_in_workspace(path, workspace_dir)
        return True
    except (PathSecurityError, Exception):
        return False
