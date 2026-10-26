@echo off
chcp 65001 >nul
title Trợ Lý AI - Windows Desktop Launcher

cd /d "%~dp0\.."

echo ========================================================
echo  KHỞI CHẠY TRỢ LÝ AI (WINDOWS DESKTOP APPLICATION)
echo ========================================================
echo.

:: 1. Kiểm tra môi trường ảo
if exist ".venv\Scripts\activate.bat" (
    echo [*] Kích hoạt môi trường ảo .venv...
    call .venv\Scripts\activate.bat
) else (
    echo [*] Sử dụng môi trường Python hệ thống...
)

:: 2. Khởi động Trợ lý AI
echo [*] Đang khởi chạy máy chủ backend và giao diện Desktop...
echo.

python -m assistant ui

if %ERRORLEVEL% neq 0 (
    echo.
    echo [LỖI] Ứng dụng đã kết thúc với mã lỗi %ERRORLEVEL%.
    pause
)
