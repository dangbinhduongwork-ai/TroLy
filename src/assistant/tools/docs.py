"""Bộ công cụ xử lý tài liệu văn phòng (PDF, Word, Excel).

Hỗ trợ:
- read_pdf: Đọc và trích xuất nội dung từ file PDF.
- read_docx: Đọc nội dung văn bản và bảng từ file Word (.docx).
- read_excel: Đọc dữ liệu các sheet từ bảng tính Excel (.xlsx).
- create_docx: Soạn thảo và lưu file Word (.docx) mới trong workspace.
- create_excel: Tạo bảng tính Excel (.xlsx) từ dữ liệu danh sách/cột trong workspace.

Tuân thủ:
- Bọc toàn bộ nội dung đọc được trong thẻ <untrusted_content> để chống prompt injection.
- Kiểm soát đường dẫn tuyệt đối trong workspace qua resolve_in_workspace.
- Phân quyền: Đọc = READ, Tạo mới = WRITE_SAFE, Ghi đè file có sẵn = CONFIRM.
"""

from pathlib import Path
from typing import Any

from assistant.safety.injection import wrap_untrusted_content
from assistant.safety.paths import resolve_in_workspace
from assistant.safety.permissions import PermissionLevel
from assistant.tools.registry import register_tool

# Kiểm tra thư viện xử lý tài liệu
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


