"""Bản tin buổi sáng tóm tắt công việc và lời nhắc trong ngày (Morning Briefing).

Tính năng:
- Tự động lấy danh sách lời nhắc việc trong ngày hôm nay từ SQLite.
- Gọi mô hình qua ModelRouter để tổng hợp bản tin chào buổi sáng truyền cảm hứng, súc tích.
- Tự động dự phòng bản tin định dạng sẵn nếu mất mạng hoặc mô hình gặp sự cố.
"""

from datetime import datetime
import zoneinfo

from assistant.core.prompts import get_current_time_str
from assistant.core.router import ModelRouter
from assistant.llm.base import Message
from assistant.reminders.store import ReminderStore


async def generate_morning_briefing(
    router: ModelRouter,
    store: ReminderStore,
    timezone_str: str = "Asia/Ho_Chi_Minh",
) -> str:
    """Tạo bản tin tổng hợp buổi sáng cho người dùng."""
    try:
        tz = zoneinfo.ZoneInfo(timezone_str)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()

    today_prefix = now.strftime("%Y-%m-%d")
    all_reminders = store.list_reminders(limit=100)

    # Lọc các lời nhắc thuộc ngày hôm nay
    today_reminders = [
        r for r in all_reminders
        if r["trigger_at"].startswith(today_prefix) and r["status"] in ("pending", "snoozed", "fired")
    ]

    time_header = get_current_time_str(timezone_str)

    if not today_reminders:
        reminder_summary = "Hôm nay bạn không có lịch hẹn hoặc lời nhắc nào đã lên lịch trước."
    else:
        rem_lines = []
        for r in today_reminders:
            try:
                dt = datetime.fromisoformat(r["trigger_at"])
                h_str = dt.strftime("%H:%M")
            except Exception:
                h_str = r["trigger_at"]
            status_text = " (Đã nhắc)" if r["status"] == "fired" else ""
            rem_lines.append(f"- [{h_str}] {r['message']}{status_text}")
        reminder_summary = "Các lời nhắc đã lên lịch trong ngày hôm nay:\n" + "\n".join(rem_lines)

    prompt_content = (
        f"Hôm nay là: {time_header}\n\n"
        f"Dữ liệu lịch nhắc việc:\n{reminder_summary}\n\n"
        "Hãy viết một Bản tin buổi sáng (Morning Briefing) ngắn gọn, lịch sự, truyền năng lượng tích cực "
        "bằng tiếng Việt. Tóm tắt rõ ràng các mốc thời gian cần lưu ý trong ngày."
    )

    chunks: list[str] = []
    try:
        async for event in router.stream_chat(
            messages=[Message(role="user", content=prompt_content)],
            system="Bạn là trợ lý cá nhân chuyên nghiệp, hỗ trợ khởi đầu ngày mới hiệu quả.",
        ):
            if event.type == "text_delta" and isinstance(event.content, str):
                chunks.append(event.content)
        result = "".join(chunks).strip()
        if result:
            return result
    except Exception:
        pass

    # Bản tin dự phòng nếu không gọi được model
    fallback_lines = [
        "☀️ [BẢN TIN BUỔI SÁNG — TRỢ LÝ AI]",
        f"Thời gian: {time_header}",
        "Chúc bạn một ngày làm việc thuận lợi và nhiều năng lượng!",
        "",
        reminder_summary,
    ]
    return "\n".join(fallback_lines)
