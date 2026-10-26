# -*- mode: python ; coding: utf-8 -*-
"""Cấu hình đóng gói PyInstaller cho ứng dụng Trợ Lý AI trên Windows.

Đặc tính:
- Chế độ thư mục (--onedir): Tối ưu tốc độ khởi động và tránh báo động giả từ Windows Defender.
- Không hiện cửa sổ console (--noconsole / console=False): Tránh bật màn hình đen làm phiền người dùng.
- Đính kèm thư mục giao diện tĩnh (ui_static) và file cấu hình toml mẫu.
"""

from pathlib import Path
import sys

block_cipher = None
project_root = Path.cwd()

# Thu thập tệp tĩnh và cấu hình
datas = [
    (str(project_root / "src" / "assistant" / "ui_static"), "assistant/ui_static"),
    (str(project_root / "config" / "settings.toml"), "config"),
]

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "pystray._win32",
    "winotify",
    "PIL._imaging",
    "engineio.async_drivers.asgi",
    "sqlite3",
    "apscheduler.triggers.date",
    "apscheduler.triggers.cron",
    "keyring.backends.Windows",
    "pypdf",
    "docx",
    "openpyxl",
]

a = Analysis(
    [str(project_root / "src" / "assistant" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Trợ Lý AI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Assistant",
)
