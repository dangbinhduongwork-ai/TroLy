"""Môi trường kiểm tra Python và Git ban đầu cho dự án Trợ lý AI."""

import shutil
import subprocess
import sys


def check_python_version() -> bool:
    """Kiểm tra phiên bản Python có từ 3.11 trở lên hay không."""
    major, minor, micro = sys.version_info[:3]
    version_str = f"{major}.{minor}.{micro}"
    print(f"[INFO] Phiên bản Python hiện tại: {version_str}")

    if sys.version_info < (3, 11):
        print("[LỖI] Phiên bản Python không đạt yêu cầu!")
        print("  - Yêu cầu tối thiểu: Python 3.11+")
        print("  - Hướng dẫn cài đặt:")
        print("    1. Truy cập https://www.python.org/downloads/windows/")
        print("    2. Tải bản cài đặt Python 3.11 hoặc 3.12 (64-bit).")
        print("    3. Khi cài đặt, NHỚ TÍCH CHỌN: 'Add python.exe to PATH'.")
        return False

    print("  -> Đạt yêu cầu Python (>= 3.11).")
    return True


def check_git_installed() -> bool:
    """Kiểm tra Git đã được cài đặt và có trong PATH chưa."""
    git_path = shutil.which("git")
    if not git_path:
        print("[LỖI] Không tìm thấy Git trên máy tính!")
        print("  - Hướng dẫn cài đặt:")
        print("    1. Truy cập https://git-scm.com/download/win")
        print("    2. Tải bản cài đặt '64-bit Git for Windows Setup'.")
        print("    3. Cài đặt theo các tuỳ chọn mặc định.")
        print("    4. Mở lại terminal sau khi cài đặt xong.")
        return False

    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        git_ver = result.stdout.strip()
        print(f"[INFO] Git đã được cài đặt: {git_ver} (tại {git_path})")
        print("  -> Đạt yêu cầu Git.")
        return True
    except Exception as err:
        print(f"[CẢNH BÁO] Tìm thấy git nhưng không thể chạy: {err}")
        return False


def main() -> int:
    """Chạy toàn bộ kiểm tra môi trường ban đầu."""
    print("=" * 60)
    print("KIỂM TRA ĐIỀU KIỆN TIÊN QUYẾT: PYTHON VÀ GIT (GIAI ĐOẠN 0)")
    print("=" * 60)

    py_ok = check_python_version()
    git_ok = check_git_installed()

    print("-" * 60)
    if py_ok and git_ok:
        print("[THÀNH CÔNG] Môi trường máy tính của bạn đã sẵn sàng cho Giai đoạn 0!")
        return 0

    print("[CẦN XỬ LÝ] Vui lòng cài đặt các công cụ còn thiếu theo hướng dẫn trên.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
