<#
.SYNOPSIS
    构建 H3 Workbench 镜像 + 给定版本 tag + 写 docker-compose.pinned.yml（含 digest 固化）

.DESCRIPTION
    流程：
      1. docker compose build（按 docker-compose.yml 完整构建）
      2. 从 compose 解析出 source image 名（image: 段或自动生成）
      3. docker tag 到用户指定 tag（默认 minimax-h3-lite:2.9.1-cu130）
      4. docker inspect --format='{{.Id}}' 拿 sha256 本地内容哈希
      5. 生成 docker-compose.pinned.yml（services.mmh3.image: 覆盖为 <tag>@<sha256>）

    之后用 `docker compose -f docker-compose.yml -f docker-compose.pinned.yml up -d`
    即可让 compose 引用 pinned digest，免疫 tag 被覆盖（即使有人 docker push 覆盖
    :2.9.1-cu130 这个 tag，本地 image ID 仍能命中已构建的层）。

    局限：本地 image ID 只能保护**本地**消费链；要做 CI/release 级别的不可变
    pin，请改用 `docker push` 到 registry（Docker Hub / GHCR）后用 RepoDigests。

.PARAMETER Tag
    版本 tag（默认 "2.9.1-cu130"，与 Dockerfile torch wheel 版本对齐）

.PARAMETER ComposeFile
    compose 文件（默认 "docker-compose.yml"）

.EXAMPLE
    PS> .\scripts\build_and_pin.ps1
    # 默认：build → tag minimax-h3-lite:2.9.1-cu130 → 生成 pinned override

.EXAMPLE
    PS> .\scripts\build_and_pin.ps1 -Tag "2.9.1-cu130-rc1"
    # 自定义 tag

.NOTES
    失败时 exit 1；所有错误信息打印到 stderr 并保留原 compose 不动。
#>

[CmdletBinding()]
param(
    [string]$Tag = "2.9.1-cu130",
    [string]$ComposeFile = "docker-compose.yml"
)

$ErrorActionPreference = 'Stop'

# 控制台 UTF-8
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
} catch { }

# === 1. docker 存在性检查 ===
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker 命令不在 PATH；请先安装 Docker Desktop 并启动 daemon"
    exit 1
}

# === 2. compose 文件存在性 ===
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composePath = Join-Path $repoRoot $ComposeFile
if (-not (Test-Path $composePath)) {
    Write-Error "compose 文件不存在: $composePath"
    exit 1
}
Set-Location $repoRoot

# === 3. docker compose build ===
Write-Host "==> docker compose build（首次约 10-20 分钟；含 torch cu130 wheel 下载）" -ForegroundColor Cyan
& docker compose -f $ComposeFile build
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose build 失败，rc=$LASTEXITCODE"
    exit 1
}

# === 4. 解析 source image 名 ===
Write-Host "==> 解析 compose image 名称..." -ForegroundColor Cyan
$sourceImage = (& docker compose -f $ComposeFile config --images | Select-Object -First 1).Trim()
if ([string]::IsNullOrWhiteSpace($sourceImage)) {
    Write-Error "docker compose config --images 未返回任何 image"
    exit 1
}
Write-Host "  source image: $sourceImage"

# === 5. tag ===
$targetImage = "minimax-h3-lite:$Tag"
Write-Host "==> docker tag $sourceImage $targetImage" -ForegroundColor Cyan
& docker tag $sourceImage $targetImage
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker tag 失败"
    exit 1
}

# === 6. 拿 image ID（sha256 本地内容哈希）===
Write-Host "==> docker inspect 拿本地 image ID" -ForegroundColor Cyan
$imageId = (& docker inspect --format='{{.Id}}' $targetImage).Trim()
if ($imageId -notmatch '^sha256:[a-f0-9]{64}$') {
    Write-Error "拿到的 image ID 格式异常: '$imageId'"
    exit 1
}
Write-Host "  image ID: $imageId"

# === 7. 生成 docker-compose.pinned.yml ===
$pinnedPath = Join-Path $repoRoot "docker-compose.pinned.yml"
$content = @"
# docker-compose.pinned.yml — digest 固化覆盖层
#
# 自动生成自 scripts/build_and_pin.ps1 于 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# source : $sourceImage
# target : $targetImage
# digest : $imageId
#
# 用法（与原 compose 合并使用）：
#   docker compose -f docker-compose.yml -f docker-compose.pinned.yml up -d
#
# 效果：services.mmh3.image 被覆盖为 <tag>@<sha256>，免疫 tag 漂移；
# 唯一能破坏这条 pinned 链的是本地 image 被 docker rmi 或重新 pull 覆盖。

services:
  mmh3:
    image: ${targetImage}@${imageId}
"@
$content | Out-File -FilePath $pinnedPath -Encoding utf8 -NoNewline
Write-Host "==> 写入 $pinnedPath" -ForegroundColor Green

# === 8. 总结 ===
Write-Host ""
Write-Host "[DONE] 构建 + digest 固化完成" -ForegroundColor Green
Write-Host "  原 compose   : $ComposeFile"
Write-Host "  pinned 覆盖  : docker-compose.pinned.yml"
Write-Host "  启动命令     :"
Write-Host "    docker compose -f $ComposeFile -f docker-compose.pinned.yml up -d" -ForegroundColor Yellow
Write-Host "  验证         :"
Write-Host "    curl http://127.0.0.1:18080/api/health"
Write-Host "  端到端冒烟   :"
Write-Host "    pwsh scripts/verify_image.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ⚠ 升级镜像时只需重跑本脚本（生成新 digest）；不要手动编辑 pinned.yml"
Write-Host "  ⚠ 共享给团队时记得 git add docker-compose.pinned.yml"

exit 0
