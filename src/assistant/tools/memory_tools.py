"""Bộ công cụ quản lý và truy vấn trí nhớ dài hạn (Memory Tools).

Cung cấp:
- remember_fact (WRITE_SAFE): Lưu hoặc cập nhật một ghi nhớ về người dùng.
- recall_memories (READ): Tìm kiếm trong trí nhớ dài hạn và lịch sử chat cũ.
- forget_memory (CONFIRM): Xóa một mục trí nhớ theo ID (cần người dùng phê duyệt).
"""

from typing import Any

from assistant.memory.store import MemoryStore
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import register_tool


def _get_store() -> MemoryStore:
    """Khởi tạo MemoryStore dùng chung."""
    return MemoryStore()


@register_tool(
    name="remember_fact",
    description="Ghi nhớ hoặc cập nhật một dữ kiện dài hạn về người dùng (sở thích, dự án, quy tắc đặt tên, thông tin chung).",
    permission_level=PermissionLevel.WRITE_SAFE,
)
def remember_fact(category: str, content: str) -> dict[str, Any]:
    """Lưu trữ một thông tin đáng nhớ vào cơ sở dữ liệu."""
    cat_clean = category.strip().lower()
    if cat_clean not in ("preference", "project", "naming_rule", "general"):
        cat_clean = "general"

    content_clean = content.strip()
    if not content_clean:
        return {"ok": False, "data": None, "error": "Nội dung ghi nhớ không được để trống.", "truncated": False}

    store = _get_store()

    # Chống trùng lặp
    existing = store.search_memories(content_clean[:25])
    matched_id = None
    for em in existing:
        if em["category"] == cat_clean:
            matched_id = em["id"]
            break

    if matched_id:
        store.update_memory(matched_id, content=content_clean, category=cat_clean)
        return {
            "ok": True,
            "data": f"Đã cập nhật mục trí nhớ ID '{matched_id}' ({cat_clean}): {content_clean}",
            "error": None,
            "truncated": False,
        }

    new_id = store.add_memory(category=cat_clean, content=content_clean)
    return {
        "ok": True,
        "data": f"Đã lưu vào trí nhớ dài hạn ({cat_clean}): {content_clean} (ID: {new_id})",
        "error": None,
        "truncated": False,
    }


@register_tool(
    name="recall_memories",
    description="Tìm kiếm trong trí nhớ dài hạn và lịch sử chat cũ để truy hồi các thông tin đã lưu về người dùng.",
    permission_level=PermissionLevel.READ,
)
def recall_memories(query: str, limit: int = 10) -> dict[str, Any]:
    """Truy xuất trí nhớ và lịch sử hội thoại qua tìm kiếm toàn văn FTS5."""
    q_clean = query.strip()
    if not q_clean:
        return {"ok": False, "data": None, "error": "Từ khóa tìm kiếm không được để trống.", "truncated": False}

    store = _get_store()

    # 1. Tìm trong bảng memories
    memories = store.search_memories(q_clean, limit=limit)
    if not memories:
        # Nếu FTS không khớp, liệt kê các memory gần nhất
        memories = store.list_memories(limit=5)

    # 2. Tìm trong tin nhắn cũ
    past_messages = store.search_messages(q_clean, limit=5)

    return {
        "ok": True,
        "data": {
            "query": q_clean,
            "memories_found": [
                {"id": m["id"], "category": m["category"], "content": m["content"]}
                for m in memories
            ],
            "past_messages_found": [
                {"role": pm["role"], "content": pm["content"], "date": pm["created_at"]}
                for pm in past_messages
            ],
        },
        "error": None,
        "truncated": False,
    }


@register_tool(
    name="forget_memory",
    description="Xóa một mục trí nhớ theo ID. Luôn cần người dùng phê duyệt trước khi xóa.",
    permission_level=PermissionLevel.CONFIRM,
)
def forget_memory(memory_id: str) -> dict[str, Any]:
    """Xóa mục trí nhớ khỏi cơ sở dữ liệu."""
    mem_id_clean = memory_id.strip()
    if not mem_id_clean:
        return {"ok": False, "data": None, "error": "ID mục trí nhớ không được để trống.", "truncated": False}

    store = _get_store()
    existing = store.get_memory(mem_id_clean)
    if not existing:
        return {"ok": False, "data": None, "error": f"Không tìm thấy mục trí nhớ với ID: {mem_id_clean}", "truncated": False}

    deleted = store.delete_memory(mem_id_clean)
    if deleted:
        return {
            "ok": True,
            "data": f"Đã xóa thành công mục trí nhớ ID '{mem_id_clean}': \"{existing['content']}\"",
            "error": None,
            "truncated": False,
        }
    return {"ok": False, "data": None, "error": "Không thể xóa mục trí nhớ.", "truncated": False}
