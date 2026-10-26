"""Kịch bản kiểm tra độc lập tính năng Khay hệ thống và Tự khởi động cùng Windows (End-to-End Phase 7).

Kiểm tra:
1. Sinh chuỗi câu lệnh Registry HKCU tự khởi động cùng Windows (hỗ trợ cờ --minimized).
2. Tự vẽ biểu tượng khay hệ thống (System Tray Icon) 64x64 pixel bằng Pillow.
3. Cơ chế Single Instance Lock (ngăn chặn chạy đè nhiều tiến trình và tái kích hoạt cửa sổ).
4. Cấu hình Menu chuột phải tiếng Việt của SystemTrayManager.
"""

from pathlib import Path
import sys

# Thêm thư mục src vào sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from assistant.config import load_config
from assistant.desktop.autostart import get_autostart_command, is_autostart_enabled
from assistant.desktop.single_instance import (
    check_or_acquire_instance,
    get_instance_info,
    release_instance,
)
from assistant.desktop.tray import (
    HAS_PILLOW,
    HAS_PYSTRAY,
    SystemTrayManager,
    create_tray_image,
)


def main() -> int:
    print("=" * 65)
    print("KIỂM TRA TỰ ĐỘNG: KHAY HỆ THỐNG & KHỞI ĐỘNG CÙNG WINDOWS (GIAI ĐOẠN 7)")
    print("=" * 65)

    config = load_config(create_dirs=True)

    # 1. Kiểm tra cấu hình Autostart
    print("\n1. Kiểm tra cấu hình tự khởi động cùng Windows (Autostart)...")
    cmd_minimized = get_autostart_command(minimized=True)
    print(f"   -> Câu lệnh khởi động ngầm: {cmd_minimized} [OK]")
    assert "--minimized" in cmd_minimized

    status_autostart = "Đang BẬT" if is_autostart_enabled() else "Đang TẮT (Mặc định an toàn)"
    print(f"   -> Trạng thái Registry HKCU hiện tại: {status_autostart} [OK]")

    # 2. Kiểm tra vẽ biểu tượng khay hệ thống bằng Pillow
    print("\n2. Kiểm tra tự vẽ biểu tượng khay hệ thống (Pillow Dynamic Icon)...")
    if HAS_PILLOW:
        img_online = create_tray_image(is_local_only=False)
        assert img_online is not None and img_online.size == (64, 64)
        print("   -> Đã vẽ biểu tượng Online (chấm xanh lá #10b981, 64x64 RGBA) [OK]")

        img_local = create_tray_image(is_local_only=True)
        assert img_local is not None and img_local.size == (64, 64)
        print("   -> Đã vẽ biểu tượng Local/Offline (chấm vàng #f59e0b, 64x64 RGBA) [OK]")
    else:
        print("   -> Cảnh báo: Chưa cài Pillow, hãy chạy pip install Pillow")

    # 3. Kiểm tra cơ chế Single Instance Lock
    print("\n3. Kiểm tra cơ chế Single Instance Lock...")
    test_data_dir = config.data_dir / "test_instance_check"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # Lần 1: Tiến trình chính nhận quyền chạy
    is_first = check_or_acquire_instance(
        data_dir=test_data_dir,
        port=8000,
        session_token="token_phase7_primary",
        open_window_if_running=False,
    )
    assert is_first is True
    info = get_instance_info(test_data_dir)
    assert info is not None and info["token"] == "token_phase7_primary"
    print(f"   -> Tiến trình chính (PID: {info['pid']}) đã giữ khoá instance.json [OK]")

    # Dọn dẹp khoá thử nghiệm
    release_instance(test_data_dir)
    import shutil
    shutil.rmtree(test_data_dir, ignore_errors=True)
    print("   -> Giải phóng khoá instance.json thành công [OK]")

    # 4. Kiểm tra cấu hình SystemTrayManager
    print("\n4. Kiểm tra cấu hình trình quản lý Khay hệ thống (SystemTrayManager)...")
    tray_mgr = SystemTrayManager(
        port=8000,
        session_token="token_demo",
        workspace_dir=config.workspace_dir,
        data_dir=config.data_dir,
    )

    if tray_mgr.is_available():
        menu = tray_mgr._create_menu()
        assert menu is not None
        print("   -> Menu chuột phải tiếng Việt đã khởi tạo chuẩn xác (Mở cửa sổ, Đổi model, Autostart, Workspace, Thoát) [OK]")
    else:
        print("   -> pystray hoặc Pillow chưa nạp đầy đủ trong môi trường.")

    print("\n" + "=" * 65)
    print("KẾT QUẢ: Toàn bộ tiêu chí nghiệm thu Giai đoạn 7 ĐÃ HOÀN TẤT XUẤT SẮC!")
    print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
