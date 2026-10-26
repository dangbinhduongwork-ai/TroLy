"""Quản lý tiến trình duy nhất (Single Instance Lock) cho Trợ Lý AI.

Mục đích:
- Ngăn chặn người dùng chạy nhiều bản sao Trợ lý cùng lúc gây xung đột cổng mạng (ui_port)
  hoặc chạy lặp các tác vụ định kỳ trong APScheduler.
- Nếu ứng dụng đã đang chạy ngầm, tự động tái kích hoạt cửa sổ giao diện Microsoft Edge
  với Session Token hiện hành, rồi thoát nhẹ nhàng tiến trình mới.
"""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import socket
from typing import Any

from assistant.desktop.window import launch_desktop_window

logger = logging.getLogger("assistant.desktop.single_instance")

INSTANCE_FILE = "instance.json"


def _is_server_alive(port: int, timeout: float = 0.5) -> bool:
    """Kiểm tra máy chủ tại 127.0.0.1:<port> có đang mở kết nối hay không."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            res = sock.connect_ex(("127.0.0.1", port))
            return res == 0
    except Exception:
        return False


def get_instance_info(data_dir: Path) -> dict[str, Any] | None:
    """Đọc thông tin phiên chạy hiện hành từ tệp instance.json."""
    info_path = data_dir / INSTANCE_FILE
    if not info_path.is_file():
        return None

    try:
        content = info_path.read_text(encoding="utf-8")
        return json.loads(content)
    except Exception:
        return None


def check_or_acquire_instance(
    data_dir: Path,
    port: int,
    session_token: str,
    open_window_if_running: bool = True,
) -> bool:
    """Kiểm tra xem đã có tiến trình nào đang chạy hay chưa.

    Returns:
        True: Là tiến trình chính duy nhất, được phép tiếp tục chạy máy chủ.
        False: Đã có tiến trình khác đang chạy ngầm; đã kích hoạt lại cửa sổ và tiến trình hiện tại nên thoát.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    info_path = data_dir / INSTANCE_FILE

    old_info = get_instance_info(data_dir)
    if old_info:
        old_port = old_info.get("port", port)
        old_token = old_info.get("token", "")
        old_pid = old_info.get("pid")

        # Kiểm tra máy chủ cũ có thực sự còn sống không
        if _is_server_alive(old_port):
            logger.info("Phát hiện tiến trình Trợ Lý AI khác đang chạy ngầm (PID: %s, Port: %s)", old_pid, old_port)
            if open_window_if_running and old_token:
                logger.info("Đang kích hoạt lại cửa sổ ứng dụng cho tiến trình hiện có...")
                launch_desktop_window(port=old_port, session_token=old_token)
            return False

    # Ghi lại thông tin tiến trình hiện tại làm instance chính
    current_info = {
        "pid": os.getpid(),
        "port": port,
        "token": session_token,
        "started_at": datetime.now().isoformat(),
    }

    try:
        info_path.write_text(json.dumps(current_info, indent=2), encoding="utf-8")
    except Exception as err:
        logger.warning("Không thể ghi file instance.json: %s", err)

    return True


def release_instance(data_dir: Path) -> None:
    """Giải phóng file instance.json khi ứng dụng thoát hoàn toàn."""
    info_path = data_dir / INSTANCE_FILE
    try:
        if info_path.is_file():
            info = get_instance_info(data_dir)
            # Chỉ xoá nếu chính PID hiện tại đã tạo ra file này
            if info and info.get("pid") == os.getpid():
                info_path.unlink(missing_ok=True)
    except Exception as err:
        logger.debug("Lỗi giải phóng instance lock: %s", err)
