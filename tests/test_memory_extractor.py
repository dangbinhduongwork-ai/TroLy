"""Kiểm thử tự động cho memory/extractor.py với mock provider.

Đảm bảo:
- Trích xuất đúng thông tin.
- Nếu is_sensitive=True, BẮT BUỘC dùng local (Ollama) và TUYỆT ĐỐI không gọi Gemini.
- Chống trùng lặp: cập nhật bản ghi cũ thay vì tạo rác.
"""

from collections.abc import AsyncIterator
from pathlib import Path
import pytest
from assistant.core.router import ModelRouter
from assistant.llm.base import LLMProvider, Message, StreamEvent
from assistant.memory.extractor import (
    _clean_json_response,
    _has_memory_signal,
    extract_and_store_memories,
)
from assistant.memory.store import MemoryStore


class MockProvider(LLMProvider):
    """Provider giả lập dùng trong kiểm thử."""

    def __init__(self, name: str, mock_output: str) -> None:
        self._name = name
        self.default_model = f"mock-{name}"
        self.mock_output = mock_output
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._name

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        self.call_count += 1
        yield StreamEvent(type="text_delta", content=self.mock_output)

    async def list_models(self) -> list[str]:
        return [self.default_model]


def test_has_memory_signal() -> None:
    """Kiểm tra nhận diện câu nói có tín hiệu ghi nhớ."""
    assert _has_memory_signal("Hãy nhớ tôi thích đặt tên file theo chuẩn mới") is True
    assert _has_memory_signal("Ghi nhớ giúp tôi dự án đang làm") is True
    assert _has_memory_signal("Quy tắc của tôi là không xóa file gốc") is True
    assert _has_memory_signal("Thời tiết hôm nay ở Hà Nội thế nào?") is False
    assert _has_memory_signal("Hãy mở trình duyệt Edge") is False


def test_clean_json_response() -> None:
    """Kiểm tra phân tích JSON từ phản hồi LLM (cả dạng thuần và bọc trong markdown code block)."""
    # 1. JSON thuần
    raw_1 = '[{"category": "naming_rule", "content": "Quy tắc đặt tên file YYYY-MM-DD"}]'
    res_1 = _clean_json_response(raw_1)
    assert len(res_1) == 1
    assert res_1[0]["category"] == "naming_rule"

    # 2. Bọc trong code block markdown
    raw_2 = '```json\n[{"category": "preference", "content": "Thích dùng dark mode"}]\n```'
    res_2 = _clean_json_response(raw_2)
    assert len(res_2) == 1
    assert res_2[0]["category"] == "preference"

    # 3. Chuỗi rác không hợp lệ
    assert _clean_json_response("Đây không phải là json") == []


@pytest.mark.asyncio
async def test_extract_and_store_normal(tmp_path: Path) -> None:
    """Kiểm tra trích xuất và lưu trí nhớ ở chế độ bình thường."""
    store = MemoryStore(db_path=tmp_path / "test_store.db")

    mock_gemini = MockProvider(
        name="gemini",
        mock_output='[{"category": "naming_rule", "content": "Quy tắc đặt tên file báo cáo theo mẫu YYYY-MM-DD_ten-bao-cao"}]',
    )
    mock_ollama = MockProvider(name="ollama", mock_output="[]")

    router = ModelRouter(gemini_provider=mock_gemini, ollama_provider=mock_ollama)
    router.set_mode("gemini")

    results = await extract_and_store_memories(
        user_message="Hãy nhớ tôi thích đặt tên file báo cáo theo mẫu YYYY-MM-DD_ten-bao-cao",
        assistant_response="Tôi đã ghi nhớ quy tắc đặt tên file của bạn.",
        store=store,
        router=router,
        is_sensitive=False,
    )

    assert len(results) == 1
    assert results[0]["action"] == "created"
    assert results[0]["category"] == "naming_rule"
    assert mock_gemini.call_count == 1
    assert mock_ollama.call_count == 0

    # Kiểm tra đã lưu vào DB
    mems = store.list_memories()
    assert len(mems) == 1
    assert "YYYY-MM-DD" in mems[0]["content"]


