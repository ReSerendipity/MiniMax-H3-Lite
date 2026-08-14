# MM·H3 工作台 — 一键启动脚本（PowerShell）
# 用法: .\start.ps1
# 功能: 启动前端静态服务器(8080) + 后端 FastAPI(18080)
# 前提: 已安装 Python 3.10+ 和 pip

param(
    [int]$FrontendPort = 8080,
    [int]$BackendPort = 18080
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "=== MM·H3 工作台 启动中 ===" -ForegroundColor Cyan
Write-Host "前端: http://localhost:$FrontendPort"
Write-Host "后端: http://localhost:$BackendPort"
Write-Host ""

# ── 检查 Python ──────────────────────────────────
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "未检测到 Python，请安装 Python 3.10+ 后重试。" -ForegroundColor Red
    exit 1
}

# ── 安装后端依赖 ────────────────────────────────
$venvPath = Join-Path $Root ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "创建虚拟环境..." -ForegroundColor Yellow
    python -m venv .venv
}
& (Join-Path $venvPath "Scripts\Activate.ps1")
Write-Host "安装后端依赖..." -ForegroundColor Yellow
pip install -r requirements.txt -q

# ── 启动后端（后台） ────────────────────────────
$env:MMH3_PORT = $BackendPort
$env:MMH3_HOST = "127.0.0.1"
$backendProc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", $BackendPort `
    -WorkingDirectory $Root -PassThru -WindowStyle Minimized

# ── 启动前端（后台） ────────────────────────────
$frontendProc = Start-Process -FilePath "node" `
    -ArgumentList "server.js" `
    -WorkingDirectory $Root -PassThru -WindowStyle Minimized

# ── 打开浏览器 ──────────────────────────────────
Start-Process "http://localhost:$FrontendPort"

Write-Host ""
Write-Host "=== 启动完成 ===" -ForegroundColor Green
Write-Host "前端 PID: $($frontendProc.Id)  后端 PID: $($backendProc.Id)"
Write-Host "按 Ctrl+C 或关闭此窗口停止服务" -ForegroundColor DarkGray

# 等待子进程
try {
    Wait-Process -Id $backendProc.Id
} finally {
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
}
