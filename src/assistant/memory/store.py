"""Lớp lưu trữ cơ sở dữ liệu SQLite cục bộ và tìm kiếm toàn văn FTS5 (Memory Store).

Quản lý:
- Bảng `conversations`: Lưu danh sách các cuộc trò chuyện.
- Bảng `messages`: Lưu lịch sử tin nhắn chi tiết.
- Bảng `memories`: Lưu các dữ kiện dài hạn về người dùng (preference, project, naming_rule, general).
- Bảng ảo FTS5: `memories_fts` và `messages_fts` để tìm kiếm toàn văn tiếng Việt siêu tốc.
Bật chế độ WAL (Write-Ahead Logging) để tối ưu hiệu năng đọc/ghi đồng thời trên Windows.
"""

from datetime import datetime
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


class MemoryStore:
    """Quản trị cơ sở dữ liệu SQLite của ứng dụng Trợ Lý AI."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            config = load_config(create_dirs=True)
            db_path = config.data_dir / "assistant.db"

        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối tới SQLite và bật chế độ WAL, tối ưu PRAGMA cho SSD cùng Foreign Keys."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -32000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """Khởi tạo cấu trúc các bảng và bảng ảo FTS5 nếu chưa tồn tại."""
        with self._get_connection() as conn:
            # 1. Bảng conversations
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_sensitive INTEGER NOT NULL DEFAULT 0
                );
                """
            )

            # 2. Bảng messages
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT,
                    model_used TEXT,
                    tool_calls_json TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

            # 3. Bảng memories
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_conv_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            # 4. Bảng ảo FTS5 cho memories
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    id UNINDEXED,
                    category,
                    content,
                    tokenize='unicode61'
                );
                """
            )

            # 5. Bảng ảo FTS5 cho messages
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    id UNINDEXED,
                    conversation_id UNINDEXED,
                    content,
                    tokenize='unicode61'
                );
                """
            )

            # 6. Các chỉ mục (INDEX) tăng tốc truy vấn thường xuyên
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);"
            )

    # =========================================================================
    # QUẢN LÝ HỘI THOẠI (CONVERSATIONS)
    # =========================================================================

    def create_conversation(
        self,
        title: str = "Cuộc trò chuyện mới",
        is_sensitive: bool = False,
    ) -> str:
        """Tạo mới một cuộc hội thoại."""
        conv_id = str(uuid.uuid4())
        now = get_current_iso_time()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at, is_sensitive)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conv_id, title, now, now, 1 if is_sensitive else 0),
            )
        return conv_id

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        """Lấy thông tin hội thoại theo ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conv_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def list_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        """Liệt kê danh sách hội thoại gần nhất."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, title, created_at, updated_at, is_sensitive
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def update_conversation(
        self,
        conv_id: str,
        title: str | None = None,
        is_sensitive: bool | None = None,
    ) -> bool:
        """Cập nhật tiêu đề hoặc cờ nhạy cảm của hội thoại."""
        now = get_current_iso_time()
        fields: list[str] = ["updated_at = ?"]
        params: list[Any] = [now]

        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if is_sensitive is not None:
            fields.append("is_sensitive = ?")
            params.append(1 if is_sensitive else 0)

        params.append(conv_id)
        query = f"UPDATE conversations SET {', '.join(fields)} WHERE id = ?"

        with self._get_connection() as conn:
            cur = conn.execute(query, tuple(params))
            return cur.rowcount > 0

    def delete_conversation(self, conv_id: str) -> bool:
        """Xoá một cuộc hội thoại và toàn bộ tin nhắn liên quan (Cascade)."""
        with self._get_connection() as conn:
            # Xoá FTS5 của các tin nhắn thuộc hội thoại này trước
            conn.execute("DELETE FROM messages_fts WHERE conversation_id = ?", (conv_id,))
            cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            return cur.rowcount > 0

    # =========================================================================
    # QUẢN LÝ TIN NHẮN (MESSAGES)
    # =========================================================================

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str | None,
        model_used: str | None = None,
        tool_calls_json: str | None = None,
    ) -> str:
        """Thêm tin nhắn vào cuộc hội thoại và đồng bộ FTS5."""
        msg_id = str(uuid.uuid4())
        now = get_current_iso_time()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, model_used, tool_calls_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conversation_id, role, content or "", model_used, tool_calls_json, now),
            )

            # Cập nhật thời điểm sửa đổi của cuộc hội thoại
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

            # Đồng bộ FTS5
            if content and content.strip():
                conn.execute(
                    "INSERT INTO messages_fts (id, conversation_id, content) VALUES (?, ?, ?)",
                    (msg_id, conversation_id, content.strip()),
                )

        return msg_id

    def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Lấy danh sách tin nhắn theo thứ tự thời gian tăng dần."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, conversation_id, role, content, model_used, tool_calls_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            )
            return [dict(r) for r in cursor.fetchall()]

    def search_messages(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Tìm kiếm toàn văn tin nhắn cũ qua FTS5."""
        q_clean = query.strip()
        if not q_clean:
            return []

        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    SELECT m.id, m.conversation_id, m.role, m.content, m.created_at, c.title as conversation_title
                    FROM messages_fts f
                    JOIN messages m ON f.id = m.id
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE messages_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (q_clean, limit),
                )
                return [dict(r) for r in cursor.fetchall()]
            except sqlite3.OperationalError:
                # Nếu cú pháp MATCH chứa ký tự đặc biệt hoặc lỗi FTS5, fallback qua LIKE
                cursor = conn.execute(
                    """
                    SELECT m.id, m.conversation_id, m.role, m.content, m.created_at, c.title as conversation_title
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.content LIKE ?
                    ORDER BY m.created_at DESC
                    LIMIT ?
                    """,
                    (f"%{q_clean}%", limit),
                )
                return [dict(r) for r in cursor.fetchall()]


    # =========================================================================
    # QUẢN LÝ TRÍ NHỚ DÀI HẠN (MEMORIES)
    # =========================================================================

    def add_memory(
        self,
        category: str,
        content: str,
        source_conv_id: str | None = None,
    ) -> str:
        """Lưu một dữ kiện mới vào trí nhớ dài hạn và đồng bộ FTS5."""
        mem_id = str(uuid.uuid4())
        now = get_current_iso_time()
        cat_clean = category.strip().lower()
        content_clean = content.strip()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO memories (id, category, content, source_conv_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mem_id, cat_clean, content_clean, source_conv_id, now, now),
            )

            # Đồng bộ FTS5
            conn.execute(
                "INSERT INTO memories_fts (id, category, content) VALUES (?, ?, ?)",
                (mem_id, cat_clean, content_clean),
            )

        return mem_id

    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        category: str | None = None,
    ) -> bool:
        """Cập nhật nội dung hoặc danh mục của một mục trí nhớ."""
        now = get_current_iso_time()
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                return False

            new_content = content.strip() if content is not None else row["content"]
            new_cat = category.strip().lower() if category is not None else row["category"]

            conn.execute(
                """
                UPDATE memories
                SET content = ?, category = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_content, new_cat, now, memory_id),
            )

            # Cập nhật FTS5
            conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
            conn.execute(
                "INSERT INTO memories_fts (id, category, content) VALUES (?, ?, ?)",
                (memory_id, new_cat, new_content),
            )
            return True

    def delete_memory(self, memory_id: str) -> bool:
        """Xoá một mục trí nhớ theo ID."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        """Lấy chi tiết một mục trí nhớ theo ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def list_memories(
        self,
        category: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Liệt kê danh sách các mục trí nhớ (có thể lọc theo danh mục)."""
        with self._get_connection() as conn:
            if category:
                cursor = conn.execute(
                    """
                    SELECT id, category, content, source_conv_id, created_at, updated_at
                    FROM memories
                    WHERE category = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (category.strip().lower(), limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, category, content, source_conv_id, created_at, updated_at
                    FROM memories
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            return [dict(r) for r in cursor.fetchall()]

    def search_memories(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Tìm kiếm toàn văn FTS5 trong bảng memories."""
        q_clean = query.strip()
        if not q_clean:
            return []

        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    SELECT m.id, m.category, m.content, m.created_at, m.updated_at
                    FROM memories_fts f
                    JOIN memories m ON f.id = m.id
                    WHERE memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (q_clean, limit),
                )
                return [dict(r) for r in cursor.fetchall()]
            except sqlite3.OperationalError:
                # Nếu cú pháp MATCH chứa ký tự đặc biệt gây lỗi FTS5, fallback qua LIKE
                cursor = conn.execute(
                    """
                    SELECT id, category, content, created_at, updated_at
                    FROM memories
                    WHERE content LIKE ? OR category LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (f"%{q_clean}%", f"%{q_clean}%", limit),
                )
                return [dict(r) for r in cursor.fetchall()]
