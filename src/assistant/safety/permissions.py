"""Hệ thống phân quyền 3 cấp độ và danh sách từ chối cứng (Hard DENY) cho các lệnh nguy hiểm.

Tuân thủ nghiêm ngặt Nguyên tắc 2 (An toàn trước tiên):
- Mọi thao tác phá huỷ, ghi đè, chạy lệnh phải được kiểm soát chặt chẽ.
- Lệnh độc hại trong danh sách từ chối cứng (DENY) tuyệt đối không được phép duyệt.
"""

from enum import Enum
import re
from typing import Any


class PermissionLevel(str, Enum):
    """Mức quyền khai báo của công cụ."""

    READ = "READ"              # Thao tác đọc an toàn -> Tự động cho phép (ALLOW)
    WRITE_SAFE = "WRITE_SAFE"  # Tạo mới bên trong workspace -> Tự động cho phép (ALLOW)
    CONFIRM = "CONFIRM"        # Xóa, ghi đè, ra ngoài workspace, chạy lệnh -> Cần duyệt (NEEDS_APPROVAL)


class PermissionDecision(str, Enum):
    """Kết quả đánh giá quyền của hệ thống bảo vệ."""

    ALLOW = "ALLOW"                      # Cho phép thực thi ngay
    NEEDS_APPROVAL = "NEEDS_APPROVAL"    # Yêu cầu người dùng phê duyệt trong terminal
    DENY = "DENY"                        # Từ chối cứng, tuyệt đối không cho phép duyệt


# Danh sách biểu thức chính quy (Regex) các lệnh nguy hiểm bị từ chối cứng (Hard DENY)
DANGEROUS_COMMAND_PATTERNS = [
    # 1. Định dạng hoặc can thiệp phân vùng ổ đĩa
    (re.compile(r"\bformat\b(\s+[a-zA-Z]:|\s+/)", re.IGNORECASE), "Lệnh định dạng ổ đĩa (format) bị cấm hoàn toàn."),
    (re.compile(r"\bdiskpart\b", re.IGNORECASE), "Lệnh can thiệp phân vùng ổ cứng (diskpart) bị cấm."),
    
    # 2. Xóa đệ quy toàn bộ thư mục hoặc ổ đĩa
    (re.compile(r"\bdel\b\s+.*(/s|/f)", re.IGNORECASE), "Lệnh xóa toàn bộ tập tin đệ quy (del /s /f) bị cấm."),
    (re.compile(r"\b(rmdir|rd)\b\s+.*(/s|/q)", re.IGNORECASE), "Lệnh xóa thư mục đệ quy hàng loạt (rmdir /s) bị cấm."),
    (re.compile(r"\bRemove-Item\b\s+.*-Recurse\s+.*-Force", re.IGNORECASE), "Lệnh PowerShell Remove-Item -Recurse -Force bị cấm."),
    
    # 3. Can thiệp Registry và Boot hệ thống
    (re.compile(r"\breg\b\s+delete\b", re.IGNORECASE), "Lệnh xóa Registry hệ thống (reg delete) bị cấm."),
    (re.compile(r"\bbcdedit\b", re.IGNORECASE), "Lệnh can thiệp cấu hình khởi động Windows (bcdedit) bị cấm."),
    (re.compile(r"\bcipher\b\s+/w", re.IGNORECASE), "Lệnh ghi đè dữ liệu ổ cứng vĩnh viễn (cipher /w) bị cấm."),
    
    # 4. Can thiệp người dùng và mật khẩu hệ thống
    (re.compile(r"\bnet\b\s+(user|localgroup)\b", re.IGNORECASE), "Lệnh quản trị tài khoản người dùng hệ thống (net user) bị cấm."),
    
    # 5. PowerShell thực thi mã bị làm rối hoặc mã hóa
    (re.compile(r"powershell.*(-e|-encodedcommand)\b", re.IGNORECASE), "Lệnh PowerShell chạy mã hóa -EncodedCommand bị cấm."),
    
    # 6. Tải mã từ web rồi thực thi trực tiếp (Code Injection / RCE)
    (re.compile(r"(curl|wget|irm|Invoke-WebRequest)\s+.*\|\s*(bash|sh|cmd|powershell|iex|Invoke-Expression)", re.IGNORECASE), "Hành vi tải mã từ Internet rồi thực thi trực tiếp bị cấm triệt để."),
    (re.compile(r"DownloadString\(.*\|\s*(iex|Invoke-Expression)", re.IGNORECASE), "Hành vi DownloadString rồi thực thi qua iex bị cấm triệt để."),
    
    # 7. Tắt máy hoặc khởi động lại đột ngột
    (re.compile(r"\bshutdown\b\s+/(s|r|p)", re.IGNORECASE), "Lệnh tắt máy hoặc khởi động lại đột ngột (shutdown) bị cấm."),
]


def check_hard_deny(command: str) -> str | None:
    """Kiểm tra xem lệnh shell có nằm trong danh sách từ chối cứng (Hard DENY) hay không.

    Returns:
        Lý do từ chối nếu lệnh nguy hiểm, None nếu vượt qua kiểm tra từ chối cứng.
    """
    cmd_clean = command.strip()
    for pattern, reason in DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(cmd_clean):
            return reason
    return None


def evaluate_permission(
    tool_name: str,
    declared_level: PermissionLevel,
    args: dict[str, Any],
    file_exists_callback: Any = None,
) -> tuple[PermissionDecision, str]:
    """Đánh giá quyết định phân quyền cho một lần gọi công cụ.

    Args:
        tool_name: Tên của công cụ.
        declared_level: Mức quyền khai báo của công cụ (READ, WRITE_SAFE, CONFIRM).
        args: Tham số truyền vào công cụ.
        file_exists_callback: Hàm callback tuỳ chọn kiểm tra file đích đã tồn tại hay chưa.

    Returns:
        Tuple gồm (PermissionDecision, lý do).
    """
    # 1. Kiểm tra đối với công cụ chạy lệnh run_command
    if tool_name == "run_command":
        cmd = str(args.get("command", "")).strip()
        deny_reason = check_hard_deny(cmd)
        if deny_reason:
            return PermissionDecision.DENY, f"[TỪ CHỐI CỨNG] {deny_reason}"
        return (
            PermissionDecision.NEEDS_APPROVAL,
            f"Thực thi lệnh shell: '{cmd}' cần người dùng phê duyệt trước khi chạy.",
        )

    # 2. Xử lý mức READ
    if declared_level == PermissionLevel.READ:
        return PermissionDecision.ALLOW, "Thao tác đọc được tự động cho phép."

    # 3. Xử lý mức WRITE_SAFE
    if declared_level == PermissionLevel.WRITE_SAFE:
        # Nếu ghi đè lên file đã tồn tại sẵn -> nâng lên mức CONFIRM (cần duyệt)
        if file_exists_callback and file_exists_callback(args.get("path", "")):
            return (
                PermissionDecision.NEEDS_APPROVAL,
                f"Tập tin '{args.get('path')}' đã tồn tại từ trước. Việc ghi đè cần người dùng xác nhận.",
            )
        return PermissionDecision.ALLOW, "Tạo mới an toàn trong workspace được tự động cho phép."

    # 4. Xử lý mức CONFIRM
    if declared_level == PermissionLevel.CONFIRM:
        return (
            PermissionDecision.NEEDS_APPROVAL,
            f"Thao tác '{tool_name}' có tính chất phá huỷ, xoá bỏ hoặc thay đổi trạng thái cần được duyệt.",
        )

    return PermissionDecision.DENY, "Không xác định được mức quyền hợp lệ."
