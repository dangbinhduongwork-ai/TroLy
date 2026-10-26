"""Nhà cung cấp mô hình Ollama cục bộ qua endpoint tương thích OpenAI bằng HTTP streaming (httpx).

Tuân thủ Nguyên tắc 11: Sử dụng trực tiếp `httpx` thay vì cài thêm thư viện openai hay ollama riêng biệt.
Tên model được lấy trực tiếp từ config, có hướng dẫn cụ thể cách bật nếu máy chủ chưa chạy.
"""

from collections.abc import AsyncIterator
import json
from typing import Any
import httpx

from assistant.config import Config, load_config
from assistant.llm.base import (
    LLMProvider,
    Message,
    ProviderError,
    StreamEvent,
    Usage,
)


class OllamaProvider(LLMProvider):
    """Hiện thực LLMProvider cho mô hình cục bộ qua Ollama."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config(create_dirs=False)
        self._host = self._config.ollama_host.rstrip("/")
        self._model_name = self._config.local_model

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def default_model(self) -> str:
        return self._model_name

    async def is_available(self) -> bool:
        """Kiểm tra máy chủ Ollama có đang hoạt động trên máy hay không."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self._host}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Lấy danh sách các model đã được cài đặt tải về trong Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self._host}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                raise ProviderError(
                    kind="server_5xx",
                    message=f"Máy chủ Ollama phản hồi mã lỗi {res.status_code}",
                )
        except httpx.ConnectError as err:
            raise ProviderError(
                kind="network",
                message="Ollama chưa được bật. Hãy mở ứng dụng Ollama hoặc gõ lệnh 'ollama serve' trong terminal.",
                raw_error=err,
            ) from err
        except Exception as err:
            if isinstance(err, ProviderError):
                raise
            raise ProviderError(
                kind="unknown",
                message=f"Lỗi khi đọc danh sách model Ollama: {err}",
                raw_error=err,
            ) from err

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Truyền phát luồng hội thoại bất đồng bộ từ endpoint /v1/chat/completions của Ollama."""
        # 1. Chuẩn hoá danh sách messages theo chuẩn OpenAI
        formatted_messages: list[dict[str, Any]] = []
        if system:
            formatted_messages.append({"role": "system", "content": system})

        for msg in messages:
            msg_dict: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
            formatted_messages.append(msg_dict)

        payload = {
            "model": self._model_name,
            "messages": formatted_messages,
            "stream": True,
        }

        url = f"{self._host}/v1/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code == 404:
                        raise ProviderError(
                            kind="unknown",
                            message=(
                                f"Model '{self._model_name}' chưa được cài đặt trong Ollama. "
                                f"Vui lòng chạy lệnh: 'ollama pull {self._model_name}'"
                            ),
                        )
                    if response.status_code != 200:
                        body = await response.aread()
                        raise ProviderError(
                            kind="server_5xx",
                            message=f"Ollama trả về lỗi {response.status_code}: {body.decode(errors='ignore')}",
                        )

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue

                        data_str = line.removeprefix("data:").strip()
                        if data_str == "[DONE]":
                            yield StreamEvent(type="done", content={"finish_reason": "stop"})
                            break

                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                text_chunk = delta.get("content")
                                if text_chunk:
                                    yield StreamEvent(type="text_delta", content=text_chunk)

                            # Trích xuất usage nếu có
                            usage_data = chunk.get("usage")
                            if usage_data:
                                yield StreamEvent(
                                    type="usage",
                                    content=Usage(
                                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                                        completion_tokens=usage_data.get("completion_tokens", 0),
                                        total_tokens=usage_data.get("total_tokens", 0),
                                    ),
                                )
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError as err:
            raise ProviderError(
                kind="network",
                message="Ollama chưa được bật. Hãy mở ứng dụng Ollama hoặc gõ lệnh 'ollama serve' trong terminal.",
                raw_error=err,
            ) from err
        except httpx.TimeoutException as err:
            raise ProviderError(
                kind="network",
                message="Kết nối tới mô hình Ollama bị quá thời gian chờ (timeout).",
                raw_error=err,
            ) from err
        except Exception as err:
            if isinstance(err, ProviderError):
                raise
            raise ProviderError(
                kind="unknown",
                message=f"Lỗi khi nhận phản hồi từ Ollama: {err}",
                raw_error=err,
            ) from err