@pytest.mark.asyncio
async def test_extract_and_store_sensitive_local_only(tmp_path: Path) -> None:
    """Kiểm định nguyên tắc an toàn: is_sensitive=True BẮT BUỘC chỉ dùng Ollama, CẤM gọi Gemini."""
    store = MemoryStore(db_path=tmp_path / "test_store_sens.db")

    mock_gemini = MockProvider(name="gemini", mock_output="[]")
    mock_ollama = MockProvider(
        name="ollama",
        mock_output='[{"category": "project", "content": "Dự án bảo mật mật khẩu nội bộ"}]',
    )

    router = ModelRouter(gemini_provider=mock_gemini, ollama_provider=mock_ollama)
    # Kể cả khi router đang để chế độ "gemini", khi is_sensitive=True vẫn cấm gọi Gemini
    router.set_mode("gemini")

    results = await extract_and_store_memories(
        user_message="Ghi nhớ dự án bảo mật nội bộ này",
        assistant_response="Tôi đã ghi nhận.",
        store=store,
        router=router,
        is_sensitive=True,  # ĐÁNH DẤU NHẠY CẢM
    )

    assert len(results) == 1
    assert results[0]["category"] == "project"

    # KIỂM ĐỊNH TUYỆT ĐỐI: Gemini KHÔNG được gọi bất kỳ lần nào
    assert mock_gemini.call_count == 0
    assert mock_ollama.call_count == 1


@pytest.mark.asyncio
async def test_extract_and_store_deduplication(tmp_path: Path) -> None:
    """Kiểm tra chống trùng lặp: cập nhật bản ghi cũ khi nội dung tương tự đã tồn tại."""
    store = MemoryStore(db_path=tmp_path / "test_dedup.db")

    # Đã có sẵn 1 quy tắc đặt tên cũ
    old_id = store.add_memory("naming_rule", "Quy tắc đặt tên file báo cáo theo mẫu YYYY-MM-DD")

    mock_ollama = MockProvider(
        name="ollama",
        mock_output='[{"category": "naming_rule", "content": "Quy tắc đặt tên file báo cáo theo mẫu YYYYMMDD_v2"}]',
    )
    router = ModelRouter(gemini_provider=mock_ollama, ollama_provider=mock_ollama)
    router.set_mode("local")

    results = await extract_and_store_memories(
        user_message="Hãy nhớ quy tắc đặt tên file báo cáo mới là YYYYMMDD_v2",
        assistant_response="Tôi đã cập nhật quy tắc cho bạn.",
        store=store,
        router=router,
        is_sensitive=False,
    )

    assert len(results) == 1
    assert results[0]["action"] == "updated"
    assert results[0]["id"] == old_id

    # Tổng số bản ghi trong DB vẫn là 1, không sinh bản ghi rác
    all_mems = store.list_memories()
    assert len(all_mems) == 1
    assert "YYYYMMDD_v2" in all_mems[0]["content"]


@pytest.mark.asyncio
async def test_extract_and_save_compatibility(tmp_path: Path) -> None:
    """Kiểm tra hàm tương thích extract_and_save_memories hoạt động với các tham số từ ws.py."""
    from assistant.memory.extractor import extract_and_save_memories

    store = MemoryStore(db_path=tmp_path / "test_compat.db")
    mock_ollama = MockProvider(
        name="ollama",
        mock_output='[{"category": "preference", "content": "Thích dùng dark mode"}]',
    )
    router = ModelRouter(gemini_provider=mock_ollama, ollama_provider=mock_ollama)

    results = await extract_and_save_memories(
        user_message="Hãy nhớ rằng tôi thích dùng dark mode",
        assistant_message="Đã ghi nhớ sở thích của bạn.",
        conv_id="conv-123",
        router=router,
        memory_store=store,
        is_sensitive=False,
    )

    assert len(results) == 1
    assert results[0]["category"] == "preference"
    assert results[0]["action"] == "created"

