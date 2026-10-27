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


import logging
from pathlib import Path

KEYRING_SERVICE = "TroLyAI"
KEYRING_KEYS_STORE = "GEMINI_API_KEYS_JSON"
KEYRING_SINGLE_KEY = "GEMINI_API_KEY"

logger = logging.getLogger("assistant.llm.gemini_provider")


def _get_keys_backup_path() -> Path:
    """Đường dẫn lưu danh sách khóa dự phòng trong AppData cục bộ của người dùng."""
    from assistant.config import _get_default_data_dir

    data_dir = _get_default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "gemini_keys.json"


def mask_api_key(key: str) -> str:
    """Che giấu một phần API Key để hiển thị an toàn trên giao diện."""
    if not key:
        return ""
    cleaned = key.strip().strip("\"'")
    if len(cleaned) <= 10:
        return cleaned[:3] + "..." + cleaned[-2:]
    return cleaned[:8] + "..." + cleaned[-4:]


def get_gemini_api_keys() -> list[dict[str, Any]]:
    """Lấy danh sách tất cả các Gemini API Keys.

    Cơ chế Dual Persistence đảm bảo không bao giờ mất dữ liệu:
    1. Đọc từ Windows Credential Locker (keyring).
    2. Nếu keyring không có hoặc lỗi, đọc từ file dữ liệu gemini_keys.json.
    3. Tự động di chuyển (migrate) key đơn lẻ cũ nếu cả 2 đều chưa có.
    """
    import json

    keys: list[dict[str, Any]] = []

    # 1. Thử đọc từ Windows Credential Locker (keyring)
    try:
        import keyring

        raw_json = keyring.get_password(KEYRING_SERVICE, KEYRING_KEYS_STORE)
        if raw_json and raw_json.strip():
            parsed = json.loads(raw_json)
            if isinstance(parsed, list) and parsed:
                keys = parsed
    except Exception as exc:
        logger.debug("Không thể đọc keyring store: %s", exc)

    # 2. Nếu keyring trống, đọc từ file dự phòng AppData cục bộ
    if not keys:
        try:
            backup_file = _get_keys_backup_path()
            if backup_file.is_file():
                content = backup_file.read_text(encoding="utf-8")
                if content and content.strip():
                    parsed = json.loads(content)
                    if isinstance(parsed, list) and parsed:
                        keys = parsed
                        # Đồng bộ ngược lại vào keyring
                        try:
                            import keyring

                            keyring.set_password(KEYRING_SERVICE, KEYRING_KEYS_STORE, json.dumps(keys, ensure_ascii=False))
                        except Exception:
                            pass
        except Exception as exc:
            logger.debug("Không thể đọc file dự phòng keys: %s", exc)

    # 3. Nếu chưa có danh sách ở cả 2 nơi, kiểm tra key đơn lẻ cũ từ keyring hoặc biến môi trường
    if not keys:
        legacy_key = None
        try:
            import keyring

            legacy_key = keyring.get_password(KEYRING_SERVICE, KEYRING_SINGLE_KEY)
        except Exception:
            pass
        if not legacy_key:
            legacy_key = os.getenv("GEMINI_API_KEY")

        if legacy_key and legacy_key.strip():
            cleaned = legacy_key.strip().strip("\"'")
            if cleaned:
                from datetime import datetime

                initial_item = {
                    "id": "key_default",
                    "name": "Khóa mặc định",
                    "key": cleaned,
                    "created_at": datetime.now().isoformat(),
                    "is_active": True,
                }
                keys = [initial_item]
                save_gemini_api_keys(keys)
    elif keys:
        # Nếu đã có keys trong keyring nhưng file backup chưa có, đồng bộ sang file backup
        try:
            backup_file = _get_keys_backup_path()
            if not backup_file.is_file():
                backup_file.write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return keys


def save_gemini_api_keys(keys: list[dict[str, Any]]) -> None:
    """Lưu danh sách khóa an toàn với cơ chế Dual Persistence (Keyring + File dự phòng)."""
    import json
    from assistant.logging_setup import SecretFilter

    # Đảm bảo có ít nhất 1 khóa is_active nếu danh sách không rỗng
    has_active = any(k.get("is_active") for k in keys)
    if keys and not has_active:
        keys[0]["is_active"] = True

    # 1. Lưu lập tức vào file dự phòng cục bộ trong %APPDATA%
    try:
        backup_file = _get_keys_backup_path()
        backup_file.write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Không thể ghi file dự phòng gemini_keys.json: %s", exc)

    # 2. Lưu vào Windows Credential Locker (keyring)
    try:
        import keyring

        raw_json = json.dumps(keys, ensure_ascii=False)
        keyring.set_password(KEYRING_SERVICE, KEYRING_KEYS_STORE, raw_json)

        # Tìm key đang active để đồng bộ với single key
        active_key = ""
        for k in keys:
            if k.get("is_active"):
                active_key = k.get("key", "")
                break
        if not active_key and keys:
            active_key = keys[0].get("key", "")

        if active_key:
            keyring.set_password(KEYRING_SERVICE, KEYRING_SINGLE_KEY, active_key)
            try:
                SecretFilter.register_secret(active_key)
            except Exception:
                pass
        else:
            try:
                keyring.delete_password(KEYRING_SERVICE, KEYRING_SINGLE_KEY)
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Không thể lưu khóa vào Windows Credential Locker: %s", exc)

    # 3. Đăng ký tất cả các khóa vào bộ lọc an toàn để không bao giờ lộ ra log
    for k in keys:
        if k.get("key"):
            try:
                SecretFilter.register_secret(k["key"])
            except Exception:
                pass


