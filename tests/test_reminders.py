"""Kiểm thử tự động cho hệ thống nhắc việc và tác vụ định kỳ (Giai đoạn 4).

Kiểm tra:
- ReminderStore: CRUD, trạng thái, hoãn nhắc (snooze), phát hiện bỏ lỡ (missed).
- ReminderScheduler: Quét missed reminders khi khởi động, chạy kích hoạt thuần Python không gọi LLM.
- ReminderTools: Cấp quyền (create_reminder=CONFIRM, list=READ, cancel/snooze=WRITE_SAFE), định dạng giờ tiếng Việt.
- Morning Briefing: Tổng hợp bản tin sáng tóm tắt công việc trong ngày.
"""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
import pytest
import zoneinfo

from assistant.core.router import ModelRouter
from assistant.llm.base import LLMProvider, Message, StreamEvent
from assistant.reminders.briefing import generate_morning_briefing
from assistant.reminders.notifier import show_windows_toast
from assistant.reminders.scheduler import ReminderScheduler, parse_iso_datetime
from assistant.reminders.store import ReminderStore
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import default_tool_registry
from assistant.tools.reminder_tools import (
    cancel_reminder,
    create_reminder,
    format_vietnamese_datetime,
    list_reminders,
    snooze_reminder,
)


class MockBriefingProvider(LLMProvider):
    """Provider giả lập dùng để test sinh bản tin sáng."""

    def __init__(self, output: str) -> None:
        self.output = output
        self.default_model = "mock-briefing"

    @property
    def provider_name(self) -> str:
        return "mock"

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(type="text_delta", content=self.output)

    async def list_models(self) -> list[str]:
        return ["mock-briefing"]


def test_reminder_store_crud(tmp_path: Path) -> None:
    """Kiểm tra tạo, đọc, cập nhật trạng thái và xoá lời nhắc."""
    store = ReminderStore(db_path=tmp_path / "rem_test.db")

    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    future_time = (datetime.now(tz) + timedelta(hours=2)).isoformat()

    # 1. Thêm lời nhắc
    rid = store.add_reminder(
        message="Họp tổng kết dự án với khách hàng",
        trigger_at=future_time,
    )
    assert rid is not None

    # 2. Lấy chi tiết
    rem = store.get_reminder(rid)
    assert rem is not None
    assert rem["message"] == "Họp tổng kết dự án với khách hàng"
    assert rem["status"] == "pending"

    # 3. Cập nhật trạng thái
    ok = store.update_status(rid, "fired")
    assert ok is True
    assert store.get_reminder(rid)["status"] == "fired"

    # 4. Huỷ lời nhắc
    ok_cancel = store.cancel_reminder(rid)
    assert ok_cancel is True
    assert store.get_reminder(rid)["status"] == "cancelled"

    # 5. Xoá lời nhắc
    ok_del = store.delete_reminder(rid)
    assert ok_del is True
    assert store.get_reminder(rid) is None


def test_reminder_store_snooze(tmp_path: Path) -> None:
    """Kiểm tra tính năng hoãn nhắc việc (snooze N phút)."""
    store = ReminderStore(db_path=tmp_path / "snooze_test.db")

    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.now(tz)
    orig_time = (now + timedelta(minutes=5)).isoformat()

    rid = store.add_reminder("Uống nước định kỳ", trigger_at=orig_time)

    # Hoãn 15 phút
    snoozed = store.snooze_reminder(rid, minutes=15, timezone_str="Asia/Ho_Chi_Minh")
    assert snoozed is not None
    assert snoozed["status"] == "snoozed"

    new_dt = datetime.fromisoformat(snoozed["trigger_at"])
    # Kiểm tra thời gian mới chênh lệch khoảng ~15 phút so với hiện tại
    diff_minutes = (new_dt - now).total_seconds() / 60
    assert 14.5 <= diff_minutes <= 15.5


def test_scheduler_missed_reminders_on_startup(tmp_path: Path) -> None:
    """Kiểm tra tự động phát hiện và cảnh báo các lời nhắc bị quá hạn khi khởi động."""
    db_path = tmp_path / "missed_test.db"
    store = ReminderStore(db_path=db_path)

    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.now(tz)

    # Tạo 2 lời nhắc trong quá khứ (giả lập tắt máy từ hôm qua)
    past_1 = (now - timedelta(hours=3)).isoformat()
    past_2 = (now - timedelta(minutes=45)).isoformat()
    future = (now + timedelta(hours=1)).isoformat()

    id1 = store.add_reminder("Nộp báo cáo tài chính tuần", trigger_at=past_1)
    id2 = store.add_reminder("Gọi điện cho đối tác", trigger_at=past_2)
    id3 = store.add_reminder("Tập thể dục buổi tối", trigger_at=future)

    scheduler = ReminderScheduler(store=store)
    missed = scheduler.check_missed_reminders_on_startup()

    assert len(missed) == 2
    missed_ids = [m["id"] for m in missed]
    assert id1 in missed_ids
    assert id2 in missed_ids
    assert id3 not in missed_ids

    # Kiểm tra trạng thái trong DB đã chuyển sang 'missed'
    assert store.get_reminder(id1)["status"] == "missed"
    assert store.get_reminder(id2)["status"] == "missed"
    assert store.get_reminder(id3)["status"] == "pending"

    # Kiểm tra định dạng báo cáo tiếng Việt
    report = scheduler.format_missed_reminders_report(missed)
    assert "Bạn đã bỏ lỡ 2 lời nhắc trong lúc tắt chương trình:" in report
    assert "Nộp báo cáo tài chính tuần" in report
    assert "Gọi điện cho đối tác" in report


