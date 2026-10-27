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

:: 2. Kiểm tra thư viện phụ thuộc (tự động cài đặt nếu thiếu uvicorn)
python -c "import uvicorn" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [*] Chưa phát hiện gói uvicorn. Đang tự động cài đặt các phụ thuộc...
    python -m pip install "uvicorn[standard]>=0.28.0" "fastapi>=0.110.0" "websockets>=12.0" "pystray>=0.19.5" "Pillow>=10.2.0" "apscheduler>=3.10.4,<4.0.0" "winotify>=1.1.0" "pypdf>=4.0.0" "python-docx>=1.1.0" "openpyxl>=3.1.0" "python-multipart>=0.0.9" "pyinstaller>=6.5.0"
    if %ERRORLEVEL% neq 0 (
        echo [*] Đang thử cập nhật gói qua pyproject.toml...
        taskkill /F /IM assistant.exe 2>nul
        python -m pip install -e ".[dev]"
    )
    if %ERRORLEVEL% neq 0 (
        echo [LỖI] Cài đặt phụ thuộc thất bại. Vui lòng kiểm tra kết nối mạng hoặc môi trường Python.
        pause
        exit /b %ERRORLEVEL%
    )
)


:: 3. Thiết lập đường dẫn nguồn dự án (đảm bảo luôn tìm thấy module assistant)
set PYTHONPATH=%CD%\src;%PYTHONPATH%

:: 4. Tự sửa liên kết assistant nếu bị lỗi phân phối dở dang
python -c "import assistant" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [*] Đang thiết lập lại liên kết gói assistant...
    taskkill /F /IM assistant.exe 2>nul
    python -m pip install -e . --no-deps
)

:: 5. Khởi động Trợ lý AI
echo [*] Đang khởi chạy máy chủ backend và giao diện Desktop...
echo.

python -m assistant ui


if %ERRORLEVEL% neq 0 (
    echo.
    echo [LỖI] Ứng dụng đã kết thúc với mã lỗi %ERRORLEVEL%.
    pause
)

