@echo off
chcp 65001 >nul
echo ========================================================
echo  ĐẨY MÃ NGUỒN LÊN GITHUB (https://github.com/dangbinhduongwork-ai/TroLy)
echo ========================================================

:: 1. Khởi tạo Git nếu chưa có
if not exist ".git" (
    echo [1/5] Khởi tạo git repository...
    git init
    git branch -M main
) else (
    echo [1/5] Git đã được khởi tạo.
)

:: 2. Cấu hình remote origin
echo [2/5] Cấu hình remote origin...
git remote remove origin 2>nul
git remote add origin https://github.com/dangbinhduongwork-ai/TroLy
git branch -M main

:: 3. Thêm file vào staging
echo [3/5] Thêm file vào staging...
git add .

:: 4. Commit mã nguồn
echo [4/5] Tạo commit mã nguồn...
git commit -m "feat(agents): implement document tools, SSRF defense, directory organizer, and specialized agents for phase 5" || git commit -m "feat: phase 5 agents"



:: 5. Đẩy lên GitHub
echo [5/5] Đang đẩy lên GitHub (nhánh main)...
git push -u origin main

if %ERRORLEVEL% neq 0 (
    echo.
    echo [CẢNH BÁO] Nếu GitHub của bạn đã có sẵn file README/license, hãy thử kéo về trước bằng lệnh:
    echo     git pull --rebase origin main
    echo     git push -u origin main
) else (
    echo.
    echo [THÀNH CÔNG] Đã đẩy mã nguồn lên GitHub thành công!
)

echo.
pause
