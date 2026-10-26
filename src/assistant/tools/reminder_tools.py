"""Bộ công cụ đặt lịch nhắc việc và tác vụ định kỳ (Reminder Tools).

Cung cấp:
- create_reminder (CONFIRM): Đặt lịch nhắc mới, AI diễn giải rõ thứ ngày giờ để người dùng xác nhận.
- list_reminders (READ): Xem danh sách lời nhắc đang chờ hoặc đã qua.
- cancel_reminder (WRITE_SAFE): Huỷ một lời nhắc theo ID.
- snooze_reminder (WRITE_SAFE): Hoãn lời nhắc lại N phút.
"""

from datetime import datetime
from typing import Any
import zoneinfo

from assistant.config import load_config
from assistant.core.prompts import WEEKDAY_VI
from assistant.reminders.scheduler import get_global_scheduler, parse_iso_datetime
from assistant.reminders.store import ReminderStore
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import register_tool


def _get_store() -> ReminderStore:
    """Khởi tạo ReminderStore dùng chung."""
    return ReminderStore()


def format_vietnamese_datetime(dt: datetime) -> str:
    """Định dạng thời gian rõ ràng sang tiếng Việt: '15:00 thứ Ba ngày 27/10/2026'."""
    weekday = WEEKDAY_VI[dt.weekday()]
    return f"{dt.strftime('%H:%M')} {weekday} ngày {dt.strftime('%d/%m/%Y')}"


@register_tool(
    name="create_reminder",
    description=(
        "Đặt lịch nhắc việc mới. Cần cung cấp thời gian trigger_at (định dạng ISO 8601 có ngày giờ), "
        "nội dung lời nhắc và biểu thức lặp cron_expr nếu muốn lặp lại định kỳ. "
        "Trước khi lưu, luôn yêu cầu người dùng xác nhận rõ thứ, ngày, giờ."
    ),
    permission_level=PermissionLevel.CONFIRM,
)
def create_reminder(
    trigger_at: str,
    message: str,
    cron_expr: str | None = None,
) -> dict[str, Any]:
    """Tạo mới một lời nhắc việc và lập lịch thông báo."""
    msg_clean = message.strip()
    if not msg_clean:
        return {"ok": False, "data": None, "error": "Nội dung lời nhắc không được để trống.", "truncated": False}

    config = load_config(create_dirs=False)
    tz_str = config.timezone

    # Chuẩn hoá và kiểm tra thời gian kích hoạt
    try:
        dt = parse_iso_datetime(trigger_at.strip(), tz_str)
        trigger_iso = dt.isoformat()
        human_time = format_vietnamese_datetime(dt)
    except Exception as err:
        return {
            "ok": False,
            "data": None,
            "error": f"Định dạng thời gian trigger_at không hợp lệ ('{trigger_at}'). Lỗi: {err}",
            "truncated": False,
        }

    store = _get_store()
    rem_id = store.add_reminder(
        message=msg_clean,
        trigger_at=trigger_iso,
        cron_expr=cron_expr.strip() if cron_expr else None,
    )

    # Đưa vào bộ lập lịch nếu scheduler đang chạy
    scheduler = get_global_scheduler()
    if scheduler:
        new_rem = store.get_reminder(rem_id)
        if new_rem:
            scheduler.schedule_reminder(new_rem)

    cron_info = f" (Lặp lại: {cron_expr})" if cron_expr else ""
    confirmation = f"Đã đặt lịch nhắc vào lúc {human_time}: \"{msg_clean}\"{cron_info} (ID: {rem_id})"

    return {
        "ok": True,
        "data": {
            "reminder_id": rem_id,
            "message": msg_clean,
            "trigger_at": trigger_iso,
            "human_time": human_time,
            "cron_expr": cron_expr,
            "confirmation": confirmation,
        },
        "error": None,
        "truncated": False,
    }


@register_tool(
    name="list_reminders",
    description="Xem danh sách các lời nhắc việc (có thể lọc theo status: pending, fired, snoozed, cancelled, missed).",
    permission_level=PermissionLevel.READ,
)
def list_reminders(
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Liệt kê danh sách lời nhắc từ cơ sở dữ liệu."""
    store = _get_store()
    config = load_config(create_dirs=False)
    tz_str = config.timezone

    items = store.list_reminders(status=status, limit=limit)
    formatted_items = []
    for it in items:
        try:
            dt = parse_iso_datetime(it["trigger_at"], tz_str)
            h_time = format_vietnamese_datetime(dt)
        except Exception:
            h_time = it["trigger_at"]

        formatted_items.append({
            "id": it["id"],
            "message": it["message"],
            "time": h_time,
            "status": it["status"],
            "cron_expr": it.get("cron_expr"),
        })

    return {
        "ok": True,
        "data": {
            "total": len(formatted_items),
            "status_filter": status or "tất cả",
            "reminders": formatted_items,
        },
        "error": None,
        "truncated": False,
    }


@register_tool(
    name="cancel_reminder",
    description="Huỷ bỏ một lời nhắc việc theo ID.",
    permission_level=PermissionLevel.WRITE_SAFE,
)
def cancel_reminder(reminder_id: str) -> dict[str, Any]:
    """Huỷ lời nhắc việc."""
    rem_id_clean = reminder_id.strip()
    if not rem_id_clean:
        return {"ok": False, "data": None, "error": "ID lời nhắc không được để trống.", "truncated": False}

    store = _get_store()
    existing = store.get_reminder(rem_id_clean)
    if not existing:
        return {"ok": False, "data": None, "error": f"Không tìm thấy lời nhắc với ID: {rem_id_clean}", "truncated": False}

    cancelled = store.cancel_reminder(rem_id_clean)
    if cancelled:
        scheduler = get_global_scheduler()
        if scheduler:
            scheduler.cancel_scheduled_job(rem_id_clean)

        return {
            "ok": True,
            "data": f"Đã huỷ lời nhắc ID '{rem_id_clean}': \"{existing['message']}\"",
            "error": None,
            "truncated": False,
        }

    return {"ok": False, "data": None, "error": "Không thể huỷ lời nhắc.", "truncated": False}


@register_tool(
    name="snooze_reminder",
    description="Hoãn lời nhắc lùi lại N phút (mặc định 10 phút).",
    permission_level=PermissionLevel.WRITE_SAFE,
)
def snooze_reminder(reminder_id: str, minutes: int = 10) -> dict[str, Any]:
    """Hoãn lời nhắc việc."""
    rem_id_clean = reminder_id.strip()
    if not rem_id_clean:
        return {"ok": False, "data": None, "error": "ID lời nhắc không được để trống.", "truncated": False}

    if minutes <= 0:
        minutes = 10

    store = _get_store()
    config = load_config(create_dirs=False)
    updated = store.snooze_reminder(rem_id_clean, minutes=minutes, timezone_str=config.timezone)
    if not updated:
        return {"ok": False, "data": None, "error": f"Không tìm thấy lời nhắc với ID: {rem_id_clean}", "truncated": False}

    scheduler = get_global_scheduler()
    if scheduler:
        scheduler.schedule_reminder(updated)

    dt = parse_iso_datetime(updated["trigger_at"], config.timezone)
    h_time = format_vietnamese_datetime(dt)

    return {
        "ok": True,
        "data": f"Đã hoãn lời nhắc thêm {minutes} phút. Sẽ nhắc lại vào lúc {h_time}: \"{updated['message']}\"",
        "error": None,
        "truncated": False,
    }
