"""Kiểm thử tự động cho quản lý ngữ cảnh hội thoại (core/context.py) và system prompt (core/prompts.py)."""

import pytest

from assistant.core.context import ConversationContext, estimate_messages_tokens, estimate_tokens
from assistant.core.prompts import get_system_prompt
from assistant.llm.base import Message
from tests.test_router import DummyProvider


def test_estimate_tokens() -> None:
    """Kiểm tra hàm ước lượng số token."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("Xin chào bạn, tôi là trợ lý AI.") >= 10


def test_context_basic_operations() -> None:
    """Kiểm tra các thao tác thêm, xóa và chuyển đổi tin nhắn trong ngữ cảnh."""
    ctx = ConversationContext(max_tokens=1000)
    ctx.add_user_message("Câu hỏi 1")
    ctx.add_assistant_message("Câu trả lời 1")

    assert len(ctx.messages) == 2
    llm_msgs = ctx.get_messages_for_llm()
    assert len(llm_msgs) == 2
    assert llm_msgs[0].role == "user"
    assert llm_msgs[1].role == "assistant"

    ctx.clear()
    assert len(ctx.messages) == 0
    assert ctx.summary is None


@pytest.mark.asyncio
async def test_context_compression_triggers_when_budget_exceeded() -> None:
    """Kiểm tra khi vượt quá ngân sách token thì kích hoạt tóm tắt."""
    # Đặt max_tokens thấp để dễ kích hoạt
    ctx = ConversationContext(max_tokens=60, keep_recent_turns=1)

    # Thêm 3 lượt hội thoại (6 tin nhắn dài)
    long_text = "Đây là một đoạn văn bản dài nhằm mục đích tăng lượng token của phiên hội thoại để kiểm thử tính năng tóm tắt tự động."
    for i in range(3):
        ctx.add_user_message(f"User turn {i}: {long_text}")
        ctx.add_assistant_message(f"Assistant turn {i}: {long_text}")

    assert len(ctx.messages) == 6

    # Model giả lập trả về bản tóm tắt
    summarizer = DummyProvider(
        name="ollama",
        default_model="qwen2.5:7b",
        responses=["Tóm tắt: Người dùng đã trao đổi về việc kiểm thử token."],
    )

    compressed = await ctx.check_and_compress(local_provider=summarizer)
    assert compressed is True
    # Chỉ giữ lại 1 lượt gần nhất = 2 tin nhắn (keep_recent_turns=1)
    assert len(ctx.messages) == 2
    assert ctx.summary is not None
    assert "Tóm tắt: Người dùng đã trao đổi" in ctx.summary

    # Kiểm tra tin nhắn gửi đến LLM có bao gồm tóm tắt
    llm_msgs = ctx.get_messages_for_llm()
    assert any("[TÓM TẮT LỊCH SỬ HỘI THOẠI TRƯỚC ĐÓ]" in (m.content or "") for m in llm_msgs)


def test_get_system_prompt_has_datetime_and_timezone() -> None:
    """Kiểm tra system prompt luôn chèn thông tin ngày giờ và múi giờ."""
    prompt = get_system_prompt(timezone_str="Asia/Ho_Chi_Minh")
    assert "[THÔNG TIN HỆ THỐNG]" in prompt
    assert "Múi giờ: Asia/Ho_Chi_Minh" in prompt
    assert "Thời gian hiện tại:" in prompt


def test_get_system_prompt_with_memories() -> None:
    """Kiểm tra system prompt tự động chèn trí nhớ dài hạn của người dùng."""
    memories = [
        {"category": "naming_rule", "content": "Quy tắc đặt tên file YYYY-MM-DD"},
        {"category": "preference", "content": "Thích dùng dark mode"},
    ]
    prompt = get_system_prompt(memories=memories)
    assert "[TRÍ NHỚ DÀI HẠN VỀ NGƯỜI DÙNG]" in prompt
    assert "(naming_rule): Quy tắc đặt tên file YYYY-MM-DD" in prompt
    assert "(preference): Thích dùng dark mode" in prompt


def test_context_load_from_store_and_memories_budget(tmp_path) -> None:
    """Kiểm tra tải lịch sử từ SQLite và lấy trí nhớ theo ngân sách token."""
    from assistant.memory.store import MemoryStore

    db_path = tmp_path / "context_test.db"
    store = MemoryStore(db_path=db_path)

    cid = store.create_conversation("Hội thoại kiểm thử")
    store.add_message(cid, "user", "Tin nhắn cũ 1")
    store.add_message(cid, "assistant", "Tin nhắn phản hồi 1")

    # 1. Tải vào context
    ctx = ConversationContext()
    ctx.load_from_store(store, cid)
    assert len(ctx.messages) == 2
    assert ctx.messages[0].content == "Tin nhắn cũ 1"

    # 2. Thêm nhiều trí nhớ và kiểm tra giới hạn token
    for i in range(10):
        store.add_memory("preference", f"Sở thích người dùng số {i}: {('rất thích ' * 20)}")

    relevant = ctx.get_relevant_memories(store, max_tokens=100)
    # Vì mỗi memory khá dài, ngân sách 100 token sẽ chỉ lấy được số lượng hạn chế
    assert len(relevant) < 10


def test_context_add_message_from_dict() -> None:
    """Kiểm tra phương thức add_message_from_dict nạp dữ liệu đúng."""
    ctx = ConversationContext()
    ctx.add_message_from_dict(role="user", content="Chào trợ lý")
    ctx.add_message_from_dict(role="assistant", content="Xin chào bạn!")
    assert len(ctx.messages) == 2
    assert ctx.messages[0].role == "user"
    assert ctx.messages[0].content == "Chào trợ lý"
    assert ctx.messages[1].role == "assistant"
    assert ctx.messages[1].content == "Xin chào bạn!"

