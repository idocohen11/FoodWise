@echo off
setlocal
echo ==========================================
echo FoodWise Day 4 - Setup and Import
echo ==========================================

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher "py" was not found.
  echo Install Python 3 and try again.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creating virtual environment...
  py -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: dependency installation failed.
  pause
  exit /b 1
)

echo.
echo Starting FoodWise importer...
python import_data.py
set CODE=%ERRORLEVEL%

echo.
if "%CODE%"=="0" (
  echo Day 4 importer finished successfully.
) else (
  echo Importer ended with code %CODE%.
)
pause
exit /b %CODE%
