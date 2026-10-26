"""Kiểm thử tự động cho lớp MemoryStore (SQLite WAL, CRUD, FTS5 tiếng Việt)."""

from pathlib import Path
import sqlite3
from assistant.memory.store import MemoryStore


def test_memory_store_init_and_wal(tmp_path: Path) -> None:
    """Kiểm tra khởi tạo database, kích hoạt chế độ WAL và cấu trúc các bảng."""
    db_file = tmp_path / "test_assistant.db"
    store = MemoryStore(db_path=db_file)

    assert db_file.is_file()

    # Kiểm tra PRAGMA journal_mode = wal
    with sqlite3.connect(str(db_file)) as conn:
        cur = conn.execute("PRAGMA journal_mode;")
        mode = cur.fetchone()[0]
        assert mode.lower() == "wal"

        # Kiểm tra sự tồn tại của các bảng
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        assert "conversations" in tables
        assert "messages" in tables
        assert "memories" in tables
        assert "memories_fts" in tables
        assert "messages_fts" in tables


def test_conversations_crud(tmp_path: Path) -> None:
    """Kiểm tra tạo, đọc, cập nhật và xoá cuộc hội thoại (kèm cascade messages)."""
    db_file = tmp_path / "test_convs.db"
    store = MemoryStore(db_path=db_file)

    # 1. Tạo cuộc hội thoại
    cid = store.create_conversation(title="Dự án Website", is_sensitive=False)
    assert cid is not None

    # 2. Lấy thông tin
    conv = store.get_conversation(cid)
    assert conv is not None
    assert conv["title"] == "Dự án Website"
    assert conv["is_sensitive"] == 0

    # 3. Cập nhật hội thoại
    updated = store.update_conversation(cid, title="Dự án Website Windows App", is_sensitive=True)
    assert updated is True
    conv_updated = store.get_conversation(cid)
    assert conv_updated["title"] == "Dự án Website Windows App"
    assert conv_updated["is_sensitive"] == 1

    # 4. Liệt kê hội thoại
    convs = store.list_conversations(limit=10)
    assert len(convs) >= 1
    assert convs[0]["id"] == cid

    # 5. Thêm tin nhắn và xoá hội thoại kiểm tra cascade
    store.add_message(conversation_id=cid, role="user", content="Xin chào")
    messages = store.get_messages(cid)
    assert len(messages) == 1

    deleted = store.delete_conversation(cid)
    assert deleted is True
    assert store.get_conversation(cid) is None
    assert len(store.get_messages(cid)) == 0


def test_messages_crud_and_fts_search(tmp_path: Path) -> None:
    """Kiểm tra thêm tin nhắn và tìm kiếm toàn văn FTS5 tiếng Việt."""
    db_file = tmp_path / "test_msgs.db"
    store = MemoryStore(db_path=db_file)

    cid = store.create_conversation(title="Chat test")

    # Thêm các tin nhắn có dấu tiếng Việt
    mid1 = store.add_message(
        conversation_id=cid,
        role="user",
        content="Hãy viết cho tôi một bài báo cáo tài chính quý 3 năm 2026",
    )
    mid2 = store.add_message(
        conversation_id=cid,
        role="assistant",
        content="Đây là bản tóm tắt báo cáo tài chính quý 3 của công ty.",
        model_used="gemini-2.5-flash",
    )

    # Lấy danh sách tin nhắn
    msgs = store.get_messages(cid)
    assert len(msgs) == 2
    assert msgs[0]["id"] == mid1
    assert msgs[1]["id"] == mid2

    # Tìm kiếm toàn văn FTS5 bằng từ khoá tiếng Việt
    res = store.search_messages("báo cáo tài chính")
    assert len(res) >= 1
    contents = [r["content"] for r in res]
    assert any("quý 3" in c for c in contents)


def test_memories_crud_and_categories(tmp_path: Path) -> None:
    """Kiểm tra CRUD cho bảng memories với 4 danh mục chuẩn."""
    db_file = tmp_path / "test_mems.db"
    store = MemoryStore(db_path=db_file)

    # 1. Thêm các mục trí nhớ thuộc các danh mục khác nhau
    m1 = store.add_memory("preference", "Thích dùng giao diện nền tối dark mode")
    m2 = store.add_memory("naming_rule", "Quy tắc đặt tên file theo mẫu YYYY-MM-DD_ten-bao-cao")
    m3 = store.add_memory("project", "Đang xây dựng ứng dụng Trợ lý AI trên Windows")
    m4 = store.add_memory("general", "Người dùng là kỹ sư phần mềm")

    assert m1 and m2 and m3 and m4

    # 2. Lấy chi tiết
    mem = store.get_memory(m2)
    assert mem is not None
    assert mem["category"] == "naming_rule"
    assert "YYYY-MM-DD" in mem["content"]

    # 3. Lọc theo danh mục
    rules = store.list_memories(category="naming_rule")
    assert len(rules) == 1
    assert rules[0]["id"] == m2

    prefs = store.list_memories(category="preference")
    assert len(prefs) == 1
    assert prefs[0]["id"] == m1

    all_mems = store.list_memories()
    assert len(all_mems) == 4

    # 4. Cập nhật mục trí nhớ
    up_ok = store.update_memory(m2, content="Quy tắc đặt tên file theo mẫu YYYYMMDD_ten-file")
    assert up_ok is True
    mem_updated = store.get_memory(m2)
    assert "YYYYMMDD_ten-file" in mem_updated["content"]

    # 5. Xoá mục trí nhớ
    del_ok = store.delete_memory(m1)
    assert del_ok is True
    assert store.get_memory(m1) is None
    assert len(store.list_memories()) == 3


def test_memories_fts5_vietnamese(tmp_path: Path) -> None:
    """Kiểm tra tìm kiếm FTS5 tiếng Việt và khả năng fallback khi query chứa ký tự đặc biệt."""
    db_file = tmp_path / "test_fts.db"
    store = MemoryStore(db_path=db_file)

    store.add_memory("naming_rule", "Quy tắc đặt tên file báo cáo theo mẫu YYYY-MM-DD_ten-bao-cao")
    store.add_memory("project", "Dự án phát triển phần mềm quản lý kho hàng")

    # 1. Tìm kiếm FTS5 tiếng Việt
    results = store.search_memories("báo cáo")
    assert len(results) >= 1
    assert "YYYY-MM-DD_ten-bao-cao" in results[0]["content"]

    # 2. Tìm kiếm với ký tự đặc biệt hoặc dấu ngoặc (không làm sập hệ thống, fallback LIKE)
    results_special = store.search_memories("YYYY-MM-DD*")
    assert len(results_special) >= 1


def test_search_messages_special_characters_fallback(tmp_path: Path) -> None:
    """Kiểm tra search_messages với ký tự đặc biệt không bị văng lỗi FTS5 (Fix ERR-04)."""
    db_file = tmp_path / "test_msg_fts.db"
    store = MemoryStore(db_path=db_file)

    conv_id = store.create_conversation("Kiểm thử FTS")
    store.add_message(conv_id, role="user", content="Báo cáo tài chính quý 1: doanh thu tăng 15%")
    store.add_message(conv_id, role="assistant", content="Ghi nhận báo cáo tài chính quý 1.")

    # Tìm kiếm bình thường
    res1 = store.search_messages("tài chính")
    assert len(res1) >= 1

    # Tìm kiếm với ký tự đặc biệt FTS5 (không làm crash, tự động fallback sang LIKE)
    res2 = store.search_messages('quý 1: "*--')
    assert isinstance(res2, list)

