@echo off
chcp 65001 >nul
echo ========================================================
echo  KHOI TAO DU AN TRO LY AI (GIAI DOAN 0)
echo ========================================================

echo 1. Kiem tra Python va Git...
python scripts\check_env.py
if %ERRORLEVEL% neq 0 (
    echo [LOI] Kiem tra moi truong that bai! Vui long kiem tra lai thong bao tren.
    pause
    exit /b 1
)

echo 2. Tao moi truong ao .venv...
if not exist ".venv" (
    python -m venv .venv
    echo    Da tao xong .venv
) else (
    echo    .venv da ton tai, bo qua buoc tao.
)

echo 3. Cai dat / Cap nhat goi assistant va cac thu vien Giai doan 1...
call .venv\Scripts\activate.bat
pip install -e ".[dev]"
if %ERRORLEVEL% neq 0 (
    echo [LOI] Cai dat pip that bai!
    pause
    exit /b 1
)

echo 4. Chay kiem tra chan doan he thong (assistant doctor)...
assistant doctor

echo 5. Chay kiem thu tu dong toan bo cac module (pytest -v)...
pytest -v

echo 6. Kiem tra ma nguon bang ruff...
ruff check .

echo ========================================================
echo  HOAN TAT KIEM TRA GIAI DOAN 1 THANH CONG!
echo ========================================================
echo.
echo Ban co the chay thu cac lenh:
echo   - assistant set-key   (de luu Gemini API Key)
echo   - assistant models    (de xem danh sach cac model)
echo   - assistant chat      (de bat dau tro chuyen terminal)
echo ========================================================
pause

