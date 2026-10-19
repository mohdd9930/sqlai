@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=py -3"
        goto python_found
    )
)

where python >nul 2>&1
if errorlevel 1 (
    echo Python 3 was not found. Install Python 3 and try again.
    goto failed
)
set "PYTHON=python"

:python_found
if not exist ".venv\Scripts\python.exe" (
    echo Creating the project virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 goto failed
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto failed

echo Installing project dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto failed

if not exist ".env" (
    copy ".env.example" ".env" >nul
    if errorlevel 1 goto failed
    echo Created .env from .env.example.
    echo Add your Gemini key as GEMINI_API_KEY in .env to enable Gemini AI.
    echo The project will run in offline demo mode until a key is configured.
)

python -c "from pathlib import Path; from askdata.config import DB_PATH; raise SystemExit(0 if Path(DB_PATH).exists() else 1)"
if errorlevel 1 (
    echo Creating the sample database...
    python -m askdata.data.seed_db
    if errorlevel 1 goto failed
)

echo Starting AskData web UI at http://localhost:8000...
python -m askdata.web
echo AskData has exited.
pause
exit /b 0

:failed
echo.
echo AskData could not be started. Review the error above and try again.
pause
exit /b 1
