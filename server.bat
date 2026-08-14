@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PORT=8080

rem ============================================
rem  MM·H3 视频生成工作台 - 本地服务器启动脚本
rem  优先使用 Python，其次 Node，均无则提示
rem ============================================

where python >nul 2>nul
if %errorlevel%==0 goto :use_python

where node >nul 2>nul
if %errorlevel%==0 goto :use_node

echo 未检测到 Python 或 Node，无法启动本地服务器。
echo 请安装 Python（https://www.python.org）后重试，
echo 或直接双击 start.bat 在浏览器中打开页面。
pause
exit /b

:use_python
echo 使用 Python 启动: http://localhost:%PORT%
start "" "http://localhost:%PORT%"
python -m http.server %PORT%
exit /b

:use_node
echo 使用 Node 启动: http://localhost:%PORT%
start "" "http://localhost:%PORT%"
node server.js
exit /b
