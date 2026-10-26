"""Kiểm thử tự động cho công cụ sắp xếp dọn dẹp thư mục (organize_directory)."""

from pathlib import Path
from assistant.tools.files import organize_directory


def test_organize_directory_plan_only(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra tạo kế hoạch xem trước (execute=False) không thay đổi vị trí file."""
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))

    # Tạo các file mẫu
    (tmp_path / "photo.png").write_text("image")
    (tmp_path / "document.pdf").write_text("pdf")
    (tmp_path / "script.py").write_text("python")

    res = organize_directory(".", strategy="by_extension", execute=False)
    assert res["ok"] is True
    data = res["data"]
    assert data["total_files"] == 3
    assert len(data["plan"]) == 3

    # Xác nhận các file gốc vẫn ở vị trí cũ, chưa di chuyển
    assert (tmp_path / "photo.png").is_file()
    assert (tmp_path / "document.pdf").is_file()
    assert (tmp_path / "script.py").is_file()


def test_organize_directory_execute(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra thực thi di chuyển file (execute=True) theo phần mở rộng."""
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))

    # Tạo các file mẫu
    (tmp_path / "cat.jpg").write_text("image")
    (tmp_path / "notes.txt").write_text("text")
    (tmp_path / "app.js").write_text("javascript")

    res = organize_directory(".", strategy="by_extension", execute=True)
    assert res["ok"] is True
    assert "Đã sắp xếp thành công" in res["data"]

    # Kiểm tra các thư mục phân loại đã được tạo và file đã được chuyển vào
    assert (tmp_path / "Images" / "cat.jpg").is_file()
    assert (tmp_path / "Documents" / "notes.txt").is_file()
    assert (tmp_path / "Code" / "app.js").is_file()

    # File ở thư mục gốc không còn
    assert not (tmp_path / "cat.jpg").exists()
    assert not (tmp_path / "notes.txt").exists()
    assert not (tmp_path / "app.js").exists()
