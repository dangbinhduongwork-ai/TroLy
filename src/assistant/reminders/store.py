"""Lớp lưu trữ cơ sở dữ liệu SQLite cho các lời nhắc việc (Reminder Store).

Quản lý bảng `reminders` với các trạng thái:
- pending: Đang chờ đến giờ kích hoạt.
- fired: Đã phát thông báo thành công.
- snoozed: Đang hoãn nhắc, chờ thời điểm tiếp theo.
- cancelled: Người dùng đã huỷ.
- missed: Bị bỏ lỡ trong lúc tắt chương trình/tắt máy tính.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Any
import uuid
import zoneinfo

from assistant.config import load_config


def get_current_iso_time(timezone_str: str = "Asia/Ho_Chi_Minh") -> str:
    """Lấy thời gian hiện tại định dạng ISO 8601 kèm múi giờ."""
    try:
        tz = zoneinfo.ZoneInfo(timezone_str)
        return datetime.now(tz).isoformat()
    except Exception:
        return datetime.now().isoformat()


class ReminderStore:
    """Quản trị bảng reminders trong cơ sở dữ liệu SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            config = load_config(create_dirs=True)
            db_path = config.data_dir / "assistant.db"

        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối tới SQLite và bật chế độ WAL cùng tối ưu PRAGMA cho SSD."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -32000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        return conn

    def _init_db(self) -> None:
        """Khởi tạo bảng reminders nếu chưa tồn tại."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    message TEXT NOT NULL,
                    trigger_at TEXT NOT NULL,
                    cron_expr TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );
                """
            )
            # Tạo index tối ưu truy vấn thời gian và trạng thái
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_status_trigger ON reminders(status, trigger_at);"
            )

    def add_reminder(
        self,
        message: str,
        trigger_at: str,
        cron_expr: str | None = None,
    ) -> str:
        """Tạo mới một lời nhắc việc với trạng thái pending."""
        rem_id = str(uuid.uuid4())
        now = get_current_iso_time()
        msg_clean = message.strip()
        cron_clean = cron_expr.strip() if cron_expr else None

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reminders (id, message, trigger_at, cron_expr, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (rem_id, msg_clean, trigger_at, cron_clean, now),
            )
        return rem_id

    def get_reminder(self, reminder_id: str) -> dict[str, Any] | None:
        """Lấy thông tin một lời nhắc theo ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None

    def list_reminders(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Liệt kê danh sách các lời nhắc việc (có thể lọc theo trạng thái)."""
        with self._get_connection() as conn:
            if status:
                cur = conn.execute(
                    """
                    SELECT * FROM reminders
                    WHERE status = ?
                    ORDER BY trigger_at ASC
                    LIMIT ?
                    """,
                    (status.strip().lower(), limit),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT * FROM reminders
                    ORDER BY trigger_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            return [dict(r) for r in cur.fetchall()]

    def get_pending_reminders(self) -> list[dict[str, Any]]:
        """Lấy danh sách tất cả các lời nhắc đang chờ kích hoạt (pending hoặc snoozed)."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT * FROM reminders
                WHERE status IN ('pending', 'snoozed')
                ORDER BY trigger_at ASC
                """
            )
            return [dict(r) for r in cur.fetchall()]

    def get_missed_reminders(
        self,
        now_iso: str | None = None,
        timezone_str: str = "Asia/Ho_Chi_Minh",
    ) -> list[dict[str, Any]]:
        """Lấy các lời nhắc có trigger_at < thời điểm hiện tại nhưng vẫn ở trạng thái pending/snoozed."""
        if now_iso is None:
            now_iso = get_current_iso_time(timezone_str)

        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT * FROM reminders
                WHERE status IN ('pending', 'snoozed') AND trigger_at < ?
                ORDER BY trigger_at ASC
                """,
                (now_iso,),
            )
            return [dict(r) for r in cur.fetchall()]

    def mark_as_missed(self, reminder_ids: list[str]) -> int:
        """Đánh dấu hàng loạt lời nhắc là missed."""
        if not reminder_ids:
            return 0

        placeholders = ",".join("?" for _ in reminder_ids)
        with self._get_connection() as conn:
            cur = conn.execute(
                f"UPDATE reminders SET status = 'missed' WHERE id IN ({placeholders})",
                tuple(reminder_ids),
            )
            return cur.rowcount

    def update_status(self, reminder_id: str, status: str) -> bool:
        """Cập nhật trạng thái của lời nhắc (fired, snoozed, cancelled, missed, pending)."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE reminders SET status = ? WHERE id = ?",
                (status.strip().lower(), reminder_id),
            )
            return cur.rowcount > 0

    def update_trigger_time(self, reminder_id: str, new_trigger_at: str, status: str = "pending") -> bool:
        """Cập nhật thời gian kích hoạt mới và chuyển trạng thái."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE reminders SET trigger_at = ?, status = ? WHERE id = ?",
                (new_trigger_at, status, reminder_id),
            )
            return cur.rowcount > 0

    def snooze_reminder(
        self,
        reminder_id: str,
        minutes: int = 10,
        timezone_str: str = "Asia/Ho_Chi_Minh",
    ) -> dict[str, Any] | None:
        """Hoãn lời nhắc lại thêm N phút (trạng thái đổi thành 'snoozed')."""
        rem = self.get_reminder(reminder_id)
        if not rem:
            return None

        try:
            tz = zoneinfo.ZoneInfo(timezone_str)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now()

        new_trigger = now + timedelta(minutes=minutes)
        new_trigger_iso = new_trigger.isoformat()

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE reminders SET trigger_at = ?, status = 'snoozed' WHERE id = ?",
                (new_trigger_iso, reminder_id),
            )

        rem["trigger_at"] = new_trigger_iso
        rem["status"] = "snoozed"
        return rem

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Huỷ bỏ một lời nhắc việc."""
        return self.update_status(reminder_id, "cancelled")

    def delete_reminder(self, reminder_id: str) -> bool:
        """Xoá hoàn toàn một lời nhắc khỏi cơ sở dữ liệu."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            return cur.rowcount > 0
