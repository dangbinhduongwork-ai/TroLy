@echo off
chcp 65001 >nul
title Trợ Lý AI - Đóng Gói Ứng Dụng Windows

cd /d "%~dp0\.."

echo ========================================================
echo  ĐÓNG GÓI TRỢ LÝ AI THÀNH TỆP CHẠY WINDOWS (.EXE)
echo ========================================================
echo.

:: 1. Kích hoạt môi trường ảo nếu có
if exist ".venv\Scripts\activate.bat" (
    echo [*] Kích hoạt môi trường ảo .venv...
    call .venv\Scripts\activate.bat
)

:: 2. Kiểm tra/cài đặt các thư viện phụ thuộc và PyInstaller
python -c "import uvicorn, PyInstaller" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [*] Đang cập nhật gói phụ thuộc và PyInstaller...
    python -m pip install "uvicorn[standard]>=0.28.0" "fastapi>=0.110.0" "websockets>=12.0" "pystray>=0.19.5" "Pillow>=10.2.0" "apscheduler>=3.10.4,<4.0.0" "winotify>=1.1.0" "pypdf>=4.0.0" "python-docx>=1.1.0" "openpyxl>=3.1.0" "pyinstaller>=6.5.0"
)



:: 3. Thiết lập đường dẫn nguồn dự án
set PYTHONPATH=%CD%\src;%PYTHONPATH%

:: 4. Chạy script đóng gói
python scripts/build_exe.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [LỖI] Đóng gói thất bại với mã lỗi %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause
