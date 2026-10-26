"""Quản lý khóa bí mật qua Windows Credential Manager (keyring) và tiện ích che giấu bí mật.

Tuân thủ nghiêm ngặt Nguyên tắc 3:
- Không hardcode bí mật.
- Bí mật lưu an toàn bằng keyring hoặc biến môi trường.
- Tuyệt đối không ghi bí mật vào log, git hay in ra màn hình console.
"""

import os
import re

SERVICE_NAME = "TroLyAI"

# Pattern nhận diện các khóa API dạng phổ biến (Google Gemini, OpenAI, Generic Hex/Base64)
API_KEY_REGEX = re.compile(r"AIzaSy[0-9A-Za-z_-]{33}|[a-zA-Z0-9_-]{32,64}")


def save_secret(key_name: str, secret_value: str, service: str = SERVICE_NAME) -> None:
    """Lưu trữ khóa bí mật an toàn vào Windows Credential Manager."""
    import keyring

    keyring.set_password(service, key_name, secret_value.strip())


def get_secret(key_name: str, service: str = SERVICE_NAME) -> str | None:
    """Lấy khóa bí mật: ưu tiên từ Windows Credential Manager, sau đó từ biến môi trường."""
    try:
        import keyring

        val = keyring.get_password(service, key_name)
        if val and val.strip():
            return val.strip()
    except Exception:
        pass

    env_val = os.getenv(key_name)
    if env_val and env_val.strip():
        return env_val.strip()

    return None


def mask_secrets(text: str) -> str:
    """Che giấu toàn bộ các khóa bí mật được tìm thấy trong chuỗi văn bản."""
    if not isinstance(text, str):
        return text

    # Che giấu giá trị cụ thể từ biến môi trường nếu có
    for env_k in ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
        secret = os.getenv(env_k)
        if secret and len(secret) > 6 and secret in text:
            text = text.replace(secret, "[BÍ_MẬT_KEY]")

    # Che giấu theo pattern API key của Google AI Studio
    google_pattern = re.compile(r"AIzaSy[0-9A-Za-z_-]{33}")
    text = google_pattern.sub("[BÍ_MẬT_GEMINI_KEY]", text)

    return text
