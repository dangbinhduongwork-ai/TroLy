"""Kiểm thử tự động cho việc chuyển đổi định dạng tin nhắn và phân loại lỗi của các LLM Provider."""

from assistant.llm.base import (
    Message,
    StreamEvent,
    ToolCall,
    ToolResult,
    Usage,
)
from assistant.llm.gemini_provider import classify_gemini_error


def test_classify_gemini_errors() -> None:
    """Kiểm tra phân loại chính xác các mã lỗi và thông báo lỗi từ Gemini SDK."""
    # 1. Lỗi mạng
    net_err = Exception("Failed to connect to host: dns resolution failed or socket timeout")
    classified_net = classify_gemini_error(net_err)
    assert classified_net.kind == "network"
    assert "kết nối" in classified_net.message

    # 2. Hết hạn mức 429
    quota_err = Exception("429 ResourceExhausted: Quota exceeded for quota metric")
    classified_quota = classify_gemini_error(quota_err)
    assert classified_quota.kind == "quota_429"
    assert "hạn mức" in classified_quota.message

    # 3. Lỗi xác thực / Sai key
    auth_err = Exception("403 Forbidden: API_KEY_INVALID or permission denied")
    classified_auth = classify_gemini_error(auth_err)
    assert classified_auth.kind == "auth"
    assert "assistant set-key" in classified_auth.message

    # 4. Lỗi máy chủ 500 / 503
    server_err = Exception("503 Service Unavailable: The model is overloaded")
    classified_server = classify_gemini_error(server_err)
    assert classified_server.kind == "server_5xx"
    assert "Máy chủ Google Gemini" in classified_server.message

    # 5. Nội dung bị bộ lọc an toàn chặn
    safety_err = Exception("Generation stopped: safety policy violation")
    classified_safety = classify_gemini_error(safety_err)
    assert classified_safety.kind == "content_blocked"
    assert "bộ lọc an toàn" in classified_safety.message


def test_pydantic_message_and_event_schemas() -> None:
    """Kiểm tra schema Message, ToolCall, ToolResult và StreamEvent."""
    tool_call = ToolCall(id="call_123", name="open_app", arguments={"app_name": "notepad"})
    assert tool_call.name == "notepad" or tool_call.arguments["app_name"] == "notepad"

    tool_result = ToolResult(tool_call_id="call_123", content="Đã mở notepad")
    assert not tool_result.is_error

    user_msg = Message(role="user", content="Mở notepad giúp tôi")
    assistant_msg = Message(role="assistant", content=None, tool_calls=[tool_call])
    tool_msg = Message(role="tool", content=tool_result.content, tool_call_id="call_123")

    assert user_msg.role == "user"
    assert assistant_msg.tool_calls is not None
    assert len(assistant_msg.tool_calls) == 1
    assert tool_msg.tool_call_id == "call_123"

    event = StreamEvent(type="text_delta", content="Xin chào")
    assert event.type == "text_delta"

    usage_event = StreamEvent(
        type="usage",
        content=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )
    assert usage_event.content.total_tokens == 30
