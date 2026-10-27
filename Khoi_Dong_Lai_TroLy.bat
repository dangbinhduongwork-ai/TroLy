@echo off
chcp 65001 >nul
title Khởi Động Lại Trợ Lý AI

echo ========================================================
echo  ĐANG KHỞI ĐỘNG LẠI TRỢ LÝ AI (RESTART)
echo ========================================================
echo.

cd /d "%~dp0"

echo [*] Đang đóng các tiến trình Trợ Lý cũ đang chạy ngầm...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    taskkill /F /PID %%a 2>nul
)
taskkill /F /IM pythonw.exe 2>nul

echo [*] Đang nạp mã nguồn mới nhất và khởi chạy ứng dụng...
echo.
call "%~dp0scripts\run_app.bat"
