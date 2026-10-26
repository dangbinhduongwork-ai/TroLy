"""Kiểm thử tự động cho cơ chế Hybrid Search (FTS5 BM25 + Vector Similarity qua RRF)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from assistant.core.context import ConversationContext
from assistant.memory.embeddings import (
    blob_to_float_list,
    cosine_similarity,
    float_list_to_blob,
    get_embedding_async,
    get_embedding_sync,
    reciprocal_rank_fusion,
)
from assistant.memory.store import MemoryStore


def test_vector_blob_serialization_and_deserialization() -> None:
    """Kiểm tra tuần tự hóa float list thành BLOB và giải mã ngược lại bằng struct."""
    original = [0.12345, -0.6789, 1.0, 0.0, -1.5]
    blob = float_list_to_blob(original)
    assert isinstance(blob, bytes)
    assert len(blob) == len(original) * 4  # 4 bytes mỗi float32

    recovered = blob_to_float_list(blob)
    assert len(recovered) == len(original)
    for orig, rec in zip(original, recovered):
        assert abs(orig - rec) < 1e-5

    # Kiểm tra trường hợp biên: rỗng
    assert float_list_to_blob([]) == b""
    assert blob_to_float_list(b"") == []


def test_cosine_similarity_pure_python() -> None:
    """Kiểm tra hàm tính Cosine Similarity thuần Python với math."""
    # 1. Hai vector giống hệt nhau -> 1.0
    v1 = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v1, v1) - 1.0) < 1e-5

    # 2. Hai vector trực giao (vuông góc) -> 0.0
    v_orth1 = [1.0, 0.0]
    v_orth2 = [0.0, 1.0]
    assert abs(cosine_similarity(v_orth1, v_orth2)) < 1e-5

    # 3. Hai vector ngược chiều -> -1.0
    v_neg = [-1.0, -2.0, -3.0]
    assert abs(cosine_similarity(v1, v_neg) - (-1.0)) < 1e-5

    # 4. Vector rỗng hoặc khác độ dài -> 0.0
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_reciprocal_rank_fusion_logic() -> None:
    """Kiểm tra thuật toán Reciprocal Rank Fusion kết hợp thứ hạng."""
    # Danh sách 1: [A, B, C]
    # Danh sách 2: [B, D, A]
    list1 = ["A", "B", "C"]
    list2 = ["B", "D", "A"]

    fused = reciprocal_rank_fusion([list1, list2], k=60)
    # B đứng #2 ở list1 (rank 2) và #1 ở list2 (rank 1): 1/62 + 1/61 ~ 0.016129 + 0.016393 = 0.032522
    # A đứng #1 ở list1 (rank 1) và #3 ở list2 (rank 3): 1/61 + 1/63 ~ 0.016393 + 0.015873 = 0.032266
    # Điểm của B phải cao hơn A
    fused_dict = dict(fused)
    assert fused_dict["B"] > fused_dict["A"]
    assert fused[0][0] == "B"
    assert fused[1][0] == "A"


def test_ollama_embeddings_client_sync_and_async() -> None:
    """Kiểm tra gọi API Ollama embeddings sync và async."""
    fake_vector = [0.1, 0.2, 0.3, 0.4]

    # Test sync thành công
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embedding": fake_vector}

    with patch("httpx.Client.post", return_value=mock_resp):
        res = get_embedding_sync("kiểm thử văn bản")
        assert res == fake_vector

    # Test sync lỗi kết nối mạng -> fallback trả về None mượt mà
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        res_fail = get_embedding_sync("kiểm thử khi ollama tắt")
        assert res_fail is None

    # Test prompt rỗng
    assert get_embedding_sync("") is None


@pytest.mark.asyncio
async def test_ollama_embeddings_client_async() -> None:
    """Kiểm tra hàm get_embedding_async."""
    fake_vector = [0.5, 0.6, 0.7]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embedding": fake_vector}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await get_embedding_async("văn bản bất đồng bộ")
        assert res == fake_vector

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Ollama offline")):
        res_fail = await get_embedding_async("thử lỗi")
        assert res_fail is None


def test_hybrid_search_synonym_matching(tmp_path: Path) -> None:
    """Kiểm thử tìm kiếm từ đồng nghĩa (semantic matching) mà FTS5 thuần túy không bắt được.

    Yêu cầu: query "quy tắc đặt tên" vẫn match với memory "cách đặt file YYYY-MM-DD".
    """
    db_file = tmp_path / "test_hybrid.db"
    store = MemoryStore(db_path=db_file)

    # 1. Thêm các mục trí nhớ kèm vector embedding mẫu
    # Giả lập không gian vector 3 chiều:
    # Trục 0: Khái niệm liên quan đến quy tắc/cách đặt tên file
    # Trục 1: Khái niệm liên quan đến dự án trợ lý
    # Trục 2: Khái niệm liên quan đến giao diện dark mode
    m1 = store.add_memory(
        category="naming_rule",
        content="cách đặt file YYYY-MM-DD",
        embedding=[0.95, 0.05, 0.0],
    )
    m2 = store.add_memory(
        category="project",
        content="dự án hệ thống trợ lý ảo trên hệ điều hành Windows",
        embedding=[0.05, 0.95, 0.0],
    )
    m3 = store.add_memory(
        category="preference",
        content="thích sử dụng giao diện màu tối dark mode",
        embedding=[0.0, 0.05, 0.95],
    )

    # 2. Kiểm tra FTS5 thuần túy không tìm thấy "cách đặt file YYYY-MM-DD" khi search "quy tắc đặt tên"
    fts_pure = store.search_memories("quy tắc đặt tên")
    # Từ "quy tắc" và "tên" hoàn toàn không có trong chuỗi "cách đặt file YYYY-MM-DD"
    assert not any(r["id"] == m1 for r in fts_pure)

    # 3. Khi dùng Hybrid Search với vector embedding của truy vấn "quy tắc đặt tên"
    # Vector của truy vấn "quy tắc đặt tên" có độ tương đồng ngữ nghĩa rất cao với m1
    query_vector = [0.90, 0.10, 0.0]

    with patch("assistant.memory.store.get_embedding_sync", return_value=query_vector):
        results = store.search_memories_hybrid("quy tắc đặt tên", top_k=5)

        assert len(results) >= 1
        # m1 phải được đưa lên vị trí đầu tiên nhờ Vector Similarity kết hợp RRF
        assert results[0]["id"] == m1
        assert "cách đặt file YYYY-MM-DD" in results[0]["content"]


def test_hybrid_search_fallback_when_ollama_offline(tmp_path: Path) -> None:
    """Kiểm tra khả năng fallback mượt mà về FTS5 khi Ollama không hoạt động hoặc không có embedding."""
    db_file = tmp_path / "test_hybrid_fallback.db"
    store = MemoryStore(db_path=db_file)

    store.add_memory(category="general", content="Người dùng thích lập trình Python")
    store.add_memory(category="project", content="Xây dựng ứng dụng Windows bằng Python")

    # Giả lập Ollama bị tắt (get_embedding_sync trả về None)
    with patch("assistant.memory.store.get_embedding_sync", return_value=None):
        results = store.search_memories_hybrid("Python", top_k=5)
        # Phải fallback mượt mà về FTS5 tìm được các bản ghi chứa từ khóa "Python"
        assert len(results) >= 1
        assert any("Python" in r["content"] for r in results)


def test_hybrid_search_empty_database_and_blank_query(tmp_path: Path) -> None:
    """Kiểm tra trường hợp truy vấn rỗng hoặc database chưa có dữ liệu."""
    db_file = tmp_path / "test_empty.db"
    store = MemoryStore(db_path=db_file)

    assert store.search_memories_hybrid("") == []
    assert store.search_memories_hybrid("   ") == []
    assert store.search_memories_hybrid("Bất kỳ từ khóa nào") == []


def test_memory_update_and_delete_syncs_embeddings(tmp_path: Path) -> None:
    """Kiểm tra sửa và xóa memory cũng đồng bộ cập nhật/xóa bảng memory_embeddings."""
    db_file = tmp_path / "test_sync_emb.db"
    store = MemoryStore(db_path=db_file)

    mem_id = store.add_memory(
        category="preference",
        content="Sở thích ban đầu",
        embedding=[0.1, 0.2, 0.3],
    )

    # Kiểm tra embedding đã lưu
    with store._get_connection() as conn:
        row = conn.execute("SELECT embedding FROM memory_embeddings WHERE memory_id = ?", (mem_id,)).fetchone()
        assert row is not None
        vec = blob_to_float_list(row["embedding"])
        assert abs(vec[0] - 0.1) < 1e-5

    # Cập nhật memory với embedding mới
    store.update_memory(
        memory_id=mem_id,
        content="Sở thích đã thay đổi",
        embedding=[0.7, 0.8, 0.9],
    )

    with store._get_connection() as conn:
        row_up = conn.execute("SELECT embedding FROM memory_embeddings WHERE memory_id = ?", (mem_id,)).fetchone()
        assert row_up is not None
        vec_up = blob_to_float_list(row_up["embedding"])
        assert abs(vec_up[0] - 0.7) < 1e-5

    # Xóa memory -> embedding cũng phải bị xóa
    store.delete_memory(mem_id)
    with store._get_connection() as conn:
        row_del = conn.execute("SELECT embedding FROM memory_embeddings WHERE memory_id = ?", (mem_id,)).fetchone()
        assert row_del is None


def test_context_get_relevant_memories_with_hybrid_search(tmp_path: Path) -> None:
    """Kiểm tra ConversationContext.get_relevant_memories nạp đúng trí nhớ qua hybrid search."""
    db_file = tmp_path / "test_ctx_hybrid.db"
    store = MemoryStore(db_path=db_file)

    m1 = store.add_memory(
        category="naming_rule",
        content="cách đặt file YYYY-MM-DD",
        embedding=[0.9, 0.1, 0.0],
    )
    store.add_memory(
        category="general",
        content="Thông tin không liên quan",
        embedding=[0.0, 0.9, 0.1],
    )

    ctx = ConversationContext()
    ctx.add_user_message("Quy tắc đặt tên file là gì?")

    with patch("assistant.memory.store.get_embedding_sync", return_value=[0.88, 0.12, 0.0]):
        relevant = ctx.get_relevant_memories(store, max_tokens=200)
        assert len(relevant) >= 1
        assert relevant[0]["id"] == m1