def add_gemini_api_key(api_key: str, name: str = "") -> dict[str, Any]:
    """Thêm một Gemini API Key mới vào danh sách."""
    import uuid
    from datetime import datetime

    cleaned = api_key.strip().strip("\"'")
    if not cleaned:
        raise ValueError("Khóa API Key không được để trống")

    keys = get_gemini_api_keys()

    key_id = f"key_{uuid.uuid4().hex[:8]}"
    is_first = len(keys) == 0
    item_name = name.strip() if name and name.strip() else f"Khóa {len(keys) + 1}"

    new_item = {
        "id": key_id,
        "name": item_name,
        "key": cleaned,
        "created_at": datetime.now().isoformat(),
        "is_active": is_first,
    }
    keys.append(new_item)
    save_gemini_api_keys(keys)
    return new_item


def update_gemini_api_key(
    key_id: str,
    api_key: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Cập nhật tên hoặc giá trị của một Gemini API Key đã lưu."""
    keys = get_gemini_api_keys()
    for item in keys:
        if item.get("id") == key_id:
            if name and name.strip():
                item["name"] = name.strip()
            if api_key and api_key.strip():
                cleaned = api_key.strip().strip("\"'")
                if cleaned and "..." not in cleaned:
                    item["key"] = cleaned
            save_gemini_api_keys(keys)
            return item
    raise ValueError(f"Không tìm thấy khóa với ID: {key_id}")


def delete_gemini_api_key(key_id: str) -> bool:
    """Xóa một Gemini API Key theo ID."""
    keys = get_gemini_api_keys()
    original_len = len(keys)
    remaining = [k for k in keys if k.get("id") != key_id]
    if len(remaining) == original_len:
        return False

    has_active = any(k.get("is_active") for k in remaining)
    if remaining and not has_active:
        remaining[0]["is_active"] = True

    save_gemini_api_keys(remaining)
    return True


def set_active_gemini_api_key(key_id: str) -> bool:
    """Kích hoạt một Gemini API Key được chỉ định."""
    keys = get_gemini_api_keys()
    found = False
    for k in keys:
        if k.get("id") == key_id:
            k["is_active"] = True
            found = True
        else:
            k["is_active"] = False

    if found:
        save_gemini_api_keys(keys)
    return found


def test_gemini_api_key_connectivity(api_key: str) -> tuple[bool, str]:
    """Kiểm tra xem khóa Gemini API có hoạt động và kết nối được với Google hay không."""
    cleaned = api_key.strip().strip("\"'")
    if not cleaned:
        return False, "Khóa API Key không được để trống"

    try:
        from google import genai

        client = genai.Client(api_key=cleaned)
        # Kiểm tra thử model gemini-2.0-flash không tốn quota chat
        client.models.get(model="gemini-2.0-flash")
        return True, "Khóa Gemini API hoạt động rất tốt! Kết nối Google Gemini thành công."
    except Exception as err:
        p_err = classify_gemini_error(err)
        return False, p_err.message


def get_gemini_api_key() -> str | None:
    """Lấy Gemini API Key: ưu tiên key active trong keyring, sau đó đến biến môi trường."""
    try:
        keys = get_gemini_api_keys()
        for k in keys:
            if k.get("is_active") and k.get("key"):
                return k["key"].strip().strip("\"'")
        if keys and keys[0].get("key"):
            return keys[0]["key"].strip().strip("\"'")
    except Exception:
        pass

    try:
        import keyring

        key = keyring.get_password("TroLyAI", "GEMINI_API_KEY")
        if key and key.strip():
            cleaned = key.strip().strip("\"'")
            if cleaned:
                return cleaned
    except Exception:
        pass

    env_key = os.getenv("GEMINI_API_KEY")
    if env_key and env_key.strip():
        cleaned = env_key.strip().strip("\"'")
        if cleaned:
            return cleaned

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
        if "location" in err_str or "country" in err_str:
            msg = "Khu vực / vị trí địa lý của bạn hiện chưa được Google Gemini API hỗ trợ trực tiếp. Hãy kiểm tra lại kết nối mạng hoặc chuyển sang dùng mô hình Ollama Cục bộ."
        elif "api key restrictions" in err_str or "restrictions" in err_str:
            msg = "Khóa Gemini API bị chặn bởi chính sách giới hạn khóa (API key restrictions trên Google Cloud). Vui lòng cấu hình khóa không giới hạn hoặc tạo khóa mới tại Google AI Studio (https://aistudio.google.com/app/apikey)."
        elif "has not been used in project" in err_str or "is disabled" in err_str:
            msg = "Dịch vụ 'Generative Language API' chưa được kích hoạt trong dự án Google Cloud của khóa này. Vui lòng lấy khóa trực tiếp từ Google AI Studio (https://aistudio.google.com/app/apikey) để dùng ngay."
        else:
            msg = "Khóa Gemini API không hợp lệ hoặc đã bị vô hiệu hoá. Vui lòng vào Cài đặt hoặc dùng lệnh 'assistant set-key' để cập nhật lại khóa mới từ Google AI Studio (https://aistudio.google.com/app/apikey)."

        return ProviderError(
            kind="auth",
            message=msg,
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

    # 6. Model không tồn tại hoặc đã ngừng hỗ trợ (404 Not Found)
    if any(kw in err_str for kw in ["404", "not_found", "not found"]):
        if "not supported for generatecontent" in err_str or "version v1beta" in err_str:
            return ProviderError(
                kind="unknown",
                message=(
                    "Mô hình Gemini không khả dụng (404 Not Found). "
                    "Nguyên nhân: API Key của bạn chưa được kích hoạt dịch vụ 'Generative Language API' trên Google Cloud Console, "
                    "hoặc cần tạo khóa API mới từ Google AI Studio (https://aistudio.google.com/app/apikey). "
                    "Hãy kiểm tra lại khóa API hoặc chuyển sang chế độ 'Tự động (Auto)' / 'Ollama Cục bộ' để tiếp tục trò chuyện."
                ),
                raw_error=err,
            )
        return ProviderError(
            kind="unknown",
            message=f"Mô hình Gemini không khả dụng hoặc đã ngừng hỗ trợ (404 Not Found): {err}",
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

    def set_model(self, model_name: str) -> None:
        """Cập nhật tên mô hình Gemini đang dùng."""
        if model_name and model_name.strip():
            self._model_name = model_name.strip()

    def _get_client(self, api_version: str | None = None, api_key: str | None = None) -> Any:
        """Khởi tạo client từ thư viện google-genai với API key đã lưu hoặc truyền vào."""
        key = api_key or get_gemini_api_key()
        if not key:
            raise ProviderError(
                kind="auth",
                message="Chưa cấu hình Gemini API Key. Vui lòng vào Cài đặt để thêm khóa.",
            )

        try:
            from google import genai

            if api_version:
                return genai.Client(api_key=key, http_options={"api_version": api_version})
            return genai.Client(api_key=key)
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
        default_list = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        try:
            models_pager = await client.aio.models.list()
            model_names: list[str] = []
            async for m in models_pager:
                name = getattr(m, "name", str(m))
                # Tinh gọn tên model (ví dụ: models/gemini-2.5-flash -> gemini-2.5-flash)
                if name.startswith("models/"):
                    name = name.removeprefix("models/")
                if "gemini" in name.lower() and "embed" not in name.lower():
                    model_names.append(name)
            return sorted(model_names) if model_names else default_list
        except Exception:
            return default_list

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

        # 3. Thực hiện gọi streaming bất đồng bộ kèm cơ chế tự phục hồi danh sách mô hình & endpoint
        candidate_models = [
            self._model_name,
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
        ]
        seen: set[str] = set()
        candidates: list[str] = [m for m in candidate_models if not (m in seen or seen.add(m))]

        # Chuẩn bị danh sách client: ưu tiên client mặc định v1beta (hỗ trợ đầy đủ gemini-2.0-flash), sau đó mới tới v1 dự phòng
        clients_to_try: list[Any] = [client]
        try:
            clients_to_try.append(self._get_client(api_version="v1"))
        except Exception:
            pass

        last_err: Exception | None = None
        for cl_idx, cl in enumerate(clients_to_try):
            for idx, current_cand in enumerate(candidates):
                yielded_any = False
                try:
                    stream = await cl.aio.models.generate_content_stream(
                        model=current_cand,
                        contents=contents,
                        config=generate_config,
                    )

                    async for chunk in stream:
                        yielded_any = True
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

                    # Cập nhật mô hình hoạt động thành công
                    self._model_name = current_cand
                    yield StreamEvent(type="done", content={"finish_reason": "stop"})
                    return

                except Exception as err:
                    last_err = err
                    err_str = str(err).lower()
                    is_404 = "404" in err_str or "not_found" in err_str or "not found" in err_str
                    is_last = (cl_idx == len(clients_to_try) - 1 and idx == len(candidates) - 1)
                    # Nếu chưa yield dữ liệu nào và lỗi 404, thử tiếp model kế tiếp hoặc client kế tiếp
                    if not yielded_any and is_404 and not is_last:
                        continue
                    if is_last:
                        raise classify_gemini_error(err) from err
                    raise classify_gemini_error(err) from err

        if last_err:
            raise classify_gemini_error(last_err)
