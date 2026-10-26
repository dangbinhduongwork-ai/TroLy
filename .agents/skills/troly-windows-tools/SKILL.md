---
name: troly-windows-tools
description: >-
  Use this skill when implementing or modifying Windows-specific integrations,
  including launching apps, opening files/URLs, executing safe subprocess commands,
  storing credentials in Windows Credential Manager, and managing reminders.
---

# Hướng Dẫn Tích Hợp Hệ Điều Hành Windows An Toàn

Tài liệu hướng dẫn mẫu code chuẩn và an toàn khi tương tác với Windows 10/11 trong ứng dụng Trợ Lý AI.

---

## 1. Mở File, Thư Mục, hoặc Trang Web an toàn
Sử dụng `os.startfile` của thư viện chuẩn Python trên Windows để mở tài liệu, thư mục hoặc URL trình duyệt mặc định một cách an toàn mà không cần shell:

```python
import os
from pathlib import Path

def open_item_safely(target: str | Path) -> None:
    """Mở file, thư mục hoặc URL an toàn bằng ứng dụng mặc định của Windows."""
    if isinstance(target, str) and (target.startswith("http://") or target.startswith("https://")):
        os.startfile(target)
        return

    path = Path(target).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy đường dẫn: {path}")
    os.startfile(str(path))
```

---

## 2. Thực thi tiến trình con (Subprocess) an toàn
Tuyệt đối không dùng `shell=True`. Luôn truyền tham số dạng danh sách:

```python
import subprocess
from typing import Sequence

def run_command_safely(
    args: Sequence[str],
    timeout_sec: int = 30
) -> subprocess.CompletedProcess[str]:
    """Thực thi một chương trình con trên Windows không qua shell."""
    return subprocess.run(
        list(args),
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False
    )
```

---

## 3. Lưu trữ khóa bí mật an toàn với `keyring`
Lưu trữ Gemini API key vào Windows Credential Locker an toàn:

```python
import keyring

SERVICE_NAME = "TroLyAI"

def save_api_key(key_name: str, secret_value: str) -> None:
    keyring.set_password(SERVICE_NAME, key_name, secret_value)

def get_api_key(key_name: str) -> str | None:
    return keyring.get_password(SERVICE_NAME, key_name)
```

---

## 4. Kiểm tra Path Traversal
Đảm bảo các thao tác với file không bao giờ vượt ra ngoài thư mục được cấp phép:

```python
from pathlib import Path

def is_safe_path(base_dir: Path, target_path: Path) -> bool:
    """Kiểm tra đường dẫn mục tiêu có nằm trọn trong thư mục gốc cho phép hay không."""
    resolved_base = base_dir.resolve()
    resolved_target = target_path.resolve()
    return resolved_target.is_relative_to(resolved_base)
```
