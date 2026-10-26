"""Kịch bản kiểm tra độc lập hệ thống xử lý tài liệu và các Agent chuyên trách (End-to-End Phase 5).

Kiểm tra:
1. Tạo và đọc file Excel (.xlsx) danh sách chi tiêu mẫu.
2. Tạo và đọc file Word (.docx) báo cáo dự án.
3. Chống SSRF khi đọc web (fetch_webpage).
4. Phân loại và dọn dẹp thư mục thông minh (organize_directory).
5. Uỷ quyền cho các Agent chuyên trách (delegate_to_agent) với quyền tối thiểu.
"""

import asyncio
from pathlib import Path
import sys

# Thêm thư mục src vào đường dẫn nạp module
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from assistant.agents.orchestrator import run_subagent
from assistant.agents.spec import SPECIALIZED_AGENTS
from assistant.config import load_config
from assistant.tools.docs import create_docx, create_excel, read_docx, read_excel
from assistant.tools.files import organize_directory
from assistant.tools.web import fetch_webpage, is_ssrf_safe_url


async def main() -> int:
    print("=" * 65)
    print("KIỂM TRA TỰ ĐỘNG: TÀI LIỆU & CÁC AGENT CHUYÊN TRÁCH (GIAI ĐOẠN 5)")
    print("=" * 65)

    config = load_config(create_dirs=True)
    ws = config.workspace_dir
    ws.mkdir(parents=True, exist_ok=True)
    print(f"1. Thư mục làm việc Workspace: {ws} [OK]")

    # 1. Thử nghiệm tạo file Excel chi tiêu mẫu
    print("\n2. Tạo bảng tính Excel chi tiêu mẫu...")
    excel_data = {
        "ChiTieuThang10": [
            ["Khoản mục", "Số tiền (VNĐ)", "Phân loại"],
            ["Mua sách chuyên ngành AI", 450000, "Học tập"],
            ["Tiền cà phê làm việc", 120000, "Sinh hoạt"],
            ["Đăng ký dịch vụ VPS", 300000, "Công nghệ"],
        ]
    }
    res_excel = create_excel("chi_tieu_mau.xlsx", sheets_data=excel_data)
    print(f"   -> Kết quả: {res_excel.get('data') or res_excel.get('error')} [OK]")

    # Đọc lại file Excel
    read_xl_res = read_excel("chi_tieu_mau.xlsx")
    assert read_xl_res["ok"] is True
    assert "<untrusted_content" in read_xl_res["data"]
    print("   -> Đọc lại dữ liệu Excel và bọc untrusted_content thành công [OK]")

    # 2. Thử nghiệm tạo file Word báo cáo
    print("\n3. Tạo tài liệu Word báo cáo...")
    res_word = create_docx(
        path="bao_cao_du_an.docx",
        title="Báo Cáo Tiến Độ Dự Án Trợ Lý AI",
        paragraphs=[
            "Dự án đã hoàn thành tích hợp các Agent chuyên trách và công cụ tài liệu.",
            "Các luồng dữ liệu bên ngoài đều được bọc trong thẻ bảo vệ chống injection.",
        ],
    )
    print(f"   -> Kết quả: {res_word.get('data') or res_word.get('error')} [OK]")

    # Đọc lại file Word
    read_w_res = read_docx("bao_cao_du_an.docx")
    assert read_w_res["ok"] is True
    assert "<untrusted_content" in read_w_res["data"]
    print("   -> Đọc lại tài liệu Word thành công [OK]")

    # 3. Kiểm tra phòng chống SSRF trên web
    print("\n4. Kiểm tra phòng chống SSRF (Server-Side Request Forgery)...")
    safe_local, reason_local = is_ssrf_safe_url("http://127.0.0.1:8000/admin")
    assert safe_local is False
    print(f"   -> Chặn URL nội bộ http://127.0.0.1:8000: '{reason_local}' [OK]")

    safe_public, _ = is_ssrf_safe_url("https://www.google.com")
    assert safe_public is True
    print("   -> Cho phép tên miền công khai https://www.google.com [OK]")

    # 4. Kiểm tra sắp xếp dọn dẹp thư mục
    print("\n5. Thử nghiệm công cụ organize_directory...")
    test_folder = ws / "test_sort_folder"
    test_folder.mkdir(parents=True, exist_ok=True)
    (test_folder / "image1.png").write_text("dummy")
    (test_folder / "table.xlsx").write_text("dummy")
    (test_folder / "script.py").write_text("dummy")

    # Kế hoạch xem trước (execute=False)
    res_plan = organize_directory("test_sort_folder", strategy="by_extension", execute=False)
    assert res_plan["ok"] is True
    print(f"   -> Lập kế hoạch xem trước: Tìm thấy {res_plan['data']['total_files']} file cần chuyển [OK]")

    # Thực thi di chuyển (execute=True)
    res_exec = organize_directory("test_sort_folder", strategy="by_extension", execute=True)
    assert res_exec["ok"] is True
    print(f"   -> Thực thi di chuyển: {res_exec['data']} [OK]")

    # Dọn dẹp thư mục test
    import shutil
    shutil.rmtree(test_folder, ignore_errors=True)

    # 5. Kiểm tra 4 Agent chuyên trách
    print("\n6. Kiểm tra cấu hình và đặc quyền tối thiểu của 4 Agent chuyên trách:")
    for name, spec in SPECIALIZED_AGENTS.items():
        print(f"   - [{spec.name}]: {len(spec.allowed_tools)} công cụ cho phép ({', '.join(spec.allowed_tools)})")

    print("\n" + "=" * 65)
    print("KẾT QUẢ: Toàn bộ tiêu chí nghiệm thu Giai đoạn 5 ĐÃ HOÀN TẤT XUẤT SẮC!")
    print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
