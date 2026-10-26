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

:: 2. Kiểm tra/cài đặt PyInstaller
python -c "import PyInstaller" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [*] Đang cài đặt thư viện PyInstaller...
    pip install pyinstaller
)

:: 3. Chạy script đóng gói
python scripts/build_exe.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [LỖI] Đóng gói thất bại với mã lỗi %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause
