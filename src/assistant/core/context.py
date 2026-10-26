"""Quản lý cửa sổ ngữ cảnh hội thoại theo ngân sách token.

Khi độ dài hội thoại vượt quá ngân sách token cấu hình, lớp Context sẽ tự động
kích hoạt tóm tắt phần lịch sử cũ (bằng model cục bộ) và bảo toàn các lượt trao đổi gần nhất.
"""

from typing import TYPE_CHECKING
from assistant.llm.base import Message

if TYPE_CHECKING:
    from assistant.llm.base import LLMProvider


def estimate_tokens(text: str | None) -> int:
    """Ước lượng số token của chuỗi văn bản (quy chuẩn xấp xỉ 3-4 ký tự = 1 token)."""
    if not text:
        return 0
    # Tiếng Việt có dấu thường chiếm nhiều byte hơn, tính trung bình 3 ký tự ~ 1 token
    return max(1, len(text) // 3)


def estimate_messages_tokens(messages: list[Message]) -> int:
    """Tính tổng số token ước lượng của danh sách tin nhắn."""
    total = 0
    for m in messages:
        total += 4  # Overhead cho metadata mỗi lượt tin nhắn
        total += estimate_tokens(m.content)
    return total


class ConversationContext:
    """Quản lý lịch sử hội thoại của phiên làm việc."""

    def __init__(
        self,
        max_tokens: int = 4000,
        keep_recent_turns: int = 4,
    ) -> None:
        self.max_tokens = max_tokens
        self.keep_recent_turns = keep_recent_turns
        self.messages: list[Message] = []
        self.summary: str | None = None

    def add_user_message(self, content: str) -> None:
        """Thêm tin nhắn của người dùng vào ngữ cảnh."""
        self.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Thêm tin nhắn phản hồi của trợ lý vào ngữ cảnh."""
        self.messages.append(Message(role="assistant", content=content))

    def add_message(self, message: Message) -> None:
        """Thêm một tin nhắn tổng quát vào ngữ cảnh."""
        self.messages.append(message)

    def clear(self) -> None:
        """Xoá sạch toàn bộ lịch sử và bản tóm tắt."""
        self.messages.clear()
        self.summary = None

    def get_messages_for_llm(self) -> list[Message]:
        """Tạo danh sách tin nhắn đã chèn bản tóm tắt (nếu có) để gửi tới LLM."""
        result: list[Message] = []
        if self.summary:
            result.append(
                Message(
                    role="user",
                    content=f"[TÓM TẮT LỊCH SỬ HỘI THOẠI TRƯỚC ĐÓ]\n{self.summary}",
                )
            )
            result.append(
                Message(
                    role="assistant",
                    content="Tôi đã nắm được toàn bộ nội dung tóm tắt từ các trao đổi trước đó. Tôi sẵn sàng hỗ trợ bạn tiếp tục.",
                )
            )
        result.extend(self.messages)
        return result

    def total_estimated_tokens(self) -> int:
        """Ước lượng tổng số token hiện tại của toàn bộ ngữ cảnh."""
        tokens = estimate_messages_tokens(self.messages)
        if self.summary:
            tokens += estimate_tokens(self.summary) + 20
        return tokens

    async def check_and_compress(self, local_provider: "LLMProvider | None" = None) -> bool:
        """Kiểm tra và nén lịch sử hội thoại nếu vượt quá ngân sách token.

        Returns:
            True nếu đã thực hiện tóm tắt/cắt giảm, False nếu chưa vượt ngưỡng.
        """
        current_tokens = self.total_estimated_tokens()
        if current_tokens <= self.max_tokens:
            return False

        # Số tin nhắn tối thiểu cần giữ lại (mỗi turn gồm user + assistant = 2 tin nhắn)
        min_keep_count = self.keep_recent_turns * 2
        if len(self.messages) <= min_keep_count:
            return False

        # Phân tách: các tin nhắn cũ cần tóm tắt và các tin nhắn gần nhất giữ nguyên
        older_messages = self.messages[:-min_keep_count]
        recent_messages = self.messages[-min_keep_count:]

        # Tạo chuỗi văn bản cần tóm tắt
        conversation_text_lines: list[str] = []
        if self.summary:
            conversation_text_lines.append(f"Tóm tắt trước đó: {self.summary}")

        for m in older_messages:
            sender = "Người dùng" if m.role == "user" else "Trợ lý"
            conversation_text_lines.append(f"{sender}: {m.content or ''}")

        text_to_summarize = "\n".join(conversation_text_lines)

        new_summary: str | None = None
        if local_provider:
            try:
                summary_prompt = [
                    Message(
                        role="user",
                        content=(
                            "Hãy tóm tắt ngắn gọn các ý chính, yêu cầu, tên file/thư mục và thông tin cốt lõi "
                            "trong đoạn hội thoại sau thành một đoạn văn súc tích bằng tiếng Việt:\n\n"
                            f"{text_to_summarize}"
                        ),
                    )
                ]
                summary_chunks: list[str] = []
                async for event in local_provider.stream_chat(
                    messages=summary_prompt,
                    system="Bạn là trợ lý tóm tắt thông tin chính xác, ngắn gọn.",
                ):
                    if event.type == "text_delta" and isinstance(event.content, str):
                        summary_chunks.append(event.content)

                generated_summary = "".join(summary_chunks).strip()
                if generated_summary:
                    new_summary = generated_summary
            except Exception:
                # Nếu model cục bộ gặp lỗi khi tóm tắt, dùng tóm tắt dự phòng
                new_summary = None

        if not new_summary:
            # Tóm tắt dự phòng đơn giản nếu không gọi được model
            new_summary = f"[Đã lưu trữ {len(older_messages)} lượt trao đổi cũ để tối ưu ngữ cảnh]"

        self.summary = new_summary
        self.messages = recent_messages
        return True
