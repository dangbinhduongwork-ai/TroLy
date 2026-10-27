@echo off
setlocal
title Tro Ly AI - Windows Desktop Launcher

cd /d "%~dp0\.."

echo ========================================================
echo  KHOI CHAY TRO LY AI (WINDOWS DESKTOP APPLICATION)
echo ========================================================
echo.

REM 1. Kiem tra moi truong ao
if exist ".venv\Scripts\activate.bat" (
    echo [*] Kich hoat moi truong ao .venv...
    call .venv\Scripts\activate.bat
) else (
    echo [*] Su dung moi truong Python he thong...
)

REM 2. Thiet lap duong dan nguon du an
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM 3. Kiem tra va dam bao goi assistant san sang
python -c "import assistant" 2>nul
if errorlevel 1 (
    echo [*] Dang thiet lap goi assistant...
    python -m pip install -e . --no-deps
)

REM 4. Khoi dong Tro Ly AI
echo [*] Dang khoi chay may chu backend va giao dien Desktop...
echo.

python -m assistant ui

if errorlevel 1 (
    echo.
    echo [LOI] Ung dung da ket thuc voi ma loi %ERRORLEVEL%.
    pause
)
endlocal
