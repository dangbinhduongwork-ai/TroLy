"""Trích xuất và cập nhật trí nhớ dài hạn từ nội dung hội thoại (Memory Extractor).

Tuân thủ:
- Trích xuất tự động các dữ kiện: sở thích (preference), dự án (project), quy tắc đặt tên (naming_rule), thông tin chung (general).
- Nguyên tắc an toàn: Nếu hội thoại nhạy cảm (is_sensitive=True), BẮT BUỘC dùng model cục bộ (Ollama), tuyệt đối không gửi dữ liệu lên Gemini.
- Chống trùng lặp: Tìm kiếm các mục tương tự trước khi lưu; nếu đã tồn tại thì cập nhật thay vì tạo bản ghi rác.
"""

import json
import re
from typing import Any

from assistant.core.router import ModelRouter
from assistant.llm.base import Message
from assistant.memory.store import MemoryStore

EXTRACTION_SYSTEM_PROMPT = """Bạn là hệ thống trích xuất trí nhớ dài hạn (Long-Term Memory Extractor) cho Trợ Lý AI.
Nhiệm vụ: Đọc lượt hội thoại của người dùng và trích xuất các dữ kiện, thói quen, thông tin quan trọng cần nhớ cho các phiên làm việc sau.

Chỉ trích xuất các thông tin thuộc 4 nhóm sau:
1. "preference": Sở thích, thói quen cá nhân (ví dụ: thích dùng dark mode, thích viết code súc tích).
2. "project": Dự án đang làm, công nghệ hoặc mục tiêu công việc của người dùng.
3. "naming_rule": Quy tắc đặt tên file, thư mục, hàm, biến (ví dụ: đặt tên file theo mẫu YYYY-MM-DD_ten-file).
4. "general": Thông tin cá nhân cơ bản (tên, vai trò, ngữ cảnh chung).

ĐỊNH DẠNG ĐẦU RA:
- Bắt buộc trả về duy nhất một mảng JSON thuần túy (không kèm markdown, không giải thích):
  [{"category": "naming_rule", "content": "Quy tắc đặt tên file báo cáo theo mẫu YYYY-MM-DD_ten-bao-cao"}]
- Nếu không có thông tin nào đáng nhớ lâu dài, trả về mảng rỗng: []
"""

TRIGGER_KEYWORDS = [
    "hãy nhớ",
    "ghi nhớ",
    "nhớ là",
    "nhớ giúp",
    "quy tắc",
    "sở thích",
    "tôi thích",
    "tôi muốn",
    "dự án",
    "tên tôi",
    "tên tôi là",
    "thói quen",
    "lưu ý rằng",
]


def _has_memory_signal(text: str) -> bool:
    """Kiểm tra nhanh xem câu thoại có chứa tín hiệu cần ghi nhớ hay không."""
    lower_text = text.lower()
    return any(kw in lower_text for kw in TRIGGER_KEYWORDS)


def _clean_json_response(raw_text: str) -> list[dict[str, str]]:
    """Làm sạch chuỗi phản hồi từ LLM và phân tích thành danh sách JSON."""
    text = raw_text.strip()
    # Loại bỏ code block markdown nếu model bao bọc ```json ... ```
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            valid_items = []
            for item in data:
                if isinstance(item, dict) and "category" in item and "content" in item:
                    cat = str(item["category"]).strip().lower()
                    if cat not in ("preference", "project", "naming_rule", "general"):
                        cat = "general"
                    valid_items.append({"category": cat, "content": str(item["content"]).strip()})
            return valid_items
    except Exception:
        pass
    return []


async def extract_and_store_memories(
    user_message: str,
    assistant_response: str,
    store: MemoryStore,
    router: ModelRouter,
    is_sensitive: bool = False,
    source_conv_id: str | None = None,
    force_extract: bool = False,
) -> list[dict[str, Any]]:
    """Trích xuất thông tin đáng nhớ và lưu/cập nhật vào SQLite với chống trùng lặp."""
    # Nếu không có từ khóa tín hiệu và không ép buộc -> bỏ qua để tiết kiệm token
    if not force_extract and not _has_memory_signal(user_message):
        return []

    prompt_messages = [
        Message(
            role="user",
            content=(
                f"Người dùng nói: {user_message}\n"
                f"Trợ lý trả lời: {assistant_response}\n\n"
                "Hãy trích xuất các dữ kiện cần nhớ lâu dài của người dùng:"
            ),
        )
    ]

    extracted_text_chunks: list[str] = []

    # QUY TẮC AN TOÀN: Nếu nhạy cảm -> BẮT BUỘC gọi trực tiếp Ollama cục bộ, cấm gửi lên Gemini
    if is_sensitive:
        provider = router.ollama_provider
    else:
        provider = router.gemini_provider if router.mode == "gemini" else router.ollama_provider

    try:
        async for event in provider.stream_chat(
            messages=prompt_messages,
            system=EXTRACTION_SYSTEM_PROMPT,
        ):
            if event.type == "text_delta" and isinstance(event.content, str):
                extracted_text_chunks.append(event.content)
    except Exception:
        # Nếu model chính lỗi, thử gọi model cục bộ dự phòng
        if not is_sensitive:
            try:
                async for event in router.ollama_provider.stream_chat(
                    messages=prompt_messages,
                    system=EXTRACTION_SYSTEM_PROMPT,
                ):
                    if event.type == "text_delta" and isinstance(event.content, str):
                        extracted_text_chunks.append(event.content)
            except Exception:
                return []
        else:
            return []

    raw_output = "".join(extracted_text_chunks).strip()
    memories_data = _clean_json_response(raw_output)

    results: list[dict[str, Any]] = []

    for item in memories_data:
        cat = item["category"]
        content = item["content"]
        if not content:
            continue

        # Chống trùng lặp: Tìm kiếm các mục hiện có trong cùng category
        existing_matches = store.search_memories(content[:25])
        matched_id: str | None = None

        for em in existing_matches:
            if em["category"] == cat:
                # Nếu độ tương đồng cao hoặc có chung từ khóa chính -> xem như trùng lặp và cập nhật
                matched_id = em["id"]
                break

        if matched_id:
            # Cập nhật bản ghi cũ thay vì tạo bản ghi rác
            store.update_memory(matched_id, content=content, category=cat)
            results.append({"id": matched_id, "action": "updated", "category": cat, "content": content})
        else:
            # Tạo bản ghi mới
            new_id = store.add_memory(category=cat, content=content, source_conv_id=source_conv_id)
            results.append({"id": new_id, "action": "created", "category": cat, "content": content})

    return results