@register_tool(
    name="read_pdf",
    description="Đọc và trích xuất nội dung văn bản từ tập tin PDF trong workspace.",
    permission_level=PermissionLevel.READ,
    is_external_content=True,
)
def read_pdf(path: str, max_pages: int = 20) -> dict[str, Any]:
    """Đọc file PDF trong workspace."""
    if not HAS_PYPDF:
        return {
            "ok": False,
            "data": None,
            "error": "Chưa cài đặt thư viện pypdf. Hãy chạy: pip install pypdf",
            "truncated": False,
        }

    try:
        target = resolve_in_workspace(path)
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}

    if not target.is_file():
        return {"ok": False, "data": None, "error": f"Không tìm thấy file: {path}", "truncated": False}

    if target.suffix.lower() != ".pdf":
        return {"ok": False, "data": None, "error": "File không phải định dạng PDF (.pdf)", "truncated": False}

    try:
        reader = pypdf.PdfReader(str(target))
        total_pages = len(reader.pages)
        pages_to_read = min(total_pages, max(1, max_pages))

        extracted_text_chunks: list[str] = []
        for i in range(pages_to_read):
            page_text = reader.pages[i].extract_text() or ""
            extracted_text_chunks.append(f"--- [Trang {i + 1}/{total_pages}] ---\n{page_text.strip()}")

        full_content = "\n\n".join(extracted_text_chunks)
        max_chars = 15000
        truncated = len(full_content) > max_chars
        if truncated:
            full_content = full_content[:max_chars] + f"\n... [Đã cắt bớt nội dung, tổng số trang: {total_pages}]"

        return {
            "ok": True,
            "data": wrap_untrusted_content(full_content, source_label=target.name),
            "error": None,
            "truncated": truncated,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": f"Lỗi đọc file PDF: {err}", "truncated": False}


@register_tool(
    name="read_docx",
    description="Đọc nội dung văn bản và bảng dữ liệu từ file Word (.docx) trong workspace.",
    permission_level=PermissionLevel.READ,
    is_external_content=True,
)
def read_docx(path: str, max_paragraphs: int = 200) -> dict[str, Any]:
    """Đọc file Word (.docx) trong workspace."""
    if not HAS_DOCX:
        return {
            "ok": False,
            "data": None,
            "error": "Chưa cài đặt thư viện python-docx. Hãy chạy: pip install python-docx",
            "truncated": False,
        }

    try:
        target = resolve_in_workspace(path)
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}

    if not target.is_file():
        return {"ok": False, "data": None, "error": f"Không tìm thấy file: {path}", "truncated": False}

    if target.suffix.lower() != ".docx":
        return {"ok": False, "data": None, "error": "File không phải định dạng Word (.docx)", "truncated": False}

    try:
        doc = docx.Document(str(target))
        lines: list[str] = []

        # Đọc các đoạn văn (paragraphs)
        p_count = 0
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                lines.append(text)
                p_count += 1
                if p_count >= max_paragraphs:
                    lines.append(f"... [Đã đạt giới hạn {max_paragraphs} đoạn văn]")
                    break

        # Đọc bảng (tables) nếu có
        for t_idx, table in enumerate(doc.tables, start=1):
            lines.append(f"\n[Bảng {t_idx}]:")
            for row in table.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                lines.append(" | ".join(row_cells))

        full_content = "\n".join(lines)
        max_chars = 15000
        truncated = len(full_content) > max_chars
        if truncated:
            full_content = full_content[:max_chars] + "\n... [Đã cắt bớt nội dung]"

        return {
            "ok": True,
            "data": wrap_untrusted_content(full_content, source_label=target.name),
            "error": None,
            "truncated": truncated,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": f"Lỗi đọc file Word: {err}", "truncated": False}


@register_tool(
    name="read_excel",
    description="Đọc dữ liệu bảng tính từ file Excel (.xlsx) trong workspace.",
    permission_level=PermissionLevel.READ,
    is_external_content=True,
)
def read_excel(
    path: str,
    max_rows: int = 100,
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """Đọc file Excel (.xlsx) trong workspace."""
    if not HAS_OPENPYXL:
        return {
            "ok": False,
            "data": None,
            "error": "Chưa cài đặt thư viện openpyxl. Hãy chạy: pip install openpyxl",
            "truncated": False,
        }

    try:
        target = resolve_in_workspace(path)
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}

    if not target.is_file():
        return {"ok": False, "data": None, "error": f"Không tìm thấy file: {path}", "truncated": False}

    if target.suffix.lower() not in (".xlsx", ".xlsm"):
        return {"ok": False, "data": None, "error": "File không phải định dạng Excel (.xlsx)", "truncated": False}

    try:
        wb = openpyxl.load_workbook(str(target), data_only=True)
        sheets = [sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.sheetnames

        sections: list[str] = []
        for s_name in sheets:
            ws = wb[s_name]
            sections.append(f"=== Sheet: {s_name} ===")

            row_count = 0
            for row in ws.iter_rows(values_only=True):
                # Bỏ qua dòng trống hoàn toàn
                if not any(v is not None for v in row):
                    continue
                row_str = " | ".join(str(v) if v is not None else "" for v in row)
                sections.append(row_str)
                row_count += 1
                if row_count >= max_rows:
                    sections.append(f"... [Đã đạt giới hạn {max_rows} dòng của sheet {s_name}]")
                    break

        full_content = "\n".join(sections)
        max_chars = 15000
        truncated = len(full_content) > max_chars
        if truncated:
            full_content = full_content[:max_chars] + "\n... [Đã cắt bớt nội dung]"

        return {
            "ok": True,
            "data": wrap_untrusted_content(full_content, source_label=target.name),
            "error": None,
            "truncated": truncated,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": f"Lỗi đọc file Excel: {err}", "truncated": False}


@register_tool(
    name="create_docx",
    description="Tạo file Word (.docx) mới trong workspace với tiêu đề và danh sách các đoạn văn.",
    permission_level=PermissionLevel.WRITE_SAFE,
)
def create_docx(
    path: str,
    title: str,
    paragraphs: list[str],
) -> dict[str, Any]:
    """Tạo file Word (.docx) trong workspace."""
    if not HAS_DOCX:
        return {
            "ok": False,
            "data": None,
            "error": "Chưa cài đặt thư viện python-docx. Hãy chạy: pip install python-docx",
            "truncated": False,
        }

    try:
        target = resolve_in_workspace(path)
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}

    if target.suffix.lower() != ".docx":
        target = target.with_suffix(".docx")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        doc = docx.Document()
        if title:
            doc.add_heading(title, level=0)

        for p in paragraphs:
            p_clean = str(p).strip()
            if p_clean:
                doc.add_paragraph(p_clean)

        doc.save(str(target))
        return {
            "ok": True,
            "data": f"Đã tạo thành công file Word tại: {target.name} ({len(paragraphs)} đoạn văn)",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": f"Lỗi tạo file Word: {err}", "truncated": False}


@register_tool(
    name="create_excel",
    description=(
        "Tạo bảng tính Excel (.xlsx) mới trong workspace từ dữ liệu bảng. "
        "Tham số sheets_data có dạng dictionary { tên_sheet: [[hàng_1], [hàng_2], ...] }."
    ),
    permission_level=PermissionLevel.WRITE_SAFE,
)
def create_excel(
    path: str,
    sheets_data: dict[str, list[list[Any]]],
) -> dict[str, Any]:
    """Tạo file Excel (.xlsx) trong workspace."""
    if not HAS_OPENPYXL:
        return {
            "ok": False,
            "data": None,
            "error": "Chưa cài đặt thư viện openpyxl. Hãy chạy: pip install openpyxl",
            "truncated": False,
        }

    try:
        target = resolve_in_workspace(path)
    except Exception as err:
        return {"ok": False, "data": None, "error": str(err), "truncated": False}

    if target.suffix.lower() not in (".xlsx", ".xlsm"):
        target = target.with_suffix(".xlsx")

    if not sheets_data:
        return {
            "ok": False,
            "data": None,
            "error": "Dữ liệu sheets_data không được để trống.",
            "truncated": False,
        }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        wb = openpyxl.Workbook()

        # Xoá sheet mặc định
        first_sheet = True
        total_rows = 0

        for s_name, rows in sheets_data.items():
            if first_sheet:
                ws = wb.active
                ws.title = s_name[:31]  # Excel giới hạn tên sheet tối đa 31 ký tự
                first_sheet = False
            else:
                ws = wb.create_sheet(title=s_name[:31])

            for row in rows:
                if isinstance(row, list):
                    ws.append(row)
                    total_rows += 1

        wb.save(str(target))
        return {
            "ok": True,
            "data": f"Đã tạo thành công file Excel tại: {target.name} ({len(sheets_data)} sheet, {total_rows} dòng)",
            "error": None,
            "truncated": False,
        }
    except Exception as err:
        return {"ok": False, "data": None, "error": f"Lỗi tạo file Excel: {err}", "truncated": False}
