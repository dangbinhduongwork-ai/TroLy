"""Nhật ký kiểm toán an toàn (Audit Logger) ghi nhận mọi lượt gọi công cụ dưới định dạng JSONL.

Tuân thủ:
- Ghi nhận: thời gian, tên công cụ, tham số đã che giấu bí mật, kết quả rút gọn, quyết định phê duyệt.
- Tuyệt đối không ghi toàn bộ nội dung file (tránh phình dung lượng và bảo vệ dữ liệu nhạy cảm).
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import zoneinfo

from assistant.config import load_config
from assistant.logging_setup import SecretFilter


def _sanitize_value(val: Any) -> Any:
    """Đệ quy làm sạch và che giấu các khóa bí mật trong tham số hoặc kết quả."""
    if isinstance(val, str):
        # 1. Che giấu theo pattern của SecretFilter
        val = SecretFilter.API_KEY_PATTERN.sub("[BÍ_MẬT_KEY]", val)

        # 2. Che giấu GEMINI_API_KEY từ môi trường nếu có
        import os
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and len(gemini_key) > 5 and gemini_key in val:
            val = val.replace(gemini_key, "[BÍ_MẬT_KEY]")

        # 3. Che giấu các token bí mật đã đăng ký (như session_token)
        for sec in getattr(SecretFilter, "_registered_secrets", set()):
            if sec in val:
                val = val.replace(sec, "[BÍ_MẬT_TOKEN]")

        # Cắt ngắn nếu chuỗi quá dài (không ghi toàn bộ nội dung file vào audit log)
        if len(val) > 200:
            return val[:197] + "..."
        return val

    elif isinstance(val, dict):
        return {k: _sanitize_value(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [_sanitize_value(item) for item in val[:20]]
    return val


class AuditLogger:
    """Bộ ghi nhật ký kiểm toán append-only JSONL."""

    def __init__(self, data_dir: Path | None = None) -> None:
        if data_dir is None:
            data_dir = load_config(create_dirs=False).data_dir
        self.log_file = data_dir / "logs" / "audit.jsonl"

    def log_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        decision: str,
        result_summary: Any = None,
        is_error: bool = False,
    ) -> None:
        """Ghi một dòng nhật ký kiểm toán mới vào audit.jsonl."""
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
                now_str = datetime.now(tz).isoformat()
            except Exception:
                now_str = datetime.now().isoformat()

            entry = {
                "timestamp": now_str,
                "tool": tool_name,
                "arguments": _sanitize_value(arguments),
                "decision": decision,  # ALLOW, APPROVED, REJECTED, DENY
                "result_summary": _sanitize_value(result_summary),
                "is_error": is_error,
            }

            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            # Audit log không được làm sập ứng dụng chính
            pass
