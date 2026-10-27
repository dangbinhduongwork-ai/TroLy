"""Bộ định tuyến mô hình (Model Router) với ba chế độ: auto, gemini, local.

Quy tắc của chế độ auto:
1. Hội thoại nhạy cảm (sensitive=True) -> bắt buộc dùng local.
2. Kiểm tra nhanh kết nối Internet (cache 10s) -> nếu offline, tự dùng local.
3. Nếu online: gọi Gemini.
   - Khi gặp lỗi mạng, 429 hoặc 5xx: thử lại tối đa 2 lần với backoff. Nếu vẫn lỗi,
     tự chuyển sang local và thông báo "đã chuyển sang model cục bộ vì...".
   - Khi gặp lỗi xác thực hoặc nội dung bị chặn: dừng ngay và báo rõ nguyên nhân.
4. Đếm số request Gemini mỗi ngày, cảnh báo khi gần đạt ngưỡng daily_soft_limit.
5. Luôn ghi nhận và thông báo rõ model nào đã trả lời.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import date
import json
from pathlib import Path
import time
from typing import Any, Literal

from assistant.config import Config, load_config
from assistant.llm.base import (
    LLMProvider,
    Message,
    ProviderError,
    StreamEvent,
)
from assistant.llm.gemini_provider import GeminiProvider
from assistant.llm.ollama_provider import OllamaProvider

RouterMode = Literal["auto", "gemini", "local"]


class NetworkChecker:
    """Kiểm tra kết nối mạng Internet nhanh chóng và lưu cache kết quả."""

    def __init__(self, cache_duration_sec: int = 10) -> None:
        self.cache_duration_sec = cache_duration_sec
        self._last_check_time: float = 0.0
        self._cached_is_online: bool = True

    async def is_online(self) -> bool:
        """Kiểm tra có mạng hay không (trả về giá trị cache nếu kiểm tra trong vòng 10 giây)."""
        now = time.time()
        if (now - self._last_check_time) < self.cache_duration_sec:
            return self._cached_is_online

        # Kiểm tra nhanh kết nối socket TCP tới DNS 1.1.1.1 cổng 53 (thời gian phản hồi thường < 50ms)
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("1.1.1.1", 53),
                timeout=1.5,
            )
            writer.close()
            await writer.wait_closed()
            self._cached_is_online = True
        except Exception:
            # Dự phòng kiểm tra bằng DNS dự phòng 8.8.8.8
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection("8.8.8.8", 53),
                    timeout=1.5,
                )
                writer.close()
                await writer.wait_closed()
                self._cached_is_online = True
            except Exception:
                self._cached_is_online = False

        self._last_check_time = now
        return self._cached_is_online


class DailyUsageTracker:
    """Theo dõi và lưu trữ số lượng request Gemini API đã thực hiện trong ngày."""

    def __init__(self, data_dir: Path) -> None:
        self.usage_file = data_dir / "gemini_usage.json"
        self._cached_date = ""
        self._cached_count = 0
        self._load()

    def _load(self) -> None:
        today_str = date.today().isoformat()
        if self.usage_file.is_file():
            try:
                data = json.loads(self.usage_file.read_text(encoding="utf-8"))
                if data.get("date") == today_str:
                    self._cached_date = today_str
                    self._cached_count = data.get("count", 0)
                    return
            except Exception:
                pass

        self._cached_date = today_str
        self._cached_count = 0

    def increment(self) -> int:
        """Tăng bộ đếm request Gemini thêm 1 và ghi lại vào file."""
        today_str = date.today().isoformat()
        if self._cached_date != today_str:
            self._cached_date = today_str
            self._cached_count = 0

        self._cached_count += 1
        try:
            self.usage_file.parent.mkdir(parents=True, exist_ok=True)
            self.usage_file.write_text(
                json.dumps({"date": self._cached_date, "count": self._cached_count}),
                encoding="utf-8",
            )
        except Exception:
            pass

        return self._cached_count

    def get_count(self) -> int:
        """Lấy số lượng request đã gọi trong ngày hôm nay."""
        today_str = date.today().isoformat()
        if self._cached_date != today_str:
            self._cached_date = today_str
            self._cached_count = 0
        return self._cached_count

    # Bí danh tiện ích cho increment
    record_request = increment


class ModelRouter:
    """Bộ điều phối luồng gọi model thông minh."""

    def __init__(
        self,
        config: Config | None = None,
        gemini_provider: LLMProvider | None = None,
        ollama_provider: LLMProvider | None = None,
        network_checker: NetworkChecker | None = None,
    ) -> None:
        self.config = config or load_config(create_dirs=True)
        self.gemini_provider = gemini_provider or GeminiProvider(self.config)
        self.ollama_provider = ollama_provider or OllamaProvider(self.config)
        self.network_checker = network_checker or NetworkChecker(
            cache_duration_sec=self.config.network_cache_seconds
        )
        self.usage_tracker = DailyUsageTracker(self.config.data_dir)

        self.mode: RouterMode = "auto"
        self.last_model_used: str = ""
        self.last_provider_used: str = ""

    def set_mode(self, mode: RouterMode) -> None:
        """Thay đổi chế độ định tuyến (auto, gemini, local)."""
        if mode not in ("auto", "gemini", "local"):
            raise ValueError(f"Chế độ không hợp lệ: {mode}. Chỉ hỗ trợ: auto, gemini, local.")
        self.mode = mode

    def is_network_available(self) -> bool:
        """Kiểm tra nhanh kết nối Internet (dùng cache hoặc socket đồng bộ với timeout ngắn)."""
        checker = self.network_checker
        if hasattr(checker, "is_online_val"):
            return bool(getattr(checker, "is_online_val"))

        now = time.time()
        if (now - checker._last_check_time) < checker.cache_duration_sec:
            return checker._cached_is_online

        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.4)
            res = sock.connect_ex(("1.1.1.1", 53))
            sock.close()
            is_on = (res == 0)
        except Exception:
            is_on = False

        checker._cached_is_online = is_on
        checker._last_check_time = now
        return is_on


    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        is_sensitive: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Điều phối và truyền phát luồng hội thoại theo chế độ hiện tại."""
        # 1. Yêu cầu nhạy cảm -> BẮT BUỘC dùng model cục bộ (Ollama), tuyệt đối không gửi lên Gemini
        if is_sensitive:
            self.last_provider_used = self.ollama_provider.provider_name
            self.last_model_used = self.ollama_provider.default_model
            yield StreamEvent(
                type="text_delta",
                content="[Bảo mật: Yêu cầu nhạy cảm được xử lý hoàn toàn cục bộ trên máy]\n\n",
            )
            async for event in self.ollama_provider.stream_chat(messages, tools, system):
                yield event
            return

        # 2. Chế độ cục bộ (LOCAL)
        if self.mode == "local":
            self.last_provider_used = self.ollama_provider.provider_name
            self.last_model_used = self.ollama_provider.default_model
            async for event in self.ollama_provider.stream_chat(messages, tools, system):
                yield event
            return

        # 3. Chế độ bắt buộc Gemini (GEMINI)
        if self.mode == "gemini":
            self.last_provider_used = self.gemini_provider.provider_name
            self.last_model_used = self.gemini_provider.default_model
            self._check_and_track_daily_limit()
            async for event in self.gemini_provider.stream_chat(messages, tools, system):
                yield event
            return

        # 4. Chế độ tự động (AUTO)
        # a) Kiểm tra trạng thái mạng
        online = await self.network_checker.is_online()
        if not online:
            self.last_provider_used = self.ollama_provider.provider_name
            self.last_model_used = self.ollama_provider.default_model
            yield StreamEvent(
                type="text_delta",
                content="[Mất kết nối Internet: Tự động chuyển sang mô hình cục bộ Ollama]\n\n",
            )
            async for event in self.ollama_provider.stream_chat(messages, tools, system):
                yield event
            return

        # c) Có mạng -> gọi Gemini kèm cơ chế thử lại (Retry with Backoff) & Fallback
        self.last_provider_used = self.gemini_provider.provider_name
        self.last_model_used = self.gemini_provider.default_model
        warning_msg = self._check_and_track_daily_limit()
        if warning_msg:
            yield StreamEvent(type="text_delta", content=f"{warning_msg}\n\n")

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Đếm số sự kiện text đã phát ra
                yielded_any = False
                async for event in self.gemini_provider.stream_chat(messages, tools, system):
                    yielded_any = True
                    yield event
                return
            except ProviderError as err:
                # Nếu đã yield dở dang một phần tin nhắn mà bị lỗi đứt giữa chừng
                if yielded_any:
                    yield StreamEvent(
                        type="text_delta",
                        content=f"\n[Lỗi gián đoạn luồng từ Gemini: {err.message}]",
                    )
                    return

                # Lỗi xác thực hoặc bị chặn bản quyền/an toàn: dừng ngay, không retry, không fallback
                if err.kind in ("auth", "content_blocked"):
                    raise err

                # Lỗi mạng, 429 hoặc lỗi 5xx từ máy chủ: Thử lại với exponential backoff
                if err.kind in ("network", "quota_429", "server_5xx"):
                    if attempt < max_retries:
                        backoff_time = (attempt + 1) * 1.0  # 1.0s, 2.0s
                        await asyncio.sleep(backoff_time)
                        continue

                # Mọi lỗi khác (bao gồm 404/model ngừng hỗ trợ hoặc khi đã thử hết số lần cho phép):
                # Tự động fallback sang mô hình Ollama cục bộ trong chế độ auto
                fallback_reason = err.message
                self.last_provider_used = self.ollama_provider.provider_name
                self.last_model_used = self.ollama_provider.default_model

                yield StreamEvent(
                    type="text_delta",
                    content=(
                        f"[Hệ thống: Đã chuyển sang model cục bộ vì {fallback_reason}]\n\n"
                    ),
                )
                try:
                    async for event in self.ollama_provider.stream_chat(messages, tools, system):
                        yield event
                    return
                except Exception as ollama_err:
                    yield StreamEvent(
                        type="text_delta",
                        content=(
                            f"\n[Thông báo: Không thể hoàn tất vì kết nối Gemini gặp sự cố ({fallback_reason}) "
                            f"và mô hình cục bộ Ollama cũng chưa được bật ({ollama_err}). "
                            "Vui lòng kiểm tra lại mạng hoặc mở ứng dụng Ollama!]"
                        ),
                    )
                    yield StreamEvent(type="done", content={"finish_reason": "stop"})
                    return

    def _check_and_track_daily_limit(self) -> str | None:
        """Ghi nhận lượt gọi và cảnh báo khi gần đạt ngưỡng daily_soft_limit."""
        current_count = self.usage_tracker.increment()
        limit = self.config.daily_soft_limit

        # Cảnh báo khi đạt từ 90% ngưỡng cấu hình
        if current_count >= int(limit * 0.9):
            return (
                f"[CẢNH BÁO HẠN MỨC] Hôm nay bạn đã sử dụng {current_count}/{limit} "
                "lượt gọi Gemini API."
            )
        return None
