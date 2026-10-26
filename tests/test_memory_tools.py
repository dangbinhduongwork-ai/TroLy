"""Kiểm thử tự động cho bộ công cụ trí nhớ (remember_fact, recall_memories, forget_memory)."""

from pathlib import Path
from assistant.safety.permissions import PermissionLevel
from assistant.tools.memory_tools import forget_memory, recall_memories, remember_fact
from assistant.tools.registry import default_tool_registry


def test_memory_tools_permissions() -> None:
    """Kiểm tra cấp độ phân quyền của từng công cụ trí nhớ."""
    tool_remember = default_tool_registry.get("remember_fact")
    assert tool_remember is not None
    assert tool_remember.permission_level == PermissionLevel.WRITE_SAFE

    tool_recall = default_tool_registry.get("recall_memories")
    assert tool_recall is not None
    assert tool_recall.permission_level == PermissionLevel.READ

    tool_forget = default_tool_registry.get("forget_memory")
    assert tool_forget is not None
    assert tool_forget.permission_level == PermissionLevel.CONFIRM


def test_memory_tools_lifecycle(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra vòng đời ghi nhớ, truy hồi và xóa trí nhớ qua công cụ."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    # 1. Ghi nhớ một sở thích
    res_rem = remember_fact(category="preference", content="Thích dùng dark mode và giao diện tiếng Việt")
    assert res_rem["ok"] is True
    assert "Đã lưu vào trí nhớ dài hạn" in res_rem["data"]

    # 2. Ghi nhớ quy tắc đặt tên file
    res_rule = remember_fact(
        category="naming_rule",
        content="Quy tắc đặt tên file báo cáo theo mẫu YYYY-MM-DD_ten-bao-cao",
    )
    assert res_rule["ok"] is True

    # 3. Truy hồi trí nhớ (recall_memories)
    res_recall = recall_memories(query="báo cáo")
    assert res_recall["ok"] is True
    data = res_recall["data"]
    assert "memories_found" in data
    assert len(data["memories_found"]) >= 1
    found_rule = data["memories_found"][0]
    assert found_rule["category"] == "naming_rule"
    mem_id = found_rule["id"]

    # 4. Cập nhật khi ghi nhớ nội dung tương tự (chống trùng lặp)
    res_update = remember_fact(
        category="naming_rule",
        content="Quy tắc đặt tên file báo cáo theo mẫu YYYYMMDD_v2",
    )
    assert res_update["ok"] is True
    assert "Đã cập nhật" in res_update["data"]

    # 5. Xóa trí nhớ theo ID (forget_memory)
    res_forget = forget_memory(memory_id=mem_id)
    assert res_forget["ok"] is True
    assert "Đã xóa thành công" in res_forget["data"]

    # Thử xóa lại ID đã xóa
    res_forget_again = forget_memory(memory_id=mem_id)
    assert res_forget_again["ok"] is False
    assert "Không tìm thấy" in res_forget_again["error"]
