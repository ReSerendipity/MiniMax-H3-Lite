# make_desktop_volumes.ps1 — 桌面发版数据分卷（发版周期阶段 2 / GitHub 单资产 ≤2GiB 纪律）
#
# 产出（默认 dist\desktop\）：
#   MMH3Workbench-Data.7z.001..N   staging 全量（除壳 exe 外）7z 原生分卷，单卷 ≤1900MB
#   SHA256SUMS                     覆盖全部分卷（Setup exe 存在时一并覆盖）
#   upload-list.txt                逐文件上传清单（发版周期阶段 4 用，逐文件+重试循环）
#
# 7z 原生 -v 分卷（而非字节切片）：NSIS 安装期只需一行 `7za x ...001` 即可自动续卷。
#Requires -Version 5.1
param(
    [string]$StagingDir = "",
    [string]$OutputDir = "",
    [int]$VolumeMB = 1900,
    [switch]$RefreshChecksums   # 跳过打卷，仅按现有分卷+Setup 重算 SHA256SUMS/upload-list
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not $StagingDir) { $StagingDir = Join-Path $RepoRoot "dist\desktop\staging" }
if (-not $OutputDir) { $OutputDir = Split-Path -Parent $StagingDir }
if (-not (Test-Path (Join-Path $StagingDir "MMH3Workbench.exe"))) {
    throw "staging 无效（缺 MMH3Workbench.exe）：先跑 scripts\assemble_desktop_staging.ps1"
}

# ── 7z 探测（禁写死机器路径：先 PATH 再常见安装位）────────────
$SevenZip = $null
foreach ($c in @((Get-Command "7z" -ErrorAction SilentlyContinue).Source,
                 "C:\Program Files\7-Zip\7z.exe",
                 "C:\Program Files (x86)\7-Zip\7z.exe")) {
    if ($c -and (Test-Path $c)) { $SevenZip = $c; break }
}
if (-not $SevenZip) { throw "未找到 7z（PATH 或 Program Files 均无）" }
Write-Host "[INFO] 7z: $SevenZip"

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

if (-not $RefreshChecksums) {
    # ── 打卷（排除壳 exe：它由 Setup 安装器直接携带）────────────────
    $outBase = Join-Path $OutputDir "MMH3Workbench-Data.7z"
    Get-ChildItem $OutputDir -Filter "MMH3Workbench-Data.7z.*" -File |
        Remove-Item -Force
    & $SevenZip a -t7z "-v$($VolumeMB)M" -mx=4 -mmt=on $outBase (Join-Path $StagingDir "*") `
        "-x!MMH3Workbench.exe" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "7z 打卷失败（exit=$LASTEXITCODE）" }

    # ── 回读验证 ──────────────────────────────────────────────────
    & $SevenZip t (Join-Path $OutputDir "MMH3Workbench-Data.7z.001") | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "7z t 回读验证失败" }
}

$volumes = Get-ChildItem $OutputDir -Filter "MMH3Workbench-Data.7z.*" -File |
    Sort-Object Name
if (-not $volumes) { throw "未找到分卷文件（先跑一次不带 -RefreshChecksums 的打卷）" }
if (-not $RefreshChecksums) { Write-Host "[OK] 回读验证通过：$($volumes.Count) 卷" }

# ── SHA256SUMS.desktop（覆盖全部分卷；Setup exe 存在时一并纳入）──
# 命名避让：release.yml 已占用根级 SHA256SUMS（源码归档），桌面校验和用
# .desktop 后缀（对齐仓内 SHA256SUMS.scripts 惯例），上传不互相覆盖。
$hashTargets = @($volumes)
$setup = Get-ChildItem $OutputDir -Filter "Setup-MMH3Workbench-*.exe" -File |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($setup) { $hashTargets += $setup }

$sumsFile = Join-Path $OutputDir "SHA256SUMS.desktop"
$lines = foreach ($f in $hashTargets) {
    $h = (Get-FileHash $f.FullName -Algorithm SHA256).Hash.ToLower()
    "$h  $($f.Name)"
}
$lines | Set-Content $sumsFile -Encoding ASCII
Write-Host "[OK] SHA256SUMS.desktop（$($hashTargets.Count) 项）"

# ── upload-list（阶段 4 逐文件上传循环用）──────────────────────
$uploadNames = @($volumes.Name)
if ($setup) { $uploadNames += $setup.Name }
$uploadNames += "SHA256SUMS.desktop"
$uploadNames | Set-Content (Join-Path $OutputDir "upload-list.txt") -Encoding ASCII

$totalGB = [math]::Round((($hashTargets | Measure-Object Length -Sum).Sum) / 1GB, 2)
Write-Host ""
Write-Host "=== 分卷完成: $OutputDir（$($volumes.Count) 卷 + 校验和，共 $totalGB GB） ==="
Write-Host "上传纪律见 docs/agents/RELEASE_PROFILE.md 阶段4（gh release upload 必须带 -R；逐文件+重试）"
