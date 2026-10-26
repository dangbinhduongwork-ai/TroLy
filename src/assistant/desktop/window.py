"""Khởi chạy giao diện Desktop trong cửa sổ ứng dụng riêng biệt bằng Microsoft Edge (Desktop Window Launcher).

Nguyên tắc:
- Mở Microsoft Edge ở chế độ cửa sổ ứng dụng riêng biệt không thanh địa chỉ (--app=http://127.0.0.1:<port>/?token=<token>).
- Nếu không tìm thấy Microsoft Edge, tự động fallback sang trình duyệt mặc định của hệ thống.
- Tuyệt đối KHÔNG dùng shell=True (Nguyên tắc 4), luôn truyền danh sách tham số dạng list.
"""

import logging
import os
from pathlib import Path
import shutil
import subprocess
import webbrowser

logger = logging.getLogger("assistant.desktop.window")


def find_edge_executable() -> str | None:
    """Tìm đường dẫn tệp thực thi Microsoft Edge trên Windows."""
    # 1. Thử tìm qua PATH hệ thống
    which_path = shutil.which("msedge")
    if which_path and Path(which_path).is_file():
        return which_path

    # 2. Quét các thư mục cài đặt tiêu chuẩn trên Windows
    candidate_dirs = [
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("LocalAppData", ""),
    ]

    for base_dir in candidate_dirs:
        if not base_dir:
            continue
        edge_path = Path(base_dir) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if edge_path.is_file():
            return str(edge_path)

    return None


def launch_desktop_window(
    port: int,
    session_token: str,
    width: int = 1200,
    height: int = 800,
) -> bool:
    """Mở giao diện Trợ Lý AI trong cửa sổ ứng dụng độc lập."""
    target_url = f"http://127.0.0.1:{port}/?token={session_token}"

    edge_exe = find_edge_executable()
    if edge_exe:
        logger.info("Khởi chạy giao diện qua Microsoft Edge: %s", edge_exe)
        try:
            # Chạy Edge ở chế độ App riêng biệt (không thanh địa chỉ, không bookmark)
            args = [
                edge_exe,
                f"--app={target_url}",
                f"--window-size={width},{height}",
                "--new-window",
            ]
            subprocess.Popen(args)
            return True
        except Exception as err:
            logger.warning("Không thể mở Edge dạng app: %s. Chuyển sang fallback.", err)

    # Fallback: Mở bằng trình duyệt mặc định của hệ thống
    logger.info("Mở giao diện qua trình duyệt mặc định: %s", target_url)
    try:
        webbrowser.open(target_url)
        return True
    except Exception as err:
        logger.error("Lỗi khi mở trình duyệt: %s", err)
        return False
