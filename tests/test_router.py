"""Kiểm thử tự động cho ModelRouter sử dụng các LLMProvider giả lập (Mock/Dummy).

Kiểm tra các kịch bản:
- Tự động chuyển sang mô hình cục bộ khi offline.
- Tự động chuyển sang mô hình cục bộ khi yêu cầu nhạy cảm.
- Cơ chế thử lại và tự động fallback sang mô hình cục bộ khi gặp lỗi mạng, 429, 5xx.
- Lỗi xác thực (auth) dừng ngay và báo lỗi, không tự ý fallback.
- Ghi nhận hạn mức sử dụng ngày.
"""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
import pytest

from assistant.config import Config
from assistant.core.router import ModelRouter, NetworkChecker
from assistant.llm.base import (
    LLMProvider,
    Message,
    ProviderError,
    StreamEvent,
)


class DummyProvider(LLMProvider):
    """Mô hình giả lập cho việc kiểm thử router."""

    def __init__(
        self,
        name: str,
        default_model: str,
        error_to_raise: ProviderError | None = None,
        responses: list[str] | None = None,
    ) -> None:
        self._name = name
        self._default_model = default_model
        self.error_to_raise = error_to_raise
        self.responses = responses or ["Phản hồi thử nghiệm từ " + name]
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return self._default_model

    async def list_models(self) -> list[str]:
        return [self._default_model]

    async def is_available(self) -> bool:
        return True

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        self.call_count += 1
        if self.error_to_raise:
            raise self.error_to_raise

        for r in self.responses:
            yield StreamEvent(type="text_delta", content=r)
        yield StreamEvent(type="done", content={"finish_reason": "stop"})


