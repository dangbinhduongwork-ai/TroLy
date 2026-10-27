"""Nhà cung cấp mô hình Ollama cục bộ qua endpoint tương thích OpenAI bằng HTTP streaming (httpx).

Tuân thủ Nguyên tắc 11: Sử dụng trực tiếp `httpx` thay vì cài thêm thư viện openai hay ollama riêng biệt.
Tên model được lấy trực tiếp từ config, có hướng dẫn cụ thể cách bật nếu máy chủ chưa chạy.
"""

from collections.abc import AsyncIterator
import json
import time
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
        self._cached_models: list[str] = []
        self._last_models_check_time: float = 0.0
        self._models_ttl_seconds: float = 60.0

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def default_model(self) -> str:
        return self._model_name

    def invalidate_model_cache(self) -> None:
        """Xóa bộ đệm danh sách model để buộc truy vấn lại từ Ollama ở lần gọi kế tiếp."""
        self._cached_models = []
        self._last_models_check_time = 0.0

    def set_model(self, model_name: str) -> None:
        """Đổi mô hình Ollama cục bộ đang hoạt động và làm mới cache."""
        clean_name = model_name.strip()
        if clean_name:
            self._model_name = clean_name
            self.invalidate_model_cache()

    async def is_available(self) -> bool:
        """Kiểm tra máy chủ Ollama có đang hoạt động trên máy hay không."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self._host}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self, force_refresh: bool = False) -> list[str]:
        """Lấy danh sách các model đã được cài đặt trong Ollama (có cache TTL 60 giây)."""
        now = time.time()
        if (
            not force_refresh
            and self._cached_models
            and (now - self._last_models_check_time) < self._models_ttl_seconds
        ):
            return list(self._cached_models)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self._host}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                    self._cached_models = models
                    self._last_models_check_time = time.time()
                    return list(models)
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
            if msg.role == "tool":
                msg_dict["tool_call_id"] = msg.tool_call_id or "call"
            elif msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            formatted_messages.append(msg_dict)

        # Tự động kiểm tra và giải quyết model name nếu model chỉ định chưa khớp chính xác
        active_model = self._model_name
        installed: list[str] = []
        try:
            installed = await self.list_models()
        except Exception:
            pass

        if installed:
            # 1. Khớp chính xác
            if active_model in installed:
                pass
            # 2. Khớp tag :latest (ví dụ qwen2.5:14b khớp với qwen2.5:14b:latest hoặc ngược lại)
            elif f"{active_model}:latest" in installed:
                active_model = f"{active_model}:latest"
            elif any(m.startswith(f"{active_model}:") for m in installed):
                active_model = next(m for m in installed if m.startswith(f"{active_model}:"))
            elif any(m.split(":")[0] == active_model.split(":")[0] for m in installed):
                # Khớp cùng họ, ví dụ cấu hình qwen2.5:7b nhưng máy chỉ có qwen2.5:14b
                active_model = next(m for m in installed if m.split(":")[0] == active_model.split(":")[0])
            elif len(installed) == 1:
                # Nếu chỉ cài 1 model duy nhất trong Ollama, dùng luôn model đó
                active_model = installed[0]

        num_ctx_val = getattr(self._config, "max_context_tokens", 8192)
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": formatted_messages,
            "stream": True,
            "options": {
                "num_ctx": num_ctx_val,
            },
        }

        if tools:
            from assistant.llm.schema_adapters import to_ollama_tools

            payload["tools"] = to_ollama_tools(tools)

        url = f"{self._host}/v1/chat/completions"
        try:
            # Timeout tối ưu 45s (thay vì 180s) tránh ứng dụng bị treo lâu
            async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=5.0, read=45.0)) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code == 404:
                        installed_str = ", ".join(installed) if installed else "Chưa có model nào"
                        raise ProviderError(
                            kind="unknown",
                            message=(
                                f"Model '{active_model}' chưa được cài đặt trong Ollama. "
                                f"Các model hiện có trong máy: [{installed_str}]. "
                                f"Vui lòng chạy lệnh: 'ollama pull {active_model}' hoặc chọn model có sẵn trong trang Cài đặt."
                            ),
                        )
                    if response.status_code != 200:
                        body = await response.aread()
                        raise ProviderError(
                            kind="server_5xx",
                            message=f"Ollama trả về lỗi {response.status_code}: {body.decode(errors='ignore')}",
                        )

                    # Biến lưu trữ ghép nối tool call arguments dở dang trong luồng stream
                    accumulated_tool_calls: dict[int, dict[str, Any]] = {}

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue

                        data_str = line.removeprefix("data:").strip()
                        if data_str == "[DONE]":
                            # Phát ra các tool call đã gom xong nếu có
                            if accumulated_tool_calls:
                                from assistant.llm.base import ToolCall

                                for tc_dict in accumulated_tool_calls.values():
                                    raw_args = tc_dict.get("arguments", "{}")
                                    try:
                                        parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                                    except Exception:
                                        parsed_args = {}
                                    yield StreamEvent(
                                        type="tool_call",
                                        content=ToolCall(
                                            id=tc_dict.get("id") or "call",
                                            name=tc_dict.get("name") or "unknown",
                                            arguments=parsed_args,
                                        ),
                                    )
                                accumulated_tool_calls.clear()

                            yield StreamEvent(type="done", content={"finish_reason": "stop"})
                            break

                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})

                                # Văn bản thường
                                text_chunk = delta.get("content")
                                if text_chunk:
                                    yield StreamEvent(type="text_delta", content=text_chunk)

                                # Lệnh gọi công cụ (Tool Calls)
                                delta_tool_calls = delta.get("tool_calls")
                                if delta_tool_calls:
                                    for tc_item in delta_tool_calls:
                                        idx = tc_item.get("index", 0)
                                        if idx not in accumulated_tool_calls:
                                            accumulated_tool_calls[idx] = {
                                                "id": tc_item.get("id", f"call_{idx}"),
                                                "name": "",
                                                "arguments": "",
                                            }
                                        fn_data = tc_item.get("function", {})
                                        if fn_data.get("name"):
                                            accumulated_tool_calls[idx]["name"] = fn_data["name"]
                                        if fn_data.get("arguments"):
                                            accumulated_tool_calls[idx]["arguments"] += fn_data["arguments"]

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
