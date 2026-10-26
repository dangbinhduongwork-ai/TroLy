"""Quản lý các system prompt chuẩn tiếng Việt cho Trợ Lý AI.

Tuân thủ yêu cầu: Luôn tự động chèn ngày giờ thực tế và múi giờ hệ thống vào mỗi lượt gọi model.
"""

from datetime import datetime
import zoneinfo

WEEKDAY_VI = [
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ Nhật",
]

BASE_SYSTEM_PROMPT = """Bạn là "Trợ lý", một trợ lý trí tuệ nhân tạo (AI Assistant) chuyên nghiệp chạy trực tiếp trên máy tính Windows của người dùng.

Nhiệm vụ của bạn:
1. Giao tiếp hoàn toàn bằng tiếng Việt tự nhiên, lịch sự, ngắn gọn và rõ ràng.
2. Hỗ trợ người dùng thực hiện các công việc trên máy: thao tác file, mở phần mềm/thư mục/trang web, chạy lệnh an toàn, ghi nhớ thông tin và nhắc việc.
3. Khi xử lý các tác vụ có tính phá hủy (xóa, ghi đè, chạy lệnh hệ thống), bạn luôn phải yêu cầu người dùng xác nhận và giải thích rõ hành động sắp làm.
4. Tôn trọng quyền riêng tư: dữ liệu cá nhân của người dùng luôn được bảo vệ tối đa."""


def get_current_time_str(timezone_str: str = "Asia/Ho_Chi_Minh") -> str:
    """Tạo chuỗi thời gian định dạng tiếng Việt kèm múi giờ."""
    try:
        tz = zoneinfo.ZoneInfo(timezone_str)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()

    weekday = WEEKDAY_VI[now.weekday()]
    date_part = now.strftime("%d/%m/%Y")
    time_part = now.strftime("%H:%M:%S")

    return f"{weekday}, ngày {date_part}, lúc {time_part} (Múi giờ: {timezone_str})"


def get_system_prompt(
    custom_instructions: str | None = None,
    timezone_str: str = "Asia/Ho_Chi_Minh",
) -> str:
    """Tạo prompt hệ thống hoàn chỉnh chứa thông tin thời gian hiện tại."""
    time_str = get_current_time_str(timezone_str)
    prompt_parts = [
        BASE_SYSTEM_PROMPT,
        f"\n[THÔNG TIN HỆ THỐNG]\nThời gian hiện tại: {time_str}",
    ]

    if custom_instructions and custom_instructions.strip():
        prompt_parts.append(f"\n[CHỈ DẪN BỔ SUNG]\n{custom_instructions.strip()}")

    return "\n".join(prompt_parts)
