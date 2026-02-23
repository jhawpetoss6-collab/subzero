@echo off
title Sub-Zero Flawless Victory - Setup
echo ============================================
echo    Sub-Zero  -  Flawless Victory
echo    One-Click Setup
echo ============================================
echo.

:: Find Python
set PYTHON=
where python.exe >nul 2>&1 && set PYTHON=python.exe
if "%PYTHON%"=="" (
    if exist "C:\Python314\python.exe" set PYTHON=C:\Python314\python.exe
)
if "%PYTHON%"=="" (
    if exist "C:\Python313\python.exe" set PYTHON=C:\Python313\python.exe
)
if "%PYTHON%"=="" (
    if exist "C:\Python312\python.exe" set PYTHON=C:\Python312\python.exe
)

if "%PYTHON%"=="" (
    echo [ERROR] Python not found!
    echo Download from: https://python.org/downloads
    pause
    exit /b 1
)

echo [OK] Found Python: %PYTHON%
echo.

:: Install dependencies
echo Installing dependencies...
%PYTHON% -m pip install --upgrade pip >nul 2>&1
%PYTHON% -m pip install -r "%~dp0requirements.txt"
echo.
echo [OK] Dependencies installed.
echo.

:: Pull Ollama model
where ollama >nul 2>&1
if %errorlevel%==0 (
    echo Pulling AI model (qwen2.5:3b)...
    ollama pull qwen2.5:3b
    echo [OK] Model ready.
) else (
    echo [SKIP] Ollama not found. Install from https://ollama.ai
    echo        Then run: ollama pull qwen2.5:3b
)
echo.

:: Create desktop shortcut
echo Creating desktop shortcut...
set DESKTOP=%USERPROFILE%\Desktop
set PYTHONW=%PYTHON:python.exe=pythonw.exe%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%DESKTOP%\Sub-Zero Flawless Victory.lnk'); ^
   $s.TargetPath = '%PYTHONW%'; ^
   $s.Arguments = '%~dp0subzero_app.pyw'; ^
   $s.WorkingDirectory = '%~dp0'; ^
   $s.IconLocation = '%~dp0subzero.ico,0'; ^
   $s.Description = 'Sub-Zero Flawless Victory'; ^
   $s.Save()"

echo [OK] Desktop shortcut created.
echo.

:: Build portable package
echo Building portable USB package...
if not exist "%~dp0SubZero_Portable" mkdir "%~dp0SubZero_Portable"
copy "%~dp0*.py" "%~dp0SubZero_Portable\" /Y >nul 2>&1
copy "%~dp0*.pyw" "%~dp0SubZero_Portable\" /Y >nul 2>&1
copy "%~dp0*.png" "%~dp0SubZero_Portable\" /Y >nul 2>&1
copy "%~dp0*.ico" "%~dp0SubZero_Portable\" /Y >nul 2>&1
copy "%~dp0*.json" "%~dp0SubZero_Portable\" /Y >nul 2>&1
copy "%~dp0*.txt" "%~dp0SubZero_Portable\" /Y >nul 2>&1
copy "%~dp0*.bat" "%~dp0SubZero_Portable\" /Y >nul 2>&1
echo [OK] Portable package ready in SubZero_Portable\
echo.

echo ============================================
echo    Setup complete! 
echo    Double-click "Sub-Zero Flawless Victory"
echo    on your desktop to launch.
echo ============================================
echo.
pause
