"""Lớp lưu trữ cơ sở dữ liệu SQLite cục bộ và tìm kiếm toàn văn FTS5 (Memory Store).

Quản lý:
- Bảng `conversations`: Lưu danh sách các cuộc trò chuyện.
- Bảng `messages`: Lưu lịch sử tin nhắn chi tiết.
- Bảng `memories`: Lưu các dữ kiện dài hạn về người dùng (preference, project, naming_rule, general).
- Bảng ảo FTS5: `memories_fts` và `messages_fts` để tìm kiếm toàn văn tiếng Việt siêu tốc.
Bật chế độ WAL (Write-Ahead Logging) để tối ưu hiệu năng đọc/ghi đồng thời trên Windows.
"""

from datetime import datetime
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any
import uuid
import zoneinfo

from assistant.config import load_config
from assistant.memory.embeddings import (
    blob_to_float_list,
    cosine_similarity,
    float_list_to_blob,
    get_embedding_sync,
    reciprocal_rank_fusion,
)

logger = logging.getLogger(__name__)


def get_current_iso_time(timezone_str: str = "Asia/Ho_Chi_Minh") -> str:
    """Lấy thời gian hiện tại định dạng ISO 8601 kèm múi giờ."""
    try:
        tz = zoneinfo.ZoneInfo(timezone_str)
        return datetime.now(tz).isoformat()
    except Exception:
        return datetime.now().isoformat()


