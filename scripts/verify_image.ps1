<#
.SYNOPSIS
    端到端冒烟：docker compose up → 等 healthcheck → curl /api/health → docker compose down

.DESCRIPTION
    验证整条链路（build → 启动 → 模型加载 → API 响应）能跑通。
    用于：
      1. 改 Dockerfile / compose 后做回归
      2. 改 backend 代码后做容器内冒烟（无须本地 venv）
      3. 跑通了再进 commit / push

    失败会：
      - 打印 compose logs（最近 50 行）方便排错
      - 仍执行 docker compose down 清理（不残留容器）
      - exit 1

.PARAMETER UsePinned
    启用后用 `-f docker-compose.pinned.yml` 叠在 compose 上（与 build_and_pin.ps1 配对）

.PARAMETER Timeout
    健康检查最大等待秒数（默认 300 = 5 分钟；H3 模型首次加载实测需 2-4 分钟）

.EXAMPLE
    PS> pwsh scripts/verify_image.ps1
    # 默认：compose up → 等 health → curl → down

.EXAMPLE
    PS> pwsh scripts/verify_image.ps1 -UsePinned -Timeout 600
    # 用 digest-pinned compose + 10 分钟超时
#>

[CmdletBinding()]
param(
    [switch]$UsePinned,
    [int]$Timeout = 300
)

$ErrorActionPreference = 'Stop'
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
} catch { }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker 不在 PATH"
    exit 1
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

$composeArgs = @('-f', 'docker-compose.yml')
if ($UsePinned -and (Test-Path (Join-Path $repoRoot 'docker-compose.pinned.yml'))) {
    $composeArgs += @('-f', 'docker-compose.pinned.yml')
    Write-Host "使用 pinned override" -ForegroundColor Cyan
}

# 1. up
Write-Host "==> docker compose up -d ..." -ForegroundColor Cyan
& docker compose @composeArgs up -d
$upRc = $LASTEXITCODE
if ($upRc -ne 0) {
    Write-Error "docker compose up 失败 rc=$upRc"
    exit 1
}

# 始终 down（即使中途失败）
$tearDown = {
    Write-Host "==> docker compose down ..." -ForegroundColor Yellow
    & docker compose @composeArgs down 2>&1 | Out-Null
}

try {
    # 2. 等 healthcheck
    Write-Host "==> 等待 healthcheck healthy（超时 $Timeout 秒）..." -ForegroundColor Cyan
    $containerName = "mmh3-workbench"
    $start = Get-Date
    $healthy = $false
    $lastStatus = "(starting)"
    while (((Get-Date) - $start).TotalSeconds -lt $Timeout) {
        $status = (& docker inspect --format='{{.State.Health.Status}}' $containerName 2>$null).Trim()
        if ($status) { $lastStatus = $status }
        if ($status -eq "healthy") {
            $healthy = $true
            break
        }
        if ($status -eq "unhealthy") {
            Write-Warning "容器 health 报 unhealthy，提前结束等待"
            break
        }
        Write-Host "  [wait] status=$lastStatus, elapsed=$([math]::Round(((Get-Date) - $start).TotalSeconds))s"
        Start-Sleep -Seconds 5
    }

    if (-not $healthy) {
        Write-Warning "容器未在 $Timeout 秒内 healthy（last status: $lastStatus）"
        Write-Host "--- 最近 50 行 compose logs ---" -ForegroundColor Yellow
        & docker compose @composeArgs logs --tail=50
        exit 1
    }

    # 3. curl /api/health
    Write-Host "==> curl http://127.0.0.1:18080/api/health" -ForegroundColor Cyan
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:18080/api/health" -UseBasicParsing -TimeoutSec 10
        Write-Host "  HTTP $($resp.StatusCode)"
        Write-Host "  body: $($resp.Content)"
    } catch {
        Write-Warning "curl 失败: $_"
        Write-Host "--- 最近 30 行 compose logs ---" -ForegroundColor Yellow
        & docker compose @composeArgs logs --tail=30
        exit 1
    }

    Write-Host ""
    Write-Host "[PASS] 端到端冒烟通过" -ForegroundColor Green
    Write-Host "  - 容器 up: OK"
    Write-Host "  - healthcheck: healthy"
    Write-Host "  - /api/health: $((Invoke-WebRequest -Uri 'http://127.0.0.1:18080/api/health' -UseBasicParsing).StatusCode)"
    exit 0
}
finally {
    # 4. 总是 down
    & $tearDown
}
