"""Bộ kiểm thử an ninh đường dẫn (Security Attack Tests for safety/paths.py).

Bao gồm hơn 20 kịch bản tấn công:
- Tấn công Path Traversal: "..", "../../", "../../../Windows/System32".
- Tấn công thoát khỏi workspace qua Symlink trỏ ra ngoài.
- Tấn công tên thiết bị đặc biệt của Windows: CON, NUL, AUX, PRN, COM1-9, LPT1-9 (có và không có đuôi mở rộng).
- Tấn công đường dẫn mạng chia sẻ UNC (\\\\server\\share, //server/share).
- Tấn công tiền tố thiết bị hệ thống NT (\\\\?\\, \\??\\).
- Tấn công luồng dữ liệu thay thế NTFS (Alternate Data Streams ':').
- Tấn công ký tự cấm của hệ điều hành Windows (< > " | ? *).
- Tấn công đường dẫn tuyệt đối trỏ tới thư mục nhạy cảm (C:\\Windows).
"""

from pathlib import Path
import pytest

from assistant.safety.paths import PathSecurityError, is_safe_workspace_path, resolve_in_workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "safe_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


# 1-4: Tấn công Path Traversal
def test_attack_path_traversal_single_dotdot(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("../secret.txt", workspace)


def test_attack_path_traversal_double_dotdot(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("../../secret.txt", workspace)


def test_attack_path_traversal_deep(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("../../../../../Windows/System32/cmd.exe", workspace)


def test_attack_path_traversal_inside_subfolder(workspace: Path) -> None:
    sub = workspace / "sub"
    sub.mkdir()
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("sub/../../escaped.txt", workspace)


# 5-6: Tấn công Symlink / Junction trỏ ra ngoài
def test_attack_symlink_pointing_outside(workspace: Path, tmp_path: Path) -> None:
    outside_target = tmp_path / "outside_file.txt"
    outside_target.write_text("Dữ liệu nhạy cảm ngoài workspace", encoding="utf-8")

    link_path = workspace / "innocent_link.txt"
    try:
        link_path.symlink_to(outside_target)
    except (OSError, NotImplementedError):
        # Một số môi trường Windows cần quyền Admin để tạo symlink, nếu không có thì bỏ qua
        pytest.skip("Môi trường không có quyền tạo Symlink")

    with pytest.raises(PathSecurityError):
        resolve_in_workspace("innocent_link.txt", workspace)


# 7-15: Tấn công tên thiết bị cấm của Windows
def test_attack_reserved_device_con(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("CON", workspace)


def test_attack_reserved_device_con_with_extension(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("con.txt", workspace)


def test_attack_reserved_device_nul(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("NUL", workspace)


def test_attack_reserved_device_nul_lower_with_extension(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("nul.dat", workspace)


def test_attack_reserved_device_aux(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("AUX", workspace)


def test_attack_reserved_device_prn(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("prn.txt", workspace)


def test_attack_reserved_device_com1(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("COM1", workspace)


def test_attack_reserved_device_com9(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("com9.log", workspace)


def test_attack_reserved_device_lpt1(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("lpt1", workspace)


# 16-17: Tấn công đường dẫn mạng UNC
def test_attack_unc_backslash(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace(r"\\attacker-server\share\payload.exe", workspace)


def test_attack_unc_forwardslash(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("//attacker-server/share/payload.exe", workspace)


# 18: Tấn công tiền tố thiết bị hệ thống NT
def test_attack_nt_device_prefix(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace(r"\\?\C:\Windows\System32", workspace)


# 19-20: Tấn công luồng dữ liệu thay thế NTFS (ADS)
def test_attack_alternate_data_stream_file(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("document.txt:hidden_payload", workspace)


def test_attack_alternate_data_stream_zone_identifier(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("test.exe:Zone.Identifier", workspace)


# 21-23: Tấn công ký tự cấm trong tên file
def test_attack_invalid_char_pipe(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("file|cmd.txt", workspace)


def test_attack_invalid_char_wildcard(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("file?.txt", workspace)


def test_attack_invalid_char_brackets(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("<payload>.txt", workspace)


# 24-25: Tấn công đường dẫn trống và đường dẫn tuyệt đối ngoài workspace
def test_attack_empty_path(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace("", workspace)


def test_attack_absolute_path_outside(workspace: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_in_workspace(r"C:\Windows\System32", workspace)


# Kiểm tra đường dẫn hợp lệ trong workspace
def test_valid_safe_paths(workspace: Path) -> None:
    safe1 = resolve_in_workspace("test.txt", workspace)
    assert safe1 == (workspace / "test.txt").resolve()

    safe2 = resolve_in_workspace("sub/folder/file.json", workspace)
    assert safe2 == (workspace / "sub" / "folder" / "file.json").resolve()

    assert is_safe_workspace_path("test.txt", workspace) is True
    assert is_safe_workspace_path("../outside.txt", workspace) is False