@pytest.mark.asyncio
async def test_scheduler_pure_code_trigger(tmp_path: Path) -> None:
    """Kiểm tra việc kích hoạt nhắc nhở chạy thuần Python, không gọi LLM."""
    store = ReminderStore(db_path=tmp_path / "trigger_test.db")
    scheduler = ReminderScheduler(store=store)

    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    t_str = datetime.now(tz).isoformat()
    rid = store.add_reminder("Uống 1 cốc nước ấm", trigger_at=t_str)

    # Kích hoạt hàm xử lý khi đến giờ
    await scheduler._on_reminder_triggered(rid)

    # Kiểm tra trạng thái đã chuyển thành 'fired'
    updated = store.get_reminder(rid)
    assert updated["status"] == "fired"


def test_reminder_tools_permissions() -> None:
    """Kiểm tra cấp độ phân quyền an toàn của các công cụ nhắc việc."""
    create_tool = default_tool_registry.get("create_reminder")
    assert create_tool is not None
    assert create_tool.permission_level == PermissionLevel.CONFIRM

    list_tool = default_tool_registry.get("list_reminders")
    assert list_tool is not None
    assert list_tool.permission_level == PermissionLevel.READ

    cancel_tool = default_tool_registry.get("cancel_reminder")
    assert cancel_tool is not None
    assert cancel_tool.permission_level == PermissionLevel.WRITE_SAFE

    snooze_tool = default_tool_registry.get("snooze_reminder")
    assert snooze_tool is not None
    assert snooze_tool.permission_level == PermissionLevel.WRITE_SAFE


def test_reminder_tools_lifecycle(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra vòng đời đặt lịch, liệt kê, hoãn và huỷ qua bộ công cụ."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    future_time = (datetime.now(tz) + timedelta(minutes=30)).isoformat()

    # 1. create_reminder
    res_create = create_reminder(
        trigger_at=future_time,
        message="Họp thảo luận phương án kỹ thuật",
    )
    assert res_create["ok"] is True
    data_create = res_create["data"]
    assert "reminder_id" in data_create
    assert "Họp thảo luận phương án kỹ thuật" in data_create["confirmation"]
    rid = data_create["reminder_id"]

    # 2. list_reminders
    res_list = list_reminders()
    assert res_list["ok"] is True
    assert res_list["data"]["total"] >= 1
    found = any(r["id"] == rid for r in res_list["data"]["reminders"])
    assert found is True

    # 3. snooze_reminder
    res_snooze = snooze_reminder(reminder_id=rid, minutes=15)
    assert res_snooze["ok"] is True
    assert "Đã hoãn lời nhắc thêm 15 phút" in res_snooze["data"]

    # 4. cancel_reminder
    res_cancel = cancel_reminder(reminder_id=rid)
    assert res_cancel["ok"] is True
    assert "Đã huỷ lời nhắc" in res_cancel["data"]


@pytest.mark.asyncio
async def test_morning_briefing_generation(tmp_path: Path) -> None:
    """Kiểm tra tạo bản tin sáng tổng hợp công việc trong ngày."""
    store = ReminderStore(db_path=tmp_path / "briefing_test.db")

    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    today = datetime.now(tz)
    t1 = today.replace(hour=9, minute=0, second=0).isoformat()
    t2 = today.replace(hour=14, minute=30, second=0).isoformat()

    store.add_reminder("Đọc báo cáo thị trường", trigger_at=t1)
    store.add_reminder("Họp khách hàng dự án AI", trigger_at=t2)

    mock_text = "Chào buổi sáng! Hôm nay bạn có 2 cuộc hẹn: 09:00 đọc báo cáo và 14:30 họp khách hàng."
    mock_provider = MockBriefingProvider(output=mock_text)
    router = ModelRouter(gemini_provider=mock_provider, ollama_provider=mock_provider)

    briefing = await generate_morning_briefing(
        router=router,
        store=store,
        timezone_str="Asia/Ho_Chi_Minh",
    )

    assert "Chào buổi sáng!" in briefing
    assert "09:00" in briefing or "Họp khách hàng" in briefing


def test_show_windows_toast_fallback() -> None:
    """Kiểm tra hàm hiển thị toast không bị sập dù chạy trong môi trường không có GUI."""
    result = show_windows_toast(
        message="Kiểm tra thông báo toast an toàn",
        title="Thử nghiệm Toast",
    )
    assert result is True