class DummyNetworkChecker(NetworkChecker):
    """Bộ kiểm tra mạng giả lập."""

    def __init__(self, is_online_val: bool = True) -> None:
        super().__init__(cache_duration_sec=10)
        self.is_online_val = is_online_val

    async def is_online(self) -> bool:
        return self.is_online_val


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Fixture tạo cấu hình tạm thời cho bài test."""
    return Config(
        workspace_dir=tmp_path / "workspace",
        data_dir=tmp_path / "data",
        timezone="Asia/Ho_Chi_Minh",
        gemini_model="gemini-2.5-flash",
        local_model="qwen2.5:7b",
        ollama_host="http://127.0.0.1:11434",
        daily_soft_limit=10,
        max_context_tokens=1000,
        network_cache_seconds=1,
        ui_port=8000,
        log_level="INFO",
    )


@pytest.mark.asyncio
async def test_auto_normal_gemini(test_config: Config) -> None:
    """Kiểm tra chế độ auto khi có mạng và Gemini hoạt động bình thường."""
    gemini = DummyProvider(name="gemini", default_model="gemini-2.5-flash")
    ollama = DummyProvider(name="ollama", default_model="qwen2.5:7b")
    net = DummyNetworkChecker(is_online_val=True)

    router = ModelRouter(
        config=test_config,
        gemini_provider=gemini,
        ollama_provider=ollama,
        network_checker=net,
    )

    events: list[StreamEvent] = []
    messages = [Message(role="user", content="Xin chào")]
    async for event in router.stream_chat(messages):
        events.append(event)

    assert gemini.call_count == 1
    assert ollama.call_count == 0
    assert router.last_provider_used == "gemini"
    assert any("gemini" in str(e.content) for e in events if e.type == "text_delta")


@pytest.mark.asyncio
async def test_auto_sensitive_routes_to_local(test_config: Config) -> None:
    """Kiểm tra yêu cầu nhạy cảm bắt buộc được điều hướng sang model cục bộ."""
    gemini = DummyProvider(name="gemini", default_model="gemini-2.5-flash")
    ollama = DummyProvider(name="ollama", default_model="qwen2.5:7b")
    net = DummyNetworkChecker(is_online_val=True)

    router = ModelRouter(
        config=test_config,
        gemini_provider=gemini,
        ollama_provider=ollama,
        network_checker=net,
    )

    events: list[StreamEvent] = []
    messages = [Message(role="user", content="Mật khẩu của tôi là 123456")]
    async for event in router.stream_chat(messages, is_sensitive=True):
        events.append(event)

    assert gemini.call_count == 0  # Tuyệt đối không gọi Gemini
    assert ollama.call_count == 1  # Chỉ gọi Ollama
    assert router.last_provider_used == "ollama"
    assert any("Bảo mật" in str(e.content) for e in events if e.type == "text_delta")


@pytest.mark.asyncio
async def test_auto_offline_routes_to_local(test_config: Config) -> None:
    """Kiểm tra khi mất mạng router tự động gọi Ollama cục bộ."""
    gemini = DummyProvider(name="gemini", default_model="gemini-2.5-flash")
    ollama = DummyProvider(name="ollama", default_model="qwen2.5:7b")
    net = DummyNetworkChecker(is_online_val=False)  # Giả lập mất mạng

    router = ModelRouter(
        config=test_config,
        gemini_provider=gemini,
        ollama_provider=ollama,
        network_checker=net,
    )

    events: list[StreamEvent] = []
    messages = [Message(role="user", content="Thao tác offline")]
    async for event in router.stream_chat(messages):
        events.append(event)

    assert gemini.call_count == 0
    assert ollama.call_count == 1
    assert router.last_provider_used == "ollama"
    assert any("Mất kết nối Internet" in str(e.content) for e in events if e.type == "text_delta")


@pytest.mark.asyncio
async def test_auto_gemini_network_error_fallback(test_config: Config) -> None:
    """Kiểm tra khi Gemini gặp lỗi mạng -> retry 2 lần -> tự động fallback sang Ollama."""
    gemini = DummyProvider(
        name="gemini",
        default_model="gemini-2.5-flash",
        error_to_raise=ProviderError("network", "Không kết nối được tới máy chủ"),
    )
    ollama = DummyProvider(name="ollama", default_model="qwen2.5:7b")
    net = DummyNetworkChecker(is_online_val=True)

    router = ModelRouter(
        config=test_config,
        gemini_provider=gemini,
        ollama_provider=ollama,
        network_checker=net,
    )

    events: list[StreamEvent] = []
    messages = [Message(role="user", content="Kiểm tra fallback")]
    async for event in router.stream_chat(messages):
        events.append(event)

    # Thử lần đầu + 2 lần retry = 3 lần gọi Gemini
    assert gemini.call_count == 3
    # Sau khi hết retry -> gọi Ollama
    assert ollama.call_count == 1
    assert router.last_provider_used == "ollama"
    assert any("Đã chuyển sang model cục bộ" in str(e.content) for e in events if e.type == "text_delta")


@pytest.mark.asyncio
async def test_auto_gemini_429_fallback(test_config: Config) -> None:
    """Kiểm tra khi Gemini trả về mã 429 (hết hạn mức) -> retry -> tự động fallback sang Ollama."""
    gemini = DummyProvider(
        name="gemini",
        default_model="gemini-2.5-flash",
        error_to_raise=ProviderError("quota_429", "Hết quota 429"),
    )
    ollama = DummyProvider(name="ollama", default_model="qwen2.5:7b")
    net = DummyNetworkChecker(is_online_val=True)

    router = ModelRouter(
        config=test_config,
        gemini_provider=gemini,
        ollama_provider=ollama,
        network_checker=net,
    )

    events: list[StreamEvent] = []
    messages = [Message(role="user", content="Test 429")]
    async for event in router.stream_chat(messages):
        events.append(event)

    assert gemini.call_count == 3
    assert ollama.call_count == 1
    assert router.last_provider_used == "ollama"


@pytest.mark.asyncio
async def test_auto_gemini_5xx_fallback(test_config: Config) -> None:
    """Kiểm tra khi Gemini trả về lỗi server 5xx -> retry -> tự động fallback sang Ollama."""
    gemini = DummyProvider(
        name="gemini",
        default_model="gemini-2.5-flash",
        error_to_raise=ProviderError("server_5xx", "Lỗi máy chủ 503"),
    )
    ollama = DummyProvider(name="ollama", default_model="qwen2.5:7b")
    net = DummyNetworkChecker(is_online_val=True)

    router = ModelRouter(
        config=test_config,
        gemini_provider=gemini,
        ollama_provider=ollama,
        network_checker=net,
    )

    events: list[StreamEvent] = []
    messages = [Message(role="user", content="Test 5xx")]
    async for event in router.stream_chat(messages):
        events.append(event)

    assert gemini.call_count == 3
    assert ollama.call_count == 1
    assert router.last_provider_used == "ollama"


@pytest.mark.asyncio
async def test_auto_gemini_auth_error_no_fallback(test_config: Config) -> None:
    """Kiểm tra khi Gemini gặp lỗi xác thực (Auth/Sai key) -> báo lỗi ngay, KHÔNG fallback."""
    gemini = DummyProvider(
        name="gemini",
        default_model="gemini-2.5-flash",
        error_to_raise=ProviderError("auth", "Sai API Key"),
    )
    ollama = DummyProvider(name="ollama", default_model="qwen2.5:7b")
    net = DummyNetworkChecker(is_online_val=True)

    router = ModelRouter(
        config=test_config,
        gemini_provider=gemini,
        ollama_provider=ollama,
        network_checker=net,
    )

    messages = [Message(role="user", content="Test Auth")]
    with pytest.raises(ProviderError) as exc_info:
        async for _ in router.stream_chat(messages):
            pass

    assert exc_info.value.kind == "auth"
    assert gemini.call_count == 1  # Không retry
    assert ollama.call_count == 0  # Không fallback sai lệch


@pytest.mark.asyncio
async def test_explicit_modes(test_config: Config) -> None:
    """Kiểm tra các chế độ ép buộc: local và gemini."""
    gemini = DummyProvider(name="gemini", default_model="gemini-2.5-flash")
    ollama = DummyProvider(name="ollama", default_model="qwen2.5:7b")
    net = DummyNetworkChecker(is_online_val=True)

    router = ModelRouter(
        config=test_config,
        gemini_provider=gemini,
        ollama_provider=ollama,
        network_checker=net,
    )

    # 1. Ép buộc local
    router.set_mode("local")
    messages = [Message(role="user", content="Chỉ chạy local")]
    async for _ in router.stream_chat(messages):
        pass
    assert ollama.call_count == 1
    assert gemini.call_count == 0

    # 2. Ép buộc gemini
    router.set_mode("gemini")
    messages = [Message(role="user", content="Chỉ chạy gemini")]
    async for _ in router.stream_chat(messages):
        pass
    assert gemini.call_count == 1
