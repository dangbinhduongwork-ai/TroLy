"""Kịch bản kiểm tra độc lập luồng trí nhớ dài hạn (End-to-End Memory Verification).

Mục tiêu:
1. Lưu một quy tắc vào SQLite: "Hãy nhớ tôi thích đặt tên file báo cáo theo mẫu YYYY-MM-DD_ten-bao-cao"
2. Tắt phiên, khởi động lại phiên mới và truy vấn trí nhớ.
3. Kiểm tra tự động chèn vào system prompt.
4. Thử nghiệm sửa và xóa trí nhớ qua store/tools.
"""

import sys
from pathlib import Path

# Thêm src vào đường dẫn nạp module
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from assistant.config import load_config
from assistant.core.context import ConversationContext
from assistant.core.prompts import get_system_prompt
from assistant.memory.store import MemoryStore
from assistant.tools.memory_tools import recall_memories, remember_fact, forget_memory


def main() -> int:
    print("=" * 65)
    print("KIỂM TRA TỰ ĐỘNG: LUỒNG TRÍ NHỚ DÀI HẠN (GIAI ĐOẠN 3)")
    print("=" * 65)

    config = load_config(create_dirs=True)
    db_path = config.data_dir / "assistant_test_flow.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    store = MemoryStore(db_path=db_path)
    print(f"1. Khởi tạo cơ sở dữ liệu SQLite tại: {db_path} [OK]")

    # 1. Người dùng yêu cầu ghi nhớ
    fact_text = "Quy tắc đặt tên file báo cáo theo mẫu YYYY-MM-DD_ten-bao-cao"
    mem_id = store.add_memory(
        category="naming_rule",
        content=fact_text,
    )
    print(f"2. Đã ghi nhớ: ({fact_text}) -> ID: {mem_id} [OK]")

    # 2. Giả lập tắt chương trình và mở phiên mới
    print("\n--- [GIẢ LẬP TẮT ỨNG DỤNG VÀ KHỞI ĐỘNG PHIÊN MỚI] ---")
    store_new_session = MemoryStore(db_path=db_path)
    ctx_new = ConversationContext()

    # 3. Lấy trí nhớ nạp vào system prompt
    active_mems = ctx_new.get_relevant_memories(store_new_session, max_tokens=600)
    sys_prompt = get_system_prompt(memories=active_mems)

    assert "[TRÍ NHỚ DÀI HẠN VỀ NGƯỜI DÙNG]" in sys_prompt
    assert fact_text in sys_prompt
    print("3. Kiểm tra System Prompt phiên mới:")
    print("   -> Đã tự động chèn trí nhớ người dùng vào System Prompt [OK]")

    # 4. Tìm kiếm toàn văn FTS5 tiếng Việt
    fts_res = store_new_session.search_memories("báo cáo")
    assert len(fts_res) >= 1
    assert fts_res[0]["id"] == mem_id
    print(f"4. Tìm kiếm FTS5 tiếng Việt với từ khóa 'báo cáo': Tìm thấy {len(fts_res)} kết quả [OK]")

    # 5. Thử nghiệm cập nhật trí nhớ (như lệnh /memory-edit)
    new_fact = "Quy tắc đặt tên file báo cáo theo mẫu YYYYMMDD_ten-bao-cao_v2"
    up_ok = store_new_session.update_memory(mem_id, content=new_fact)
    assert up_ok is True
    updated_mem = store_new_session.get_memory(mem_id)
    assert updated_mem["content"] == new_fact
    print(f"5. Thao tác /memory-edit: Đã cập nhật thành '{new_fact}' [OK]")

    # 6. Thao tác xóa trí nhớ (như lệnh /memory-del)
    del_ok = store_new_session.delete_memory(mem_id)
    assert del_ok is True
    assert store_new_session.get_memory(mem_id) is None
    print(f"6. Thao tác /memory-del: Đã xóa mục trí nhớ ID: {mem_id} [OK]")

    print("\n" + "=" * 65)
    print("KẾT QUẢ: Toàn bộ tiêu chí nghiệm thu Giai đoạn 3 ĐÃ HOÀN TẤT XUẤT SẮC!")
    print("=" * 65)

    # Dọn dẹp file db test
    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
