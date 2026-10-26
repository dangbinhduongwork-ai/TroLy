"""Kiểm thử tự động cho bộ công cụ tài liệu (PDF, Word, Excel)."""

from pathlib import Path
from assistant.tools.docs import (
    HAS_DOCX,
    HAS_OPENPYXL,
    HAS_PYPDF,
    create_docx,
    create_excel,
    read_docx,
    read_excel,
    read_pdf,
)


def test_docx_create_and_read(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra tạo file Word (.docx) và đọc lại nội dung trong workspace."""
    if not HAS_DOCX:
        return

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))

    # 1. Tạo file Word
    res_create = create_docx(
        path="bao-cao.docx",
        title="Báo Cáo Tình Hình Hoạt Động Q3",
        paragraphs=[
            "Dự án đã đạt 95% mục tiêu đề ra trong giai đoạn quý 3.",
            "Các tính năng chính đã hoàn thành kiểm thử tự động.",
        ],
    )
    assert res_create["ok"] is True
    assert (tmp_path / "bao-cao.docx").is_file()

    # 2. Đọc file Word
    res_read = read_docx("bao-cao.docx")
    assert res_read["ok"] is True
    data_str = res_read["data"]
    assert "<untrusted_content" in data_str
    assert "Báo Cáo Tình Hình Hoạt Động Q3" in data_str
    assert "95% mục tiêu" in data_str


def test_excel_create_and_read(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra tạo bảng tính Excel (.xlsx) và đọc lại dữ liệu các sheet."""
    if not HAS_OPENPYXL:
        return

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))

    # 1. Tạo file Excel
    sheets = {
        "ChiTieu": [
            ["Khoản chi", "Số tiền (VNĐ)", "Ghi chú"],
            ["Tiền thuê nhà", 15000000, "Tháng 10"],
            ["Tiền điện nước", 1200000, "Tháng 10"],
        ],
        "DoanhThu": [
            ["Nguồn thu", "Số tiền"],
            ["Khách hàng A", 50000000],
        ],
    }

    res_create = create_excel("tai-chinh.xlsx", sheets_data=sheets)
    assert res_create["ok"] is True
    assert (tmp_path / "tai-chinh.xlsx").is_file()

    # 2. Đọc file Excel
    res_read = read_excel("tai-chinh.xlsx")
    assert res_read["ok"] is True
    data_str = res_read["data"]
    assert "<untrusted_content" in data_str
    assert "ChiTieu" in data_str
    assert "Tiền thuê nhà" in data_str
    assert "DoanhThu" in data_str


def test_pdf_read_with_sample(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra đọc file PDF bằng pypdf (tạo file mẫu để đọc)."""
    if not HAS_PYPDF:
        return

    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))

    # Tạo một file PDF mẫu tối thiểu bằng pypdf
    import pypdf

    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    pdf_path = tmp_path / "sample.pdf"
    with pdf_path.open("wb") as f:
        writer.write(f)

    # Đọc lại bằng công cụ read_pdf
    res_read = read_pdf("sample.pdf")
    assert res_read["ok"] is True
    assert "<untrusted_content" in res_read["data"]


def test_docs_path_traversal_blocked(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra các công cụ tài liệu chặn đứng path traversal."""
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))

    res_pdf = read_pdf("../../secret.pdf")
    assert res_pdf["ok"] is False
    assert "vượt ra ngoài" in res_pdf["error"]

    res_docx = read_docx("../outside.docx")
    assert res_docx["ok"] is False

    res_excel = read_excel("C:/Windows/test.xlsx")
    assert res_excel["ok"] is False
