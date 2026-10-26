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
4. Tôn trọng quyền riêng tư: dữ liệu cá nhân của người dùng luôn được bảo vệ tối đa.
5. Khi đặt lịch nhắc việc: Bạn không làm đồng hồ canh giờ. Hãy dùng công cụ create_reminder với thời gian ISO 8601 chuẩn xác dựa trên thời gian hệ thống ở trên. Luôn nêu rõ thứ, ngày, tháng, giờ cụ thể khi xác nhận lại với người dùng để tránh hiểu lầm các từ tương đối ("mai", "tuần sau", "chiều nay").
6. Uỷ quyền cho Agent chuyên trách: Với các lệnh đơn giản (như mở phần mềm, tạo file đơn, hỏi đáp), bạn tự thực hiện trực tiếp. Chỉ sử dụng công cụ delegate_to_agent khi tác vụ phức tạp, nhiều bước cần sự chuyên môn hóa:
   - file_organizer_agent: Phân loại, gom nhóm và dọn dẹp thư mục lớn.
   - document_agent: Phân tích, tóm tắt sâu và soạn thảo tài liệu PDF, Word (.docx), Excel (.xlsx).
   - research_agent: Tra cứu web chuyên sâu và tổng hợp thông tin an toàn.
   - coder_agent: Viết script và chạy kiểm thử phần mềm trong workspace."""




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
    memories: list[dict] | None = None,
) -> str:
    """Tạo prompt hệ thống hoàn chỉnh chứa thời gian hiện tại, quy tắc an toàn và trí nhớ dài hạn."""
    from assistant.safety.injection import get_anti_injection_instructions

    time_str = get_current_time_str(timezone_str)
    prompt_parts = [
        BASE_SYSTEM_PROMPT,
        f"\n[THÔNG TIN HỆ THỐNG]\nThời gian hiện tại: {time_str}",
        f"\n{get_anti_injection_instructions()}",
    ]

    # Chèn trí nhớ dài hạn về người dùng nếu có
    if memories:
        mem_lines = ["\n[TRÍ NHỚ DÀI HẠN VỀ NGƯỜI DÙNG]"]
        for m in memories:
            cat = m.get("category", "thông tin")
            content = m.get("content", "").strip()
            if content:
                mem_lines.append(f"- ({cat}): {content}")
        if len(mem_lines) > 1:
            prompt_parts.append("\n".join(mem_lines))

    if custom_instructions and custom_instructions.strip():
        prompt_parts.append(f"\n[CHỈ DẪN BỔ SUNG]\n{custom_instructions.strip()}")

    return "\n".join(prompt_parts)


