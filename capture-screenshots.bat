@echo off
setlocal enableDelayedExpansion
title MiniMax H3 Screenshot Capture

set "ROOT=%~dp0"
set "TESTS_DIR=%ROOT%tests"
set "BASE_URL=http://127.0.0.1:18080"
set "HEALTH=%BASE_URL%/api/health"

echo ============================================
echo   MiniMax H3 - Auto Screenshot Capture
echo ============================================
echo.

REM ---- 1. Check Node.js ----
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js not found. Please install Node.js LTS first.
  pause
  exit /b 1
)
echo [OK] Node.js found.

REM ---- 2. Ensure Playwright dependencies ----
if not exist "%TESTS_DIR%\node_modules\@playwright\test\package.json" (
  echo [INFO] Installing test dependencies ^(npm install^) ...
  pushd "%TESTS_DIR%"
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    popd
    pause
    exit /b 1
  )
  echo [INFO] Installing chromium browser for Playwright ...
  call npx playwright install chromium
  if errorlevel 1 (
    echo [ERROR] playwright install chromium failed.
    echo        Hint: re-run manually:  cd tests ^& npx playwright install chromium
    popd
    pause
    exit /b 1
  )
  popd
) else (
  echo [OK] Playwright deps already installed.
)

REM ---- 3. Detect Python (system Python preferred, then WinPython, then siblings) ----
set "PYTHON_CMD="
if exist "C:\Python312\python.exe" set "PYTHON_CMD=C:\Python312\python.exe"
if not defined PYTHON_CMD if exist "C:\Python311\python.exe" set "PYTHON_CMD=C:\Python311\python.exe"
if not defined PYTHON_CMD (
  set "WP_DIR=%ROOT%WPy64-312101"
  if exist "%WP_DIR%\python\python.exe" set "PYTHON_CMD=%WP_DIR%\python\python.exe"
)
if not defined PYTHON_CMD (
  for /d %%i in ("%ROOT%WPy64-*") do (
    if exist "%%i\python\python.exe" set "PYTHON_CMD=%%i\python\python.exe"
  )
)
if not defined PYTHON_CMD (
  for %%i in ("C:\Users\Doro\Seedvr2\WPy64-312101\python\python.exe" "C:\Users\Doro\TTS_MultiModel\WPy64-312101\python\python.exe" "C:\Users\Doro\Image_MultiModel\WPy64-312101\python\python.exe") do (
    if exist "%%~i" set "PYTHON_CMD=%%~i"
  )
)

REM ---- 4. Check if server is already running ----
echo [INFO] Checking server at %BASE_URL% ...
call :check_health
if not errorlevel 1 (
  echo [OK] Server already running.
  goto :run_capture
)

REM ---- 5. Start server in a minimized window ----
if not defined PYTHON_CMD (
  echo [ERROR] Python not found. Either start the server manually with start.bat
  echo         first, then re-run this script, or install Python 3.10+.
  pause
  exit /b 1
)
echo [INFO] Starting MiniMax H3 server ^(UI screenshots do not need GPU^) ...
start "MiniMax H3 Server" /min "%PYTHON_CMD%" "%ROOT%bin\clean_launch.py"

REM ---- 6. Wait for server to be ready (max 180s) ----
echo [INFO] Waiting for server to be ready ^(max 180s^) ...
set /a waited=0
:waitloop
call :check_health
if not errorlevel 1 goto :ready
set /a waited+=3
if !waited! geq 180 goto :timeout
timeout /t 3 /nobreak >nul
goto :waitloop

:timeout
echo [ERROR] Server did not become ready within 180s.
echo         Check logs\app.log. If the port was auto-shifted (default 18080 is
echo         occupied), the server may run on a higher port; start it manually
echo         with start.bat and pass the matching MMH3_BASE_URL to this script.
pause
exit /b 1

:ready
echo [OK] Server is ready.

:run_capture
echo [INFO] Running screenshot capture ...
pushd "%TESTS_DIR%"
set "MMH3_BASE_URL=%BASE_URL%"
node capture-screenshots.js
set "RC=!errorlevel!"
popd

echo.
echo ============================================
if !RC!==0 (
  echo   Done. Screenshots saved under: %ROOT%screenshots
) else (
  echo   Capture finished with errors ^(exit code !RC!^).
)
echo ============================================
echo.
echo NOTE: The MiniMax H3 server window may still be open ^(minimized^).
echo       Close it manually if you no longer need it.
pause
exit /b !RC!

:check_health
REM Exit 0 = HTTP 200 (ready), non-zero = not ready.
curl.exe -s -m 3 -fsS "%HEALTH%" >nul 2>nul
exit /b !errorlevel!