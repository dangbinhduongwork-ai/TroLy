"""Giao diện mô hình ngôn ngữ lớn (LLM Provider) và định dạng dữ liệu nội bộ chuẩn hoá.

Tất cả các provider (Gemini, Ollama, hoặc mô hình sau này) bắt buộc phải chuyển đổi
qua lại giữa định dạng riêng của chúng và các schema Pydantic được định nghĩa tại đây.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Mô tả một lệnh gọi công cụ được sinh ra từ mô hình."""

    id: str = Field(..., description="Mã định danh duy nhất của lệnh gọi công cụ")
    name: str = Field(..., description="Tên công cụ cần thực thi")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Các tham số truyền vào công cụ")


class ToolResult(BaseModel):
    """Kết quả thực thi công cụ trả về cho mô hình."""

    tool_call_id: str = Field(..., description="ID của ToolCall tương ứng")
    content: str = Field(..., description="Kết quả dạng chuỗi")
    is_error: bool = Field(default=False, description="Đánh dấu nếu công cụ gặp lỗi")


class Message(BaseModel):
    """Tin nhắn hội thoại nội bộ chuẩn hoá."""

    role: Literal["user", "assistant", "system", "tool"] = Field(
        ..., description="Vai trò của người gửi"
    )
    content: str | None = Field(default=None, description="Nội dung văn bản")
    tool_calls: list[ToolCall] | None = Field(
        default=None, description="Danh sách lệnh gọi công cụ nếu có"
    )
    tool_call_id: str | None = Field(
        default=None, description="ID lệnh gọi công cụ nếu role là 'tool'"
    )
    name: str | None = Field(
        default=None, description="Tên công cụ/hàm nếu role là 'tool'"
    )


class Usage(BaseModel):
    """Thông tin sử dụng token của lượt hội thoại."""

    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)


StreamEventType = Literal["text_delta", "tool_call", "usage", "done", "error"]


class StreamEvent(BaseModel):
    """Sự kiện được phát ra trong luồng streaming bất đồng bộ."""

    type: StreamEventType = Field(..., description="Loại sự kiện")
    content: Any = Field(..., description="Dữ liệu đi kèm sự kiện")


ProviderErrorKind = Literal[
    "network",          # Lỗi kết nối mạng, rớt mạng, timeout
    "quota_429",        # Hết hạn mức request (Rate Limit / Quota Exceeded)
    "server_5xx",       # Lỗi máy chủ phía nhà cung cấp (500, 503, Overloaded)
    "auth",             # Sai hoặc thiếu API key (401, 403)
    "content_blocked",  # Vi phạm chính sách an toàn, nội dung bị chặn
    "unknown",          # Lỗi không xác định khác
]


class ProviderError(Exception):
    """Ngoại lệ chuẩn hoá cho các lỗi phát sinh từ LLM Provider."""

    def __init__(
        self,
        kind: ProviderErrorKind,
        message: str,
        raw_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.raw_error = raw_error

    def __str__(self) -> str:
        return f"[{self.kind.upper()}] {self.message}"


class LLMProvider(ABC):
    """Lớp giao diện cơ sở cho tất cả các nhà cung cấp mô hình ngôn ngữ."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Tên định danh của provider (ví dụ: 'gemini', 'ollama')."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Tên model mặc định được cấu hình cho provider."""
        ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Truyền phát luồng hội thoại bất đồng bộ."""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """Liệt kê danh sách các model khả dụng từ provider này."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Kiểm tra nhanh xem provider có sẵn sàng nhận request hay không."""
        ...
