"""Kiểm thử tự động cho các công cụ hệ thống (files, apps, system, schema_adapters)."""

from pathlib import Path
from assistant.llm.schema_adapters import to_gemini_tools, to_ollama_tools
from assistant.safety.paths import resolve_in_workspace
from assistant.tools.files import (
    append_file,
    delete_path,
    list_dir,
    make_dir,
    move_path,
    read_text_file,
    rename_path,
    search_files,
    write_file,
)
from assistant.tools.registry import default_tool_registry
from assistant.tools.system import get_system_info


def test_file_tools_lifecycle(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra vòng đời tạo, đọc, nối, đổi tên, tìm kiếm và xoá file an toàn."""
    ws = tmp_path / "test_ws"
    ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WORKSPACE_DIR", str(ws))

    # 1. Tạo thư mục
    res_mkdir = make_dir("docs")
    assert res_mkdir["ok"] is True
    assert (ws / "docs").is_dir()

    # 2. Ghi file
    res_write = write_file("docs/notes.txt", "Dòng đầu tiên.\n")
    assert res_write["ok"] is True
    assert (ws / "docs" / "notes.txt").is_file()

    # 3. Ghi thêm (append)
    res_append = append_file("docs/notes.txt", "Dòng thứ hai.")
    assert res_append["ok"] is True

    # 4. Đọc file
    res_read = read_text_file("docs/notes.txt")
    assert res_read["ok"] is True
    assert "Dòng đầu tiên." in res_read["data"]
    assert "Dòng thứ hai." in res_read["data"]

    # 5. Liệt kê thư mục
    res_list = list_dir("docs")
    assert res_list["ok"] is True
    names = [item["name"] for item in res_list["data"]]
    assert "notes.txt" in names

    # 6. Tìm kiếm file
    res_search_name = search_files(query="notes")
    assert res_search_name["ok"] is True
    assert len(res_search_name["data"]) >= 1

    res_search_content = search_files(query="thứ hai", search_content=True)
    assert res_search_content["ok"] is True
    assert len(res_search_content["data"]) >= 1

    # 6b. Kiểm tra bỏ qua thư mục nặng (.git, node_modules, .venv)
    git_dir = ws / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "notes_git.txt").write_text("Không được tìm thấy", encoding="utf-8")
    res_search_ignore = search_files(query="notes_git")
    assert res_search_ignore["ok"] is True
    assert len(res_search_ignore["data"]) == 0

    # 7. Đổi tên file
    res_rename = rename_path("docs/notes.txt", "notes_renamed.txt")
    assert res_rename["ok"] is True
    assert (ws / "docs" / "notes_renamed.txt").is_file()
    assert not (ws / "docs" / "notes.txt").exists()

    # 8. Di chuyển file
    res_move = move_path("docs/notes_renamed.txt", "root_notes.txt")
    assert res_move["ok"] is True
    assert (ws / "root_notes.txt").is_file()

    # 9. Xoá file an toàn (send2trash)
    res_delete = delete_path("root_notes.txt")
    assert res_delete["ok"] is True
    assert not (ws / "root_notes.txt").exists()


def test_system_info_tool() -> None:
    """Kiểm tra công cụ get_system_info trả về cấu trúc hợp lệ."""
    info = get_system_info()
    assert info["ok"] is True
    data = info["data"]
    assert "current_time" in data
    assert "workspace_disk" in data
    assert "ram" in data
    assert data["workspace_disk"]["free_gb"] > 0


def test_schema_adapters_output() -> None:
    """Kiểm tra chuyển đổi schema sang format Gemini và Ollama."""
    schemas = default_tool_registry.get_schemas()
    assert len(schemas) > 0

    # Chuyển đổi sang Ollama format
    ollama_tools = to_ollama_tools(schemas)
    assert len(ollama_tools) == len(schemas)
    first_ollama = ollama_tools[0]
    assert first_ollama["type"] == "function"
    assert "name" in first_ollama["function"]
    assert "parameters" in first_ollama["function"]

    # Chuyển đổi sang Gemini format
    gemini_tools = to_gemini_tools(schemas)
    assert len(gemini_tools) > 0


def test_open_app_word_boundary_matching(monkeypatch) -> None:
    """Kiểm tra open_app chỉ khớp từ hoàn chỉnh, không bắt nhầm chuỗi con (Fix ERR-05)."""
    from unittest.mock import MagicMock, patch
    from assistant.tools.apps import open_app

    with patch("subprocess.Popen") as mock_popen, patch("assistant.tools.apps._get_start_menu_shortcuts", return_value=[]):
        # 1. Từ "developer" không được khớp với alias "ve" (Paint)
        res_dev = open_app("developer")
        assert res_dev["ok"] is False
        mock_popen.assert_not_called()

        # 2. Khớp chính xác "notepad"
        res_np = open_app("notepad")
        assert res_np["ok"] is True
        mock_popen.assert_called_with(["notepad.exe"], shell=False)