class MemoryStore:
    """Quản trị cơ sở dữ liệu SQLite của ứng dụng Trợ Lý AI."""

    def __init__(
        self,
        db_path: Path | None = None,
        ollama_host: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        if db_path is None or ollama_host is None or embedding_model is None:
            config = load_config(create_dirs=True)
            if db_path is None:
                db_path = config.data_dir / "assistant.db"
            if ollama_host is None:
                ollama_host = getattr(config, "ollama_host", "http://127.0.0.1:11434")
            if embedding_model is None:
                embedding_model = getattr(config, "embedding_model", "nomic-embed-text")

        self.db_path = db_path
        self.ollama_host = ollama_host or "http://127.0.0.1:11434"
        self.embedding_model = embedding_model or "nomic-embed-text"
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối tới SQLite và bật chế độ WAL, tối ưu PRAGMA cho SSD cùng Foreign Keys."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
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

            # 6. Bảng lưu trữ vector embeddings cho memories (float32 BLOB)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    memory_id TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
                );
                """
            )

            # 7. Bảng memory_categories (Danh mục trí nhớ dài hạn động)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_categories (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    label TEXT NOT NULL,
                    icon TEXT DEFAULT 'tag',
                    color TEXT DEFAULT '#3b82f6',
                    created_at TEXT NOT NULL
                );
                """
            )

            # 8. Các chỉ mục (INDEX) tăng tốc truy vấn thường xuyên
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_embeddings_created ON memory_embeddings(created_at);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_categories_name ON memory_categories(name);"
            )

            # Nạp 4 danh mục mặc định nếu bảng trống
            cur = conn.execute("SELECT COUNT(*) FROM memory_categories;")
            if cur.fetchone()[0] == 0:
                now_seed = get_current_iso_time()
                default_cats = [
                    (str(uuid.uuid4()), "preference", "Sở thích", "heart", "#ec4899", now_seed),
                    (str(uuid.uuid4()), "project", "Dự án", "briefcase", "#3b82f6", now_seed),
                    (str(uuid.uuid4()), "naming_rule", "Quy tắc đặt tên", "code", "#8b5cf6", now_seed),
                    (str(uuid.uuid4()), "general", "Chung", "info", "#10b981", now_seed),
                ]
                conn.executemany(
                    """
                    INSERT INTO memory_categories (id, name, label, icon, color, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    default_cats,
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
        embedding: list[float] | None = None,
    ) -> str:
        """Lưu một dữ kiện mới vào trí nhớ dài hạn, đồng bộ FTS5 và sinh vector embedding."""
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

        # Tự động sinh vector embedding và lưu song song
        vec = embedding
        if vec is None:
            try:
                vec = get_embedding_sync(
                    content_clean,
                    host=self.ollama_host,
                    model=self.embedding_model,
                )
            except Exception as exc:
                logger.debug("Không thể tự động sinh vector embedding: %s", exc)
                vec = None

        if vec:
            try:
                blob = float_list_to_blob(vec)
                with self._get_connection() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO memory_embeddings (memory_id, embedding, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (mem_id, blob, now),
                    )
            except Exception as exc:
                logger.debug("Lỗi lưu vector embedding vào SQLite: %s", exc)

        return mem_id

    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        category: str | None = None,
        embedding: list[float] | None = None,
    ) -> bool:
        """Cập nhật nội dung hoặc danh mục của một mục trí nhớ và cập nhật vector embedding."""
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

        # Cập nhật vector embedding nếu content thay đổi hoặc có embedding mới truyền vào
        if content is not None or embedding is not None:
            vec = embedding
            if vec is None:
                try:
                    vec = get_embedding_sync(
                        new_content,
                        host=self.ollama_host,
                        model=self.embedding_model,
                    )
                except Exception as exc:
                    logger.debug("Không thể tự động cập nhật embedding: %s", exc)
                    vec = None

            if vec:
                try:
                    blob = float_list_to_blob(vec)
                    with self._get_connection() as conn:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO memory_embeddings (memory_id, embedding, created_at)
                            VALUES (?, ?, ?)
                            """,
                            (memory_id, blob, now),
                        )
                except Exception as exc:
                    logger.debug("Lỗi cập nhật embedding: %s", exc)

        return True

    def delete_memory(self, memory_id: str) -> bool:
        """Xoá một mục trí nhớ theo ID (đồng bộ FTS5 và embeddings)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
            conn.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
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

    def search_memories_hybrid(
        self,
        query: str,
        top_k: int = 10,
        host: str | None = None,
        embedding_model: str | None = None,
    ) -> list[dict[str, Any]]:
        """Tìm kiếm trí nhớ kết hợp Hybrid Search (FTS5 BM25 + Vector Similarity qua RRF).

        1. Lấy kết quả từ FTS5 (từ khóa chính xác).
        2. Lấy kết quả từ Cosine Similarity (tương đồng ngữ nghĩa).
        3. Kết hợp bằng thuật toán Reciprocal Rank Fusion (RRF: score = 1 / (60 + rank)).
        4. Tự động fallback mượt mà về tìm kiếm FTS5/LIKE nếu Ollama chưa bật hoặc chưa có vector.
        """
        q_clean = query.strip()
        if not q_clean:
            return []

        # 1. Lấy kết quả từ FTS5 (từ khóa chính xác)
        fts_results = self.search_memories(q_clean, limit=top_k * 2)
        fts_ids = [r["id"] for r in fts_results]

        # Kiểm tra nhanh: Nếu bảng memory_embeddings chưa có bất kỳ bản ghi nào,
        # lập tức trả về fts_results[:top_k] mà không tốn chi phí gọi Ollama sinh vector.
        try:
            with self._get_connection() as conn:
                has_vector = conn.execute("SELECT 1 FROM memory_embeddings LIMIT 1").fetchone()
            if not has_vector:
                return fts_results[:top_k]
        except Exception:
            return fts_results[:top_k]

        # 2. Sinh vector embedding cho truy vấn
        target_host = host or self.ollama_host
        target_model = embedding_model or self.embedding_model

        query_vec: list[float] | None = None
        try:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    get_embedding_sync,
                    q_clean,
                    host=target_host,
                    model=target_model,
                    timeout=1.5,
                )
                query_vec = future.result(timeout=1.6)
        except Exception as exc:
            logger.debug(
                "Bỏ qua vector embedding cho truy vấn '%s' (quá 1.5s hoặc lỗi): %s",
                q_clean,
                exc,
            )
            query_vec = None

        # Nếu không lấy được vector embedding (Ollama chưa bật hoặc lỗi model hoặc quá 1.5s), fallback mượt mà
        if query_vec is None:
            return fts_results[:top_k]

        # 3. Lấy tất cả vector từ bảng memory_embeddings để tính Cosine Similarity
        vector_rankings: list[tuple[str, float]] = []
        with self._get_connection() as conn:
            rows = conn.execute("SELECT memory_id, embedding FROM memory_embeddings").fetchall()
            for r in rows:
                mem_id = r["memory_id"]
                blob = r["embedding"]
                vec = blob_to_float_list(blob)
                if vec:
                    sim = cosine_similarity(query_vec, vec)
                    if sim > 0.0:
                        vector_rankings.append((mem_id, sim))

        # Nếu không có vector embedding nào trong database, fallback về FTS5
        if not vector_rankings:
            return fts_results[:top_k]

        # Sắp xếp vector theo độ tương đồng giảm dần
        vector_rankings.sort(key=lambda x: x[1], reverse=True)
        vector_ids = [mem_id for mem_id, _ in vector_rankings[: top_k * 2]]

        # 4. Kết hợp xếp hạng bằng Reciprocal Rank Fusion (RRF)
        ranking_lists: list[list[str]] = []
        if fts_ids:
            ranking_lists.append(fts_ids)
        if vector_ids:
            ranking_lists.append(vector_ids)

        fused_items = reciprocal_rank_fusion(ranking_lists, k=60)
        top_ids = [item_id for item_id, _ in fused_items[:top_k]]

        if not top_ids:
            return fts_results[:top_k]

        # 5. Lấy dữ liệu chi tiết của các memory theo thứ tự RRF đã xếp hạng
        placeholders = ",".join("?" for _ in top_ids)
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT id, category, content, source_conv_id, created_at, updated_at
                FROM memories
                WHERE id IN ({placeholders})
                """,
                tuple(top_ids),
            )
            mem_dict = {row["id"]: dict(row) for row in cursor.fetchall()}

        ordered_results: list[dict[str, Any]] = []
        for mem_id in top_ids:
            if mem_id in mem_dict:
                ordered_results.append(mem_dict[mem_id])

        return ordered_results

    # =========================================================================
    # QUẢN LÝ DANH MỤC TRÍ NHỚ (MEMORY CATEGORIES)
    # =========================================================================

    def list_categories(self) -> list[dict[str, Any]]:
        """Trả về toàn bộ danh mục trí nhớ sắp xếp theo ngày tạo."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM memory_categories ORDER BY created_at ASC;")
            return [dict(r) for r in cur.fetchall()]

    def get_category_by_id(self, cat_id: str) -> dict[str, Any] | None:
        """Lấy thông tin danh mục theo ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM memory_categories WHERE id = ?;", (cat_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_category_by_name(self, name: str) -> dict[str, Any] | None:
        """Lấy thông tin danh mục theo mã name (slug)."""
        clean_name = re.sub(r"[^a-z0-9_-]", "", name.strip().lower())
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM memory_categories WHERE name = ?;", (clean_name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def add_category(
        self,
        name: str,
        label: str,
        icon: str = "tag",
        color: str = "#3b82f6",
    ) -> str:
        """Thêm danh mục trí nhớ mới."""
        clean_name = re.sub(r"[^a-z0-9_-]", "", name.strip().lower())
        if not clean_name:
            raise ValueError("Mã định danh danh mục (name) không hợp lệ.")
        clean_label = label.strip()
        if not clean_label:
            raise ValueError("Tên nhãn danh mục không được để trống.")

        cat_id = str(uuid.uuid4())
        now = get_current_iso_time()
        clean_icon = (icon or "tag").strip()
        clean_color = (color or "#3b82f6").strip()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO memory_categories (id, name, label, icon, color, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cat_id, clean_name, clean_label, clean_icon, clean_color, now),
            )
        return cat_id

    def update_category(
        self,
        cat_id: str,
        label: str | None = None,
        icon: str | None = None,
        color: str | None = None,
    ) -> bool:
        """Cập nhật nhãn, biểu tượng hoặc màu của danh mục."""
        fields: list[str] = []
        params: list[Any] = []

        if label is not None:
            fields.append("label = ?")
            params.append(label.strip())
        if icon is not None:
            fields.append("icon = ?")
            params.append(icon.strip())
        if color is not None:
            fields.append("color = ?")
            params.append(color.strip())

        if not fields:
            return False

        params.append(cat_id)
        query = f"UPDATE memory_categories SET {', '.join(fields)} WHERE id = ?"
        with self._get_connection() as conn:
            cur = conn.execute(query, tuple(params))
            return cur.rowcount > 0

    def delete_category(self, cat_name: str) -> bool:
        """Xoá danh mục. Chuyển toàn bộ dữ kiện sang 'general' trước khi xoá."""
        clean_name = cat_name.strip().lower()
        if clean_name == "general":
            # Không cho phép xoá danh mục mặc định
            return False

        with self._get_connection() as conn:
            # 1. Chuyển toàn bộ dữ kiện trí nhớ thuộc danh mục bị xoá về 'general'
            conn.execute("UPDATE memories SET category = 'general' WHERE category = ?;", (clean_name,))
            conn.execute("UPDATE memories_fts SET category = 'general' WHERE category = ?;", (clean_name,))
            # 2. Xoá danh mục khỏi bảng memory_categories
            cur = conn.execute("DELETE FROM memory_categories WHERE name = ?;", (clean_name,))
            return cur.rowcount > 0
