"""Trình điều phối lịch nhắc việc và tác vụ định kỳ (Reminder Scheduler).

Nguyên tắc cốt lõi:
- KHÔNG để AI làm đồng hồ. Việc canh giờ và kích hoạt thông báo chạy hoàn toàn bằng code thuần
  qua APScheduler và SQLite, tuyệt đối không gọi LLM khi đến giờ kích hoạt.
- Khi khởi động: quét phát hiện các lời nhắc bị bỏ lỡ (missed) khi tắt máy và cảnh báo ngay cho người dùng.
- Lập lịch cho các lời nhắc một lần (DateTrigger) và lời nhắc lặp lại định kỳ (CronTrigger).
"""

import asyncio
from datetime import datetime
import logging
from typing import Any
import zoneinfo

from assistant.config import Config, load_config
from assistant.reminders.notifier import notify_reminder
from assistant.reminders.store import ReminderStore, get_current_iso_time

logger = logging.getLogger("assistant.reminders.scheduler")

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger

    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False


_global_scheduler: "ReminderScheduler | None" = None


def set_global_scheduler(scheduler: "ReminderScheduler | None") -> None:
    """Lưu tham chiếu bộ lập lịch toàn cục đang hoạt động."""
    global _global_scheduler
    _global_scheduler = scheduler


def get_global_scheduler() -> "ReminderScheduler | None":
    """Lấy tham chiếu bộ lập lịch toàn cục đang hoạt động."""
    return _global_scheduler


def parse_iso_datetime(dt_str: str, timezone_str: str = "Asia/Ho_Chi_Minh") -> datetime:
    """Chuyển đổi chuỗi ISO 8601 sang đối tượng datetime có timezone."""
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            tz = zoneinfo.ZoneInfo(timezone_str)
            dt = dt.replace(tzinfo=tz)
        return dt
    except Exception:
        tz = zoneinfo.ZoneInfo(timezone_str)
        return datetime.now(tz)


