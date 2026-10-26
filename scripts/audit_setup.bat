@echo off
chcp 65001 >nul
title Trợ Lý AI - Khởi Tạo Nhánh Kiểm Toán fix/audit-1

cd /d "%~dp0\.."

echo ========================================================
echo  KHỞI TẠO NHÁNH KIỂM TOÁN VÀ KIỂM TRA MÔI TRƯỜNG
echo ========================================================
echo.

:: 1. Kiểm tra Git và chuyển sang nhánh fix/audit-1
echo [*] Kiểm tra trạng thái Git...
git rev-parse --is-inside-work-tree >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [LỖI] Thư mục hiện tại không phải là git repository!
    pause
    exit /b 1
)

echo [*] Tạo và chuyển sang nhánh mới 'fix/audit-1'...
git checkout -b fix/audit-1 2>nul
if %ERRORLEVEL% neq 0 (
    echo [*] Nhánh 'fix/audit-1' đã tồn tại, đang chuyển sang nhánh...
    git checkout fix/audit-1
)

:: 2. Kích hoạt môi trường ảo
if exist ".venv\Scripts\activate.bat" (
    echo [*] Kích hoạt môi trường ảo .venv...
    call .venv\Scripts\activate.bat
) else (
    echo [*] Không tìm thấy .venv, đang tạo mới môi trường ảo...
    python -m venv .venv
    call .venv\Scripts\activate.bat
)

:: 3. Đặt PYTHONPATH
set PYTHONPATH=%CD%\src;%PYTHONPATH%

:: 4. Kiểm tra và cập nhật cài đặt gói ở chế độ phát triển
echo [*] Cài đặt gói assistant và phụ thuộc phát triển...
taskkill /F /IM assistant.exe 2>nul
pip install -e ".[dev]"

echo.
echo ========================================================
echo  ĐÃ CHUYỂN SANG NHÁNH fix/audit-1 VÀ HOÀN TẤT THIẾT LẬP!
echo ========================================================
echo.
pause
