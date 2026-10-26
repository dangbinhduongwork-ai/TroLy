"""Điểm khởi nhập dòng lệnh (CLI) cho ứng dụng Trợ Lý AI trên Windows."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request

from assistant import __version__
from assistant.config import load_config
from assistant.logging_setup import setup_logging


def check_gemini_key() -> str:
    """Kiểm tra có GEMINI_API_KEY trong môi trường hoặc Windows Credential Manager hay không.

    Tuyệt đối tuân thủ Nguyên tắc 3: Chỉ trả về trạng thái có/không, không bao giờ in key.
    """
    key_in_env = os.getenv("GEMINI_API_KEY")
    if key_in_env and key_in_env.strip():
        return "Có (từ biến môi trường)"

    try:
        import keyring

        key_in_keyring = keyring.get_password("TroLyAI", "GEMINI_API_KEY")
        if key_in_keyring and key_in_keyring.strip():
            return "Có (từ Windows Credential Manager)"
    except Exception:
        pass

    return "Không"


def check_ollama(host: str = "http://127.0.0.1:11434") -> str:
    """Kiểm tra máy chủ Ollama cục bộ có đang hoạt động và liệt kê các model đã tải."""
    url = f"{host.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                models = [m.get("name", "") for m in data.get("models", [])]
                if models:
                    return f"Đang hoạt động ({len(models)} model: {', '.join(models)})"
                return "Đang hoạt động (chưa cài đặt model nào)"
            return f"Phản hồi mã trạng thái {response.status}"
    except urllib.error.URLError:
        return "Không thể kết nối (máy chủ Ollama chưa được bật hoặc chưa cài đặt)"
    except Exception as err:
        return f"Lỗi kiểm tra ({err})"


def check_edge_browser() -> str:
    """Kiểm tra trình duyệt Microsoft Edge có sẵn trên Windows hay không."""
    which_edge = shutil.which("msedge")
    if which_edge:
        return f"Có sẵn ({which_edge})"

    common_paths = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    ]

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        common_paths.append(
            Path(local_appdata) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        )

    for p in common_paths:
        if p.is_file():
            return f"Có sẵn ({p})"

    return "Không tìm thấy"


def run_doctor() -> int:
    """Thực thi chẩn đoán toàn diện môi trường hệ thống cho Trợ Lý AI."""
    print("=" * 65)
    print(f"BÁO CÁO CHẨN ĐOÁN MÔI TRƯỜNG TRỢ LÝ AI (v{__version__})")
    print("=" * 65)

    # 1. Phiên bản Python
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_status = "[OK]" if sys.version_info >= (3, 11) else "[CẢNH BÁO]"
    print(f"1. Phiên bản Python         : {py_status} {py_ver}")

    # 2. Cấu hình & Thư mục
    config = load_config(create_dirs=True)
    setup_logging(data_dir=config.data_dir, log_level=config.log_level)

    ws_status = "[TỒN TẠI]" if config.workspace_dir.exists() else "[CHƯA TẠO]"
    print(f"2. Thư mục làm việc (WS)    : {ws_status} {config.workspace_dir}")

    data_status = "[TỒN TẠI]" if config.data_dir.exists() else "[CHƯA TẠO]"
    print(f"3. Thư mục dữ liệu (Data)   : {data_status} {config.data_dir}")

    # 3. Khóa Gemini API
    gemini_key_status = check_gemini_key()
    print(f"4. Tìm thấy GEMINI_API_KEY  : {gemini_key_status}")

    # 4. Ollama Cục bộ
    ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    ollama_status = check_ollama(ollama_host)
    print(f"5. Máy chủ Ollama ({ollama_host}): {ollama_status}")

    # 5. Microsoft Edge
    edge_status = check_edge_browser()
    print(f"6. Trình duyệt MS Edge      : {edge_status}")

    print("=" * 65)
    print("Chẩn đoán hoàn tất.")
    return 0


def cli() -> None:
    """Hàm điểm đầu (entry point) khi chạy lệnh `assistant` trên terminal."""
    parser = argparse.ArgumentParser(
        prog="assistant",
        description="Trợ lý AI trên Windows (AI Assistant)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Hiển thị phiên bản ứng dụng",
    )

    subparsers = parser.add_subparsers(dest="command", help="Lệnh chức năng")

    # Lệnh doctor
    subparsers.add_parser("doctor", help="Kiểm tra môi trường và các kết nối hệ thống")

    args = parser.parse_args()

    if args.command == "doctor":
        sys.exit(run_doctor())
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    cli()
