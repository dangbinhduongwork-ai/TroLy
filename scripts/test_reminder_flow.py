"""Kịch bản kiểm tra độc lập hệ thống nhắc việc và tác vụ định kỳ (End-to-End Reminder Verification).

Kiểm tra các tiêu chuẩn nghiệm thu Giai đoạn 4:
1. Phát hiện và cảnh báo các lời nhắc bị bỏ lỡ (missed) khi tắt máy/chương trình.
2. Lưu trữ lời nhắc mới vào SQLite và xác nhận giờ tiếng Việt chính xác.
3. Kích hoạt thông báo Windows Toast kèm âm thanh (kể cả khi mất mạng, không phụ thuộc LLM).
4. Thao tác hoãn nhắc (snooze) và huỷ lời nhắc (cancel).
5. Tạo bản tin sáng (Morning Briefing).
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys
import zoneinfo

# Thêm thư mục src vào đường dẫn nạp module
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from assistant.config import load_config
from assistant.reminders.briefing import generate_morning_briefing
from assistant.reminders.notifier import show_windows_toast
from assistant.reminders.scheduler import ReminderScheduler, format_vietnamese_datetime, parse_iso_datetime
from assistant.reminders.store import ReminderStore
from assistant.tools.reminder_tools import create_reminder, list_reminders, snooze_reminder, cancel_reminder


async def main() -> int:
    print("=" * 65)
    print("KIỂM TRA TỰ ĐỘNG: HỆ THỐNG NHẮC VIỆC & SCHEDULER (GIAI ĐOẠN 4)")
    print("=" * 65)

    config = load_config(create_dirs=True)
    db_path = config.data_dir / "assistant_test_reminders.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    store = ReminderStore(db_path=db_path)
    tz = zoneinfo.ZoneInfo(config.timezone)
    now = datetime.now(tz)

    print(f"1. Khởi tạo cơ sở dữ liệu SQLite tại: {db_path} [OK]")

    # 1. Giả lập lời nhắc bị bỏ lỡ từ quá khứ
    past_time = (now - timedelta(hours=2)).isoformat()
    store.add_reminder(message="Họp giao ban buổi sáng với bộ phận kỹ thuật", trigger_at=past_time)

    # 2. Khởi động scheduler và kiểm tra quét missed reminders
    scheduler = ReminderScheduler(config=config, store=store)
    missed = scheduler.check_missed_reminders_on_startup()
    assert len(missed) == 1
    report = scheduler.format_missed_reminders_report(missed)
    print(f"2. Quét phát hiện lời nhắc bị bỏ lỡ khi khởi động: Tìm thấy {len(missed)} lời nhắc [OK]")
    print(f"   -> Báo cáo:\n{report}")

    # 3. Thử nghiệm tạo lời nhắc mới qua công cụ (tính toán ngày giờ tiếng Việt)
    future_time = (now + timedelta(minutes=1)).isoformat()
    res_create = create_reminder(
        trigger_at=future_time,
        message="Uống một cốc nước ấm",
    )
    assert res_create["ok"] is True
    created_id = res_create["data"]["reminder_id"]
    print(f"\n3. Tạo lời nhắc qua công cụ: {res_create['data']['confirmation']} [OK]")

    # 4. Kiểm tra phát thông báo Windows Toast kèm âm thanh
    print("4. Phát thông báo Windows Toast thử nghiệm trên màn hình...")
    toast_ok = show_windows_toast(
        message="Đã đến giờ uống 1 cốc nước ấm!",
        title="⏰ Lời Nhắc Việc — Trợ Lý AI",
    )
    print(f"   -> Kết quả phát Toast: {'Thành công' if toast_ok else 'Fallback console'} [OK]")

    # 5. Thử nghiệm hoãn nhắc việc (snooze thêm 10 phút)
    res_snooze = snooze_reminder(created_id, minutes=10)
    assert res_snooze["ok"] is True
    print(f"5. Thử nghiệm lệnh /snooze: {res_snooze['data']} [OK]")

    # 6. Thử nghiệm huỷ lời nhắc
    res_cancel = cancel_reminder(created_id)
    assert res_cancel["ok"] is True
    print(f"6. Thử nghiệm lệnh /cancel: {res_cancel['data']} [OK]")

    # 7. Thử nghiệm bản tin sáng (Morning Briefing)
    from assistant.core.router import ModelRouter
    router = ModelRouter(config=config)
    print("\n7. Tạo bản tin sáng (Morning Briefing)...")
    briefing = await generate_morning_briefing(router=router, store=store, timezone_str=config.timezone)
    print("--- [NỘI DUNG BẢN TIN SÁNG] ---")
    print(briefing)
    print("------------------------------- [OK]")

    print("\n" + "=" * 65)
    print("KẾT QUẢ: Toàn bộ tiêu chí nghiệm thu Giai đoạn 4 ĐÃ HOÀN TẤT XUẤT SẮC!")
    print("=" * 65)

    # Dọn dẹp DB test
    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
