"""Module xử lý Vector Embeddings và thuật toán tương đồng Cosine thuần Python.

Tuân thủ Nguyên tắc 11:
- Sử dụng module chuẩn `math` và `struct` để tính toán Cosine Similarity và mã hóa vector nhị phân float32.
- Tuyệt đối không cài đặt thêm numpy, scipy, chromadb hay faiss.
- Sử dụng `httpx` kết nối tới endpoint `/api/embeddings` của Ollama (model nhẹ: nomic-embed-text, all-minilm).
- Triển khai thuật toán Reciprocal Rank Fusion (RRF) để kết hợp FTS5 BM25 và Vector Similarity.
"""

import logging
import math
import struct
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def float_list_to_blob(vector: list[float]) -> bytes:
    """Chuyển đổi danh sách số thực float thành chuỗi byte nhị phân float32 (BLOB)."""
    if not vector:
        return b""
    # 'f' đại diện cho single-precision float (32-bit, 4 bytes/phần tử)
    return struct.pack(f"{len(vector)}f", *vector)


def blob_to_float_list(blob: bytes) -> list[float]:
    """Chuyển đổi chuỗi byte nhị phân float32 (BLOB) thành danh sách số thực float."""
    if not blob:
        return []
    count = len(blob) // 4
    if count == 0:
        return []
    return list(struct.unpack(f"{count}f", blob[: count * 4]))


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Tính độ tương đồng Cosine giữa hai vector thuần Python bằng math.

    Cosine Similarity = (A . B) / (||A|| * ||B||)
    Trả về giá trị trong khoảng [-1.0, 1.0]. Nếu vector rỗng hoặc độ dài không khớp, trả về 0.0.
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    sim = dot / (norm1 * norm2)
    # Kẹp giá trị trong khoảng [-1.0, 1.0] để tránh lỗi sai số dấu phẩy động
    return max(-1.0, min(1.0, sim))


def get_embedding_sync(
    prompt: str,
    host: str = "http://127.0.0.1:11434",
    model: str = "nomic-embed-text",
    timeout: float = 3.0,
) -> list[float] | None:
    """Lấy vector embedding từ endpoint Ollama /api/embeddings (chế độ đồng bộ).

    Args:
        prompt: Chuỗi văn bản cần sinh embedding.
        host: Địa chỉ máy chủ Ollama (mặc định http://127.0.0.1:11434).
        model: Tên mô hình embedding (mặc định nomic-embed-text).
        timeout: Thời gian chờ tối đa (giây).

    Returns:
        Danh sách các phần tử float32 biểu diễn vector, hoặc None nếu thất bại.
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return None

    url = f"{host.rstrip('/')}/api/embeddings"
    payload = {"model": model, "prompt": clean_prompt}

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                emb = data.get("embedding")
                if isinstance(emb, list) and emb:
                    return [float(x) for x in emb]

            logger.debug(
                "Ollama embeddings trả về mã HTTP %s: %s",
                resp.status_code,
                resp.text[:120],
            )
            return None
    except httpx.ConnectError:
        logger.debug("Không thể kết nối tới Ollama tại %s (máy chủ chưa bật).", host)
        return None
    except httpx.TimeoutException:
        logger.debug("Hết thời gian chờ sinh embedding từ Ollama (%ss).", timeout)
        return None
    except Exception as exc:
        logger.debug("Lỗi không xác định khi sinh embedding Ollama: %s", exc)
        return None


async def get_embedding_async(
    prompt: str,
    host: str = "http://127.0.0.1:11434",
    model: str = "nomic-embed-text",
    timeout: float = 3.0,
) -> list[float] | None:
    """Lấy vector embedding từ endpoint Ollama /api/embeddings (chế độ bất đồng bộ)."""
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return None

    url = f"{host.rstrip('/')}/api/embeddings"
    payload = {"model": model, "prompt": clean_prompt}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                emb = data.get("embedding")
                if isinstance(emb, list) and emb:
                    return [float(x) for x in emb]

            logger.debug(
                "Ollama embeddings async trả về mã HTTP %s: %s",
                resp.status_code,
                resp.text[:120],
            )
            return None
    except httpx.ConnectError:
        logger.debug("Không thể kết nối tới Ollama tại %s (máy chủ chưa bật).", host)
        return None
    except httpx.TimeoutException:
        logger.debug("Hết thời gian chờ sinh embedding từ Ollama (%ss).", timeout)
        return None
    except Exception as exc:
        logger.debug("Lỗi không xác định khi sinh embedding Ollama async: %s", exc)
        return None


def reciprocal_rank_fusion(
    ranking_lists: list[list[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Kết hợp các danh sách kết quả bằng thuật toán Reciprocal Rank Fusion (RRF).

    Điểm số RRF cho mỗi mục d:
        RRF(d) = sum( 1 / (k + rank_m(d)) ) với mỗi danh sách m chứa d.
    Trong đó:
        - k: Hằng số làm mịn (thông lệ 60).
        - rank_m(d): Vị trí xếp hạng của d trong danh sách m (bắt đầu từ 1).

    Args:
        ranking_lists: Danh sách các danh sách ID mục (đã được xếp hạng tốt nhất trước).
        k: Hằng số điều hòa làm mịn rank (mặc định 60).

    Returns:
        Danh sách tuple (item_id, rrf_score) được sắp xếp giảm dần theo điểm.
    """
    scores: dict[str, float] = {}

    for r_list in ranking_lists:
        for rank, item_id in enumerate(r_list, start=1):
            if not item_id:
                continue
            scores[item_id] = scores.get(item_id, 0.0) + (1.0 / (k + rank))

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
