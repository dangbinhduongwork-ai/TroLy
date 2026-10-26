"""Nhà cung cấp mô hình Google Gemini qua SDK mới `google-genai`.

Tuân thủ nghiêm ngặt:
- Không dùng gói cũ `google-generativeai`.
- Đọc khóa từ Windows Credential Manager (keyring) trước, sau đó mới đến biến môi trường.
- Tên model lấy trực tiếp từ cấu hình (không hardcode).
- Phân loại lỗi chính xác: mất mạng, hết hạn mức (429), lỗi máy chủ (5xx), lỗi xác thực, nội dung bị chặn.
"""

from collections.abc import AsyncIterator
import os
from typing import Any

from assistant.config import Config, load_config
from assistant.llm.base import (
    LLMProvider,
    Message,
    ProviderError,
    StreamEvent,
    Usage,
)


def get_gemini_api_key() -> str | None:
    """Lấy Gemini API Key: ưu tiên keyring trước, biến môi trường sau."""
    try:
        import keyring

        key = keyring.get_password("TroLyAI", "GEMINI_API_KEY")
        if key and key.strip():
            return key.strip()
    except Exception:
        pass

    env_key = os.getenv("GEMINI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    return None


def classify_gemini_error(err: Exception) -> ProviderError:
    """Phân loại ngoại lệ từ Gemini SDK thành ProviderError chuẩn hoá."""
    err_str = str(err).lower()
    err_type = type(err).__name__.lower()

    # 1. Lỗi mạng / timeout / không kết nối được
    if any(
        kw in err_str or kw in err_type
        for kw in ["connect", "timeout", "network", "dns", "getaddrinfo", "unavailable", "socket"]
    ):
        return ProviderError(
            kind="network",
            message="Không thể kết nối đến máy chủ Google Gemini. Vui lòng kiểm tra đường truyền mạng.",
            raw_error=err,
        )

    # 2. Hết hạn mức / Rate limit (429)
    if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
        return ProviderError(
            kind="quota_429",
            message="Đã hết hạn mức yêu cầu Gemini API (Mã lỗi 429: Resource Exhausted).",
            raw_error=err,
        )

    # 3. Lỗi xác thực / Sai key / Hết hạn key (401, 403)
    if any(
        kw in err_str
        for kw in [
            "401",
            "403",
            "api_key_invalid",
            "invalid_api_key",
            "permission_denied",
            "unauthenticated",
            "unauthorized",
        ]
    ):
        return ProviderError(
            kind="auth",
            message="Khóa Gemini API không hợp lệ hoặc đã bị vô hiệu hoá. Dùng lệnh 'assistant set-key' để đổi lại.",
            raw_error=err,
        )

    # 4. Lỗi máy chủ phía Google (500, 503, 5xx)
    if any(code in err_str for code in ["500", "502", "503", "504", "internal", "server error"]):
        return ProviderError(
            kind="server_5xx",
            message="Máy chủ Google Gemini đang gặp sự cố quá tải hoặc bảo trì (Lỗi 5xx).",
            raw_error=err,
        )

    # 5. Nội dung bị chặn do vi phạm an toàn
    if any(kw in err_str for kw in ["safety", "blocked", "policy", "harmful"]):
        return ProviderError(
            kind="content_blocked",
            message="Yêu cầu hoặc phản hồi đã bị bộ lọc an toàn của Gemini chặn.",
            raw_error=err,
        )

    return ProviderError(
        kind="unknown",
        message=f"Lỗi không xác định từ Gemini: {err}",
        raw_error=err,
    )


class GeminiProvider(LLMProvider):
    """Hiện thực LLMProvider cho Google Gemini sử dụng SDK `google-genai`."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config(create_dirs=False)
        self._model_name = self._config.gemini_model

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return self._model_name

    def _get_client(self) -> Any:
        """Khởi tạo client từ thư viện google-genai với API key đã lưu."""
        api_key = get_gemini_api_key()
        if not api_key:
            raise ProviderError(
                kind="auth",
                message="Chưa cấu hình Gemini API Key. Vui lòng chạy lệnh 'assistant set-key' để cài đặt.",
            )

        try:
            from google import genai

            return genai.Client(api_key=api_key)
        except ImportError as err:
            raise ProviderError(
                kind="unknown",
                message="Chưa cài đặt thư viện 'google-genai'. Vui lòng chạy: pip install google-genai",
                raw_error=err,
            ) from err

    async def is_available(self) -> bool:
        """Kiểm tra có sẵn API key hay không."""
        return get_gemini_api_key() is not None

    async def list_models(self) -> list[str]:
        """Liệt kê các model Gemini khả dụng cho API key hiện tại."""
        client = self._get_client()
        try:
            models_pager = await client.aio.models.list()
            model_names: list[str] = []
            async for m in models_pager:
                name = getattr(m, "name", str(m))
                # Tinh gọn tên model (ví dụ: models/gemini-2.5-flash -> gemini-2.5-flash)
                if name.startswith("models/"):
                    name = name.removeprefix("models/")
                if "gemini" in name.lower():
                    model_names.append(name)
            return sorted(model_names)
        except Exception as err:
            raise classify_gemini_error(err) from err

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Gửi yêu cầu hội thoại và nhận luồng phản hồi streaming từ Gemini."""
        client = self._get_client()
        from google.genai import types

        # 1. Chuyển đổi định dạng hội thoại nội bộ sang định dạng Gemini
        tool_call_id_to_name: dict[str, str] = {}
        for m in messages:
            if m.tool_calls:
                for tc in m.tool_calls:
                    if tc.id and tc.name:
                        tool_call_id_to_name[tc.id] = tc.name

        contents: list[types.Content] = []
        for msg in messages:
            if msg.role == "system":
                # System message sẽ được đưa vào config riêng
                continue

            parts: list[types.Part] = []
            if msg.role == "tool":
                func_name = (
                    getattr(msg, "name", None)
                    or (tool_call_id_to_name.get(msg.tool_call_id) if msg.tool_call_id else None)
                    or msg.tool_call_id
                    or "tool"
                )
                parts.append(
                    types.Part.from_function_response(
                        name=func_name,
                        response={"result": msg.content or ""},
                    )
                )
                contents.append(types.Content(role="user", parts=parts))
            elif msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append(
                        types.Part.from_function_call(
                            name=tc.name,
                            args=tc.arguments,
                        )
                    )
                contents.append(types.Content(role="model", parts=parts))
            else:
                role = "user" if msg.role == "user" else "model"
                parts.append(types.Part.from_text(text=msg.content or ""))
                contents.append(types.Content(role=role, parts=parts))

        # 2. Cấu hình generation
        generate_config = types.GenerateContentConfig()
        if system:
            generate_config.system_instruction = system

        if tools:
            from assistant.llm.schema_adapters import to_gemini_tools

            generate_config.tools = to_gemini_tools(tools)

        # 3. Thực hiện gọi streaming bất đồng bộ
        try:
            stream = await client.aio.models.generate_content_stream(
                model=self._model_name,
                contents=contents,
                config=generate_config,
            )

            async for chunk in stream:
                # Trích xuất văn bản từ chunk nếu có
                if chunk.text:
                    yield StreamEvent(type="text_delta", content=chunk.text)

                # Trích xuất Function Calls từ chunk nếu có
                function_calls = getattr(chunk, "function_calls", None)
                if function_calls:
                    from assistant.llm.base import ToolCall

                    for fc in function_calls:
                        call_id = getattr(fc, "id", None) or getattr(fc, "name", "call")
                        args = getattr(fc, "args", {}) or {}
                        yield StreamEvent(
                            type="tool_call",
                            content=ToolCall(
                                id=str(call_id),
                                name=getattr(fc, "name", "unknown"),
                                arguments=dict(args),
                            ),
                        )

                # Trích xuất usage nếu có trong metadata
                usage_meta = getattr(chunk, "usage_metadata", None)
                if usage_meta:
                    prompt_tok = getattr(usage_meta, "prompt_token_count", 0) or 0
                    cand_tok = getattr(usage_meta, "candidates_token_count", 0) or 0
                    total_tok = getattr(usage_meta, "total_token_count", 0) or (prompt_tok + cand_tok)
                    yield StreamEvent(
                        type="usage",
                        content=Usage(
                            prompt_tokens=prompt_tok,
                            completion_tokens=cand_tok,
                            total_tokens=total_tok,
                        ),
                    )

            yield StreamEvent(type="done", content={"finish_reason": "stop"})


        except Exception as err:
            raise classify_gemini_error(err) from err
