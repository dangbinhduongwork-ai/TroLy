@echo off
chcp 65001 >nul
echo =====================================================================
echo  [KIỂM TOÁN & HỒI QUY TOÀN BỘ] DỰ ÁN TRỢ LÝ AI (WINDOWS)
echo =====================================================================

set "PROJECT_DIR=%~dp0.."
cd /d "%PROJECT_DIR%"
set "PYTHONPATH=%PROJECT_DIR%\src;%PYTHONPATH%"

:: 1. Xác định trình thông dịch Python
set "PYTHON_EXE=python"
if exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"
)

echo [*] Trình thông dịch: %PYTHON_EXE%
echo [*] Thư mục dự án:    %PROJECT_DIR%
echo.

:: 2. Chạy Ruff Linter
echo ---------------------------------------------------------------------
echo [1/3] Kiểm tra chuẩn mã nguồn và bảo mật bằng Ruff...
echo ---------------------------------------------------------------------
%PYTHON_EXE% -m ruff check src tests scripts
if %errorlevel% neq 0 (
    echo [!] Cảnh báo: Ruff phát hiện vấn đề cần xử lý.
) else (
    echo [OK] Ruff kiểm tra hoàn toàn sạch!
)
echo.

:: 3. Chạy Pytest toàn diện
echo ---------------------------------------------------------------------
echo [2/3] Chạy bộ kiểm thử tự động toàn diện (20 test suites)...
echo ---------------------------------------------------------------------
%PYTHON_EXE% -m pytest -v
if %errorlevel% neq 0 (
    echo [!] Cảnh báo: Một số bài test tự động không vượt qua.
) else (
    echo [OK] Toàn bộ bài kiểm thử tự động đã vượt qua (100%% PASSED)!
)
echo.

:: 4. Chạy kiểm tra giao diện bằng Playwright (nếu có)
echo ---------------------------------------------------------------------
echo [3/3] Chạy kiểm thử tự động giao diện Playwright (scripts/ui_check.py)...
echo ---------------------------------------------------------------------
%PYTHON_EXE% scripts/ui_check.py
if %errorlevel% neq 0 (
    echo [!] Lưu ý: scripts/ui_check.py hoàn thành với một số lưu ý hoặc thiếu thư viện dev Playwright.
) else (
    echo [OK] Kiểm thử giao diện Playwright hoàn tất! Ảnh chụp lưu tại docs/ui-shots/
)
echo.

echo =====================================================================
echo  [HOÀN TẤT KIỂM TOÁN VÀ HỒI QUY]
echo  Chi tiết báo cáo được ghi nhận tại docs/AUDIT.md và docs/QA.md
echo =====================================================================
pause