class ReminderScheduler:
    """Bộ lập lịch nhắc việc nền tảng APScheduler AsyncIO."""

    def __init__(
        self,
        config: Config | None = None,
        store: ReminderStore | None = None,
    ) -> None:
        self.config = config or load_config(create_dirs=True)
        self.store = store or ReminderStore(self.config.data_dir / "assistant.db")
        self.timezone_str = self.config.timezone
        self.scheduler: Any = None
        self._is_running = False

        if HAS_APSCHEDULER:
            self.scheduler = AsyncIOScheduler(
                timezone=zoneinfo.ZoneInfo(self.timezone_str)
            )

    def check_missed_reminders_on_startup(self) -> list[dict[str, Any]]:
        """Quét và gom các lời nhắc bị quá hạn trong lúc tắt chương trình."""
        now_iso = get_current_iso_time(self.timezone_str)
        missed = self.store.get_missed_reminders(now_iso=now_iso, timezone_str=self.timezone_str)
        if not missed:
            return []

        missed_ids = [m["id"] for m in missed]
        self.store.mark_as_missed(missed_ids)
        logger.info("Đã phát hiện và đánh dấu %d lời nhắc bị bỏ lỡ", len(missed))
        return missed

    def format_missed_reminders_report(self, missed: list[dict[str, Any]]) -> str:
        """Tạo thông báo tiếng Việt báo cáo các lời nhắc bị bỏ lỡ."""
        if not missed:
            return ""

        lines = [f"⚠️ Bạn đã bỏ lỡ {len(missed)} lời nhắc trong lúc tắt chương trình:"]
        for m in missed:
            try:
                dt = parse_iso_datetime(m["trigger_at"], self.timezone_str)
                time_str = dt.strftime("%H:%M ngày %d/%m/%Y")
            except Exception:
                time_str = m["trigger_at"]
            lines.append(f"  - [{time_str}]: {m['message']}")
        return "\n".join(lines)

    async def _on_reminder_triggered(self, reminder_id: str) -> None:
        """Hàm kích hoạt thuần Python khi đến giờ hẹn (TUYỆT ĐỐI KHÔNG GỌI LLM)."""
        rem = self.store.get_reminder(reminder_id)
        if not rem:
            return

        # Nếu người dùng đã huỷ trong khi đang chờ thì không phát
        if rem["status"] == "cancelled":
            return

        message = rem["message"]
        cron_expr = rem.get("cron_expr")

        logger.info("Kích hoạt lời nhắc ID '%s': %s", reminder_id, message)

        # 1. Phát thông báo Windows Toast và Telegram
        try:
            await notify_reminder(
                message=message,
                telegram_chat_id=self.config.telegram_chat_id,
            )
        except Exception as err:
            logger.error("Lỗi khi phát thông báo lời nhắc: %s", err)

        # 2. Cập nhật trạng thái
        if cron_expr:
            # Lời nhắc lặp lại: giữ trạng thái pending để chờ lần kích hoạt tiếp theo
            logger.info("Lời nhắc lặp lại định kỳ (%s), tiếp tục duy trì trạng thái pending", cron_expr)
        else:
            # Lời nhắc một lần: chuyển thành fired
            self.store.update_status(reminder_id, "fired")

    def schedule_reminder(self, rem: dict[str, Any]) -> bool:
        """Đưa một lời nhắc vào hàng đợi lập lịch của APScheduler."""
        if not HAS_APSCHEDULER or not self.scheduler:
            return False

        rem_id = rem["id"]
        cron_expr = rem.get("cron_expr")
        job_id = f"reminder_{rem_id}"

        # Xoá job cũ nếu đã tồn tại trong scheduler
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

        try:
            tz = zoneinfo.ZoneInfo(self.timezone_str)
            if cron_expr:
                # Đặt lịch định kỳ theo CronTrigger
                trigger = CronTrigger.from_crontab(cron_expr, timezone=tz)
                self.scheduler.add_job(
                    self._on_reminder_triggered,
                    trigger=trigger,
                    args=[rem_id],
                    id=job_id,
                    replace_existing=True,
                )
                logger.info("Đã lập lịch định kỳ cron '%s' cho lời nhắc: %s", cron_expr, rem_id)
                return True
            else:
                # Đặt lịch một lần theo DateTrigger
                trigger_dt = parse_iso_datetime(rem["trigger_at"], self.timezone_str)
                now = datetime.now(tz)
                if trigger_dt < now:
                    logger.warning("Thời gian kích hoạt đã ở quá khứ: %s", rem["trigger_at"])
                    return False

                trigger = DateTrigger(run_date=trigger_dt, timezone=tz)
                self.scheduler.add_job(
                    self._on_reminder_triggered,
                    trigger=trigger,
                    args=[rem_id],
                    id=job_id,
                    replace_existing=True,
                )
                logger.info("Đã lập lịch hẹn lúc %s cho lời nhắc: %s", rem["trigger_at"], rem_id)
                return True
        except Exception as err:
            logger.error("Lỗi khi lập lịch lời nhắc ID %s: %s", rem_id, err)
            return False

    def cancel_scheduled_job(self, reminder_id: str) -> None:
        """Gỡ bỏ lời nhắc khỏi scheduler khi bị huỷ hoặc xoá."""
        if self.scheduler:
            job_id = f"reminder_{reminder_id}"
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass

    def start(self) -> str | None:
        """Khởi động bộ lập lịch và nạp toàn bộ lời nhắc pending."""
        # 1. Quét lời nhắc bị bỏ lỡ khi tắt chương trình
        missed = self.check_missed_reminders_on_startup()
        missed_report = self.format_missed_reminders_report(missed) if missed else None

        # 2. Khởi động APScheduler nếu chưa chạy
        if HAS_APSCHEDULER and self.scheduler:
            if not self.scheduler.running:
                self.scheduler.start()
                self._is_running = True

            # 3. Lập lịch cho tất cả lời nhắc đang pending/snoozed trong tương lai
            pending = self.store.get_pending_reminders()
            for p in pending:
                self.schedule_reminder(p)

            logger.info("APScheduler đã nạp %d lời nhắc đang chờ", len(pending))

        return missed_report

    def shutdown(self) -> None:
        """Dừng bộ lập lịch an toàn."""
        if HAS_APSCHEDULER and self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("APScheduler đã dừng hoạt động")
