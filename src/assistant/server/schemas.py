"""Định nghĩa các cấu trúc dữ liệu Pydantic cho REST API và WebSocket (Server Schemas).

Tuân thủ:
- Xác thực dữ liệu đầu vào và chuẩn hoá định dạng đầu ra.
- Hỗ trợ các màn hình: Trò chuyện, Trí nhớ dài hạn, Nhắc việc, và Trạng thái hệ thống.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


# =============================================================================
# TRẠNG THÁI HỆ THỐNG (SYSTEM STATUS)
# =============================================================================

class StatusResponse(BaseModel):
    """Thông tin trạng thái hoạt động của hệ thống Trợ Lý AI."""

    gemini_configured: bool = Field(description="Đã cấu hình API key Gemini chưa")
    gemini_reachable: bool = Field(description="Kết nối tới máy chủ Gemini bình thường không")
    ollama_running: bool = Field(description="Máy chủ Ollama cục bộ đang chạy không")
    current_model: str = Field(description="Tên mô hình hiện tại đang được sử dụng")
    gemini_model: str = Field(description="Tên mô hình Gemini được cấu hình")
    local_model: str = Field(description="Tên mô hình Ollama cục bộ được cấu hình")
    daily_requests_count: int = Field(default=0, description="Số request Gemini đã dùng hôm nay")
    daily_soft_limit: int = Field(description="Ngưỡng cảnh báo request Gemini hàng ngày")
    workspace_dir: str = Field(description="Đường dẫn thư mục làm việc an toàn")
    scheduler_running: bool = Field(description="Trạng thái bộ lập lịch nhắc việc APScheduler")


# =============================================================================
# HỘI THOẠI & TIN NHẮN (CONVERSATIONS & MESSAGES)
# =============================================================================

class ConversationCreate(BaseModel):
    """Yêu cầu tạo cuộc hội thoại mới."""

    title: str = Field(default="Cuộc trò chuyện mới", description="Tiêu đề cuộc hội thoại")
    is_sensitive: bool = Field(default=False, description="Chế độ bảo mật nhạy cảm (chỉ xử lý cục bộ)")


class ConversationUpdate(BaseModel):
    """Yêu cầu đổi tiêu đề hoặc chế độ nhạy cảm của cuộc hội thoại."""

    title: str | None = None
    is_sensitive: bool | None = None


class ConversationItem(BaseModel):
    """Thông tin tóm tắt của một cuộc hội thoại."""

    id: str
    title: str
    created_at: str
    updated_at: str
    is_sensitive: bool
    last_message: str | None = None


class MessageItem(BaseModel):
    """Chi tiết một tin nhắn trong cuộc hội thoại."""

    id: str
    conversation_id: str
    role: str
    content: str | None
    model_used: str | None = None
    tool_calls_json: str | None = None
    created_at: str


# =============================================================================
# TRÍ NHỚ DÀI HẠN (MEMORIES)
# =============================================================================

class MemoryCreate(BaseModel):
    """Yêu cầu thêm dữ kiện mới vào trí nhớ dài hạn."""

    category: str = Field(default="general", description="Danh mục: preference, project, naming_rule, general")
    content: str = Field(..., min_length=1, description="Nội dung cần ghi nhớ")


class MemoryUpdate(BaseModel):
    """Yêu cầu sửa đổi một mục trí nhớ."""

    content: str | None = None
    category: str | None = None


class MemoryItem(BaseModel):
    """Một mục dữ kiện trong trí nhớ dài hạn."""

    id: str
    category: str
    content: str
    source_conv_id: str | None = None
    created_at: str
    updated_at: str


# =============================================================================
# LỜI NHẮC VIỆC (REMINDERS)
# =============================================================================

class ReminderCreate(BaseModel):
    """Yêu cầu tạo lời nhắc việc mới."""

    message: str = Field(..., min_length=1, description="Nội dung lời nhắc việc")
    trigger_at: str = Field(..., description="Thời gian kích hoạt ISO 8601 kèm timezone")
    cron_expr: str | None = Field(default=None, description="Biểu thức cron lặp lại")


class ReminderSnooze(BaseModel):
    """Yêu cầu hoãn lời nhắc thêm N phút."""

    minutes: int = Field(default=10, ge=1, le=1440, description="Số phút hoãn")


class ReminderItem(BaseModel):
    """Thông tin chi tiết một lời nhắc việc."""

    id: str
    message: str
    trigger_at: str
    cron_expr: str | None = None
    status: str
    created_at: str


# =============================================================================
# GIAO THỨC WEBSOCKET (WEBSOCKET PROTOCOL)
# =============================================================================

ClientActionType = Literal["user_message", "approval_response", "cancel"]


class WSClientMessage(BaseModel):
    """Tin nhắn gửi từ giao diện web UI lên máy chủ WebSocket."""

    type: ClientActionType
    message: str | None = None
    conversation_id: str | None = None
    mode: Literal["auto", "gemini", "local"] = "auto"
    is_sensitive: bool = False
    request_id: str | None = None
    approved: bool | None = None


ServerEventType = Literal[
    "text_delta",
    "tool_start",
    "approval_required",
    "tool_result",
    "model_switched",
    "turn_done",
    "error",
]


class WSServerEvent(BaseModel):
    """Sự kiện gửi từ máy chủ WebSocket xuống giao diện web UI."""

    type: ServerEventType
    data: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# CÀI ĐẶT & CHẨN ĐOÁN (SETTINGS & DIAGNOSTICS)
# =============================================================================

class KeyUpdateRequest(BaseModel):
    """Yêu cầu cập nhật Gemini API Key lưu an toàn vào Windows Credential Manager."""

    api_key: str = Field(min_length=1, description="Khóa Gemini API Key mới")


class GeminiKeyItem(BaseModel):
    """Thông tin một Gemini API Key hiển thị an toàn trên giao diện."""

    id: str
    name: str
    masked_key: str
    created_at: str
    is_active: bool


class GeminiKeysResponse(BaseModel):
    """Danh sách các Gemini API Keys đã lưu."""

    ok: bool = True
    keys: list[GeminiKeyItem] = Field(default_factory=list)
    active_id: str | None = None


class GeminiKeyCreateRequest(BaseModel):
    """Yêu cầu thêm Gemini API Key mới."""

    api_key: str = Field(min_length=1, description="Khóa Gemini API Key mới")
    name: str | None = Field(default="", description="Tên gợi nhớ cho khóa")


class GeminiKeyUpdateRequest(BaseModel):
    """Yêu cầu cập nhật Gemini API Key đã lưu (tên hoặc giá trị khóa)."""

    api_key: str | None = Field(default=None, description="Khóa Gemini API Key mới nếu muốn đổi")
    name: str | None = Field(default=None, description="Tên gợi nhớ mới cho khóa")


class GeminiKeyTestRequest(BaseModel):
    """Yêu cầu kiểm tra kết nối của một API Key."""

    api_key: str | None = Field(default=None, description="Khóa API Key thô để kiểm tra")
    key_id: str | None = Field(default=None, description="ID của khóa đã lưu cần kiểm tra")


class ModelModeUpdateRequest(BaseModel):
    """Yêu cầu thay đổi chế độ định tuyến model."""

    mode: Literal["auto", "gemini", "local"] = Field(description="Chế độ định tuyến model")


class AutostartUpdateRequest(BaseModel):
    """Yêu cầu bật/tắt tự khởi động cùng Windows."""

    enabled: bool = Field(description="Bật hoặc tắt tự khởi động cùng Windows")


class HotkeyUpdateRequest(BaseModel):
    """Yêu cầu bật/tắt phím tắt toàn cục Spotlight Mode."""

    enabled: bool = Field(description="Bật hoặc tắt phím tắt toàn cục")


class FileUploadResponse(BaseModel):
    """Kết quả tải tệp tin lên Workspace an toàn."""

    ok: bool
    filename: str
    path: str
    size: int
    message: str


class DiagnosticsResponse(BaseModel):
    """Kết quả chẩn đoán toàn diện hệ thống phục vụ trang Cài đặt & Chẩn đoán."""

    gemini_configured: bool
    gemini_key_source: str
    gemini_reachable: bool
    ollama_running: bool
    ollama_models: list[str] = Field(default_factory=list)
    mode: str
    gemini_model: str
    gemini_models: list[str] = Field(default_factory=list)
    local_model: str
    autostart_enabled: bool
    workspace_dir: str
    timezone: str

