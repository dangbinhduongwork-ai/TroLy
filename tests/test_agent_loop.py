"""Kiểm thử tự động cho Agent Loop (core/agent_loop.py) với Mock Provider."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
import pytest

from assistant.config import Config
from assistant.core.agent_loop import AgentLoop
from assistant.core.context import ConversationContext
from assistant.core.router import ModelRouter
from assistant.llm.base import (
    LLMProvider,
    Message,
    StreamEvent,
    ToolCall,
)
from assistant.safety.audit import AuditLogger
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import ToolRegistry


class StepMockProvider(LLMProvider):
    """Provider giả lập sinh ra chuỗi các phản hồi theo kịch bản kiểm thử."""

    def __init__(self, turns_sequence: list[list[StreamEvent]]) -> None:
        self.turns_sequence = turns_sequence
        self.current_turn = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-model"

    async def list_models(self) -> list[str]:
        return ["mock-model"]

    async def is_available(self) -> bool:
        return True

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        if self.current_turn < len(self.turns_sequence):
            events = self.turns_sequence[self.current_turn]
            self.current_turn += 1
            for e in events:
                yield e
        else:
            yield StreamEvent(type="text_delta", content="Không còn sự kiện giả lập.")
            yield StreamEvent(type="done", content={"finish_reason": "stop"})


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    return Config(
        workspace_dir=tmp_path / "ws",
        data_dir=tmp_path / "data",
        timezone="Asia/Ho_Chi_Minh",
        gemini_model="gemini-2.5-flash",
        local_model="qwen2.5:7b",
        ollama_host="http://127.0.0.1:11434",
        daily_soft_limit=1000,
        max_context_tokens=4000,
        network_cache_seconds=10,
        ui_port=8000,
        log_level="INFO",
    )


@pytest.mark.asyncio
async def test_agent_loop_single_tool_execution(test_config: Config) -> None:
    """Kiểm tra luồng gọi công cụ đơn bước: Model gọi tool -> tool chạy -> Model trả lời kết quả."""
    registry = ToolRegistry()

    @registry.register(name="mock_calculator", permission_level=PermissionLevel.READ)
    def mock_calc(a: int, b: int) -> dict:
        return {"ok": True, "data": a + b, "error": None, "truncated": False}

    # Kịch bản:
    # Lượt 1: Model phát ra tool_call "mock_calculator" với a=5, b=10
    # Lượt 2: Model nhận kết quả và phát ra câu trả lời cuối cùng
    turn1_events = [
        StreamEvent(
            type="tool_call",
            content=ToolCall(id="c1", name="mock_calculator", arguments={"a": 5, "b": 10}),
        ),
        StreamEvent(type="done", content={"finish_reason": "tool_calls"}),
    ]
    turn2_events = [
        StreamEvent(type="text_delta", content="Kết quả phép tính là 15."),
        StreamEvent(type="done", content={"finish_reason": "stop"}),
    ]

    mock_provider = StepMockProvider([turn1_events, turn2_events])
    router = ModelRouter(
        config=test_config,
        gemini_provider=mock_provider,
        ollama_provider=mock_provider,
    )
    router.set_mode("gemini")

    audit = AuditLogger(test_config.data_dir)
    loop = AgentLoop(
        router=router,
        registry=registry,
        audit_logger=audit,
        approval_callback=lambda name, args, reason: True,
    )

    context = ConversationContext()
    context.add_user_message("Tính 5 + 10 giúp tôi")

    received_text: list[str] = []
    async for event in loop.run_turn(context=context, system_prompt="Test"):
        if event.type == "text_delta" and isinstance(event.content, str):
            received_text.append(event.content)

    full_output = "".join(received_text)
    assert "Kết quả phép tính là 15." in full_output
    assert len(context.messages) >= 3  # user -> assistant(tool_call) -> tool_result -> assistant(text)


@pytest.mark.asyncio
async def test_agent_loop_detects_infinite_loop(test_config: Config) -> None:
    """Kiểm tra phát hiện và ngắt vòng lặp vô tận khi model gọi lặp lại 1 công cụ 3 lần."""
    registry = ToolRegistry()

    @registry.register(name="loop_tool", permission_level=PermissionLevel.READ)
    def loop_tool(param: str) -> dict:
        return {"ok": True, "data": "output", "error": None, "truncated": False}

    # Kịch bản: Model liên tục gọi loop_tool với cùng tham số
    repeated_events = [
        StreamEvent(
            type="tool_call",
            content=ToolCall(id=f"c{i}", name="loop_tool", arguments={"param": "same"}),
        ),
        StreamEvent(type="done", content={"finish_reason": "tool_calls"}),
    ]

    mock_provider = StepMockProvider([repeated_events, repeated_events, repeated_events, repeated_events])
    router = ModelRouter(
        config=test_config,
        gemini_provider=mock_provider,
        ollama_provider=mock_provider,
    )
    router.set_mode("gemini")

    loop = AgentLoop(
        router=router,
        registry=registry,
        approval_callback=lambda name, args, reason: True,
    )

    context = ConversationContext()
    context.add_user_message("Lặp lại")

    output_chunks: list[str] = []
    async for event in loop.run_turn(context=context, system_prompt="Test"):
        if event.type == "text_delta" and isinstance(event.content, str):
            output_chunks.append(event.content)

    combined = "".join(output_chunks)
    assert "DỪNG AN TOÀN" in combined or "vòng lặp vô tận" in combined


@pytest.mark.asyncio
async def test_agent_loop_user_rejection(test_config: Config) -> None:
    """Kiểm tra khi người dùng từ chối phê duyệt công cụ CONFIRM."""
    registry = ToolRegistry()

    @registry.register(name="dangerous_action", permission_level=PermissionLevel.CONFIRM)
    def dangerous_action() -> dict:
        return {"ok": True, "data": "done", "error": None, "truncated": False}

    turn1 = [
        StreamEvent(
            type="tool_call",
            content=ToolCall(id="c1", name="dangerous_action", arguments={}),
        ),
        StreamEvent(type="done", content={"finish_reason": "tool_calls"}),
    ]
    turn2 = [
        StreamEvent(type="text_delta", content="Tôi hiểu bạn không đồng ý."),
        StreamEvent(type="done", content={"finish_reason": "stop"}),
    ]

    mock_provider = StepMockProvider([turn1, turn2])
    router = ModelRouter(
        config=test_config,
        gemini_provider=mock_provider,
        ollama_provider=mock_provider,
    )
    router.set_mode("gemini")

    # Callback từ chối
    loop = AgentLoop(
        router=router,
        registry=registry,
        approval_callback=lambda name, args, reason: False,  # Từ chối duyệt
    )

    context = ConversationContext()
    context.add_user_message("Chạy hành động nguy hiểm")

    output_chunks: list[str] = []
    async for event in loop.run_turn(context=context, system_prompt="Test"):
        if event.type == "text_delta" and isinstance(event.content, str):
            output_chunks.append(event.content)

    combined = "".join(output_chunks)
    assert "từ chối" in combined
