"""Kịch bản tự động đóng gói ứng dụng Windows bằng PyInstaller (scripts/build_exe.py).

Tuân thủ:
- Chế độ thư mục (--onedir) và không cửa sổ console (--noconsole).
- Gọi PyInstaller qua subprocess với tham số dạng list (shell=False) theo Nguyên tắc 4.
- Tự động tạo Shortcut "Trợ Lý AI" ngoài màn hình Desktop của người dùng.
- Kiểm tra tính toàn vẹn của gói cài đặt sau khi đóng gói.
"""

import os
from pathlib import Path
import subprocess
import sys


def get_desktop_dir() -> Path:
    """Xác định đường dẫn thư mục Desktop của người dùng Windows hiện tại."""
    userprofile = os.getenv("USERPROFILE")
    if userprofile:
        desktop = Path(userprofile) / "Desktop"
        if desktop.is_dir():
            return desktop
    return Path.home() / "Desktop"


def create_desktop_shortcut(target_exe: Path, shortcut_name: str = "Trợ Lý AI.lnk") -> bool:
    """Tạo phím tắt (Shortcut .lnk) ngoài Desktop bằng PowerShell COM Object WScript.Shell."""
    desktop_dir = get_desktop_dir()
    if not desktop_dir.is_dir():
        print(f"⚠️  Không tìm thấy thư mục Desktop tại: {desktop_dir}")
        return False

    shortcut_path = desktop_dir / shortcut_name
    working_dir = target_exe.parent

    ps_command = (
        f"$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{shortcut_path}'); "
        f"$Shortcut.TargetPath = '{target_exe}'; "
        f"$Shortcut.WorkingDirectory = '{working_dir}'; "
        f"$Shortcut.Description = 'Trợ Lý AI trên Windows (AI Assistant)'; "
        f"$Shortcut.Save()"
    )

    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            shell=False,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and shortcut_path.is_file():
            print(f"✅ Đã tạo phím tắt tiện ích ngoài Desktop: {shortcut_path}")
            return True
        else:
            print(f"⚠️  Không thể tạo shortcut ngoài Desktop: {res.stderr}")
            return False
    except Exception as err:
        print(f"⚠️  Lỗi khi gọi PowerShell tạo shortcut: {err}")
        return False


def build() -> int:
    """Thực thi toàn bộ quy trình đóng gói ứng dụng."""
    project_root = Path(__file__).resolve().parent.parent
    spec_file = project_root / "assistant.spec"

    print("=" * 65)
    print("🚀 BẮT ĐẦU ĐÓNG GÓI ỨNG DỤNG WINDOWS BẰNG PYINSTALLER")
    print(f"Thư mục dự án : {project_root}")
    print(f"Tệp cấu hình   : {spec_file}")
    print("=" * 65)

    if not spec_file.is_file():
        print(f"❌ [LỖI] Không tìm thấy file cấu hình đóng gói: {spec_file}")
        return 1

    # 1. Kiểm tra thư viện PyInstaller
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("❌ [LỖI] Chưa cài đặt PyInstaller trong môi trường Python hiện hành.")
        print("   Hãy cài đặt bổ sung bằng lệnh: pip install pyinstaller")
        return 1

    # 2. Thực thi PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(spec_file),
    ]

    print("\n[*] Đang biên dịch và thu thập dependencies (vui lòng chờ trong giây lát)...")
    try:
        proc = subprocess.run(cmd, cwd=str(project_root), shell=False)
        if proc.returncode != 0:
            print(f"\n❌ [LỖI] Quá trình PyInstaller thất bại với mã lỗi {proc.returncode}.")
            return proc.returncode
    except Exception as err:
        print(f"\n❌ [LỖI] Không thể thực thi PyInstaller: {err}")
        return 1

    # 3. Kiểm tra tính toàn vẹn của tệp .exe
    output_exe = project_root / "dist" / "Assistant" / "Trợ Lý AI.exe"
    if not output_exe.is_file():
        # Thử tìm file .exe khác nếu tên bị thay đổi
        exes = list((project_root / "dist" / "Assistant").glob("*.exe"))
        if exes:
            output_exe = exes[0]
        else:
            print(f"❌ [LỖI] Không tìm thấy tệp .exe tại: {output_exe}")
            return 1

    print("\n" + "=" * 65)
    print("🎉 ĐÓNG GÓI THÀNH CÔNG!")
    print(f"📁 Thư mục kết quả: {output_exe.parent}")
    print(f"🚀 Tệp chạy chính : {output_exe}")
    print("=" * 65)

    # 4. Tự động tạo Shortcut ngoài Desktop
    create_desktop_shortcut(output_exe, shortcut_name="Trợ Lý AI.lnk")

    print("\n💡 Hướng dẫn sử dụng:")
    print("1. Bạn có thể bấm đúp chuột vào shortcut 'Trợ Lý AI' ngoài Desktop để mở app.")
    print("2. Ứng dụng sẽ tự động chạy ngầm ở Khay hệ thống (System Tray) và mở cửa sổ chat.")
    print("3. Để sao chép sang máy khác, hãy copy toàn bộ thư mục 'dist/Assistant/'.\n")
    return 0


if __name__ == "__main__":
    sys.exit(build())
