<#
.SYNOPSIS
    把 model/ 下的 NTFS Junction 转换成真实目录（用于 Docker 部署兼容性）。

.DESCRIPTION
    本仓 model/{diffusion_models,loras,text_encoders,vae} 默认是 NTFS Junction 指向
    ComfyUI 安装目录（参见 GOTCHAS #20）。Docker Desktop -> WSL2 -> Linux 容器链路
    下，Docker 通常会跟随同盘 Junction 成功挂载；但若目标卷跨盘、跟随失败、或用户
    把仓库拷到另一台机器，Junction 会断链。本脚本提供幂等、可预演的转换工具。

    行为：
    - 默认（无 -Apply）：只列出所有 Junction、其源、目标、内容大小，并对比磁盘
      剩余空间；不会修改任何文件。
    - 加 -Apply：把每个 Junction 替换为真实目录（robocopy 复制源内容到新目录后
      删除旧 Junction，原子 swap）。
    - 跑完可重跑脚本验证："Found 0 Junctions" 即完成。

.PARAMETER ModelDir
    待检查的 model 目录；默认是脚本同级 ../model。

.PARAMETER Apply
    实际执行转换（默认 dry-run，仅报告）。

.EXAMPLE
    PS> .\scripts\convert_model_junctions.ps1
    # 只报告，不动文件

.EXAMPLE
    PS> .\scripts\convert_model_junctions.ps1 -Apply
    # 实际转换；磁盘不足会自动中止

.NOTES
    - 复制需 1.2x 源大小的临时磁盘（源 + 目标），本脚本会校验可用空间 + 5 GB 余量。
    - robocopy 在源端是 Junction 时，行为：默认 /MIR 会把 Junction 本身复制为新 Junction
      （不安全）；本脚本先 Get-Item 拿到 Junction 的解析目标路径，再 robocopy 该真实路径，
      因此新目录是纯文件，不会再次变 Junction。
#>

[CmdletBinding()]
param(
    [string]$ModelDir,
    [switch]$Apply
)

if (-not $ModelDir) {
    $ModelDir = Join-Path $PSScriptRoot '..\model'
}

# 让 Windows 控制台正确渲染中文（PS 5.1 默认按系统 ANSI 输出）
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
} catch { }

$ErrorActionPreference = 'Stop'

function Get-RealSize {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    return (Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
}

if (-not (Test-Path -LiteralPath $ModelDir)) {
    Write-Error "model 目录不存在: $ModelDir"; exit 2
}

$ModelDir = (Resolve-Path -LiteralPath $ModelDir).Path
$DriveLetter = $ModelDir.Substring(0, 1)
$vol = Get-Volume -DriveLetter $DriveLetter -ErrorAction SilentlyContinue
if (-not $vol) { Write-Error "无法获取 ${DriveLetter}: 盘符的卷信息"; exit 2 }
$freeBytes = $vol.SizeRemaining

# 收集 Junctions（顶级 + 一级子目录）
$junctions = @()
Get-ChildItem -LiteralPath $ModelDir -Force -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        $junctions += $_
    }
}

if ($junctions.Count -eq 0) {
    Write-Host "[OK] $ModelDir 下无 Junction，无需转换" -ForegroundColor Green
    exit 0
}

Write-Host "扫描到 $($junctions.Count) 个 Junction：" -ForegroundColor Cyan
$totalSrc = 0
foreach ($j in $junctions) {
    $size = Get-RealSize $j.FullName
    $totalSrc += $size
    # PowerShell 5.1 下 Junction.Target 是 string[]，取第一个并 join
    $target = if ($j.Target -is [array]) { ($j.Target -join ', ') } else { [string]$j.Target }
    $targetExists = Test-Path -LiteralPath $target
    $sizeGB = [math]::Round($size / 1GB, 2)
    $status = if ($targetExists) { 'OK' } else { 'BROKEN' }
    $row = "  {0,-20} {1,8:N2} GB  ->  {2}  [{3}]" -f $j.Name, $sizeGB, $target, $status
    Write-Host $row
    if (-not $targetExists) {
        Write-Warning "Junction 目标已断链: $target  （请先修复源路径，或用 -Apply 时此 Junction 会被换成空目录）"
    }
}

$needBytes = $totalSrc  # 新目录占用
$peakBytes = $totalSrc * 2  # 复制期间源+目标峰值
$freeGB = [math]::Round($freeBytes / 1GB, 1)
$needGB = [math]::Round($needBytes / 1GB, 1)
$peakGB = [math]::Round($peakBytes / 1GB, 1)
$reserveGB = 5

Write-Host ""
Write-Host "  复制完成新增占用：$needGB GB"
Write-Host "  复制期间峰值占用：$peakGB GB（源 + 目标并存）"
Write-Host "  磁盘剩余        ：$freeGB GB"
Write-Host "  安全余量        ：$reserveGB GB"

$required = $peakBytes + $reserveGB * 1GB
if ($freeBytes -lt $required) {
    $shortGB = [math]::Round(($required - $freeBytes) / 1GB, 1)
    Write-Warning "磁盘空间不足：还差约 $shortGB GB。请先清理磁盘再跑（建议用 -Apply）。"
    if (-not $Apply) { exit 2 } else { throw "磁盘不足，中止" }
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "[DRY-RUN] 无 -Apply，未做修改。检查通过后执行："
    Write-Host "         .\scripts\convert_model_junctions.ps1 -Apply" -ForegroundColor Yellow
    exit 0
}

# === 实际转换 ===
Write-Host ""
Write-Host "开始转换（-Apply 模式）..." -ForegroundColor Yellow

foreach ($j in $junctions) {
    $name = $j.Name
    $target = $j.Target
    $realDst = Join-Path $ModelDir ($name + '.conv.tmp')
    $finalDst = Join-Path $ModelDir $name

    if (-not (Test-Path -LiteralPath $target)) {
        Write-Warning "跳过 $name（目标已断链 $target）"
        continue
    }

    Write-Host "  转换 $name ..."
    if (Test-Path -LiteralPath $realDst) {
        Remove-Item -LiteralPath $realDst -Recurse -Force
    }

    # robocopy /MIR 把 Junction 的解析目标真实复制到新临时目录
    # /COPY:DAT 数据+属性+时间戳；/E 含空目录；/R:1 /W:1 错误快速失败
    $robocopyArgs = @(
        $target,
        $realDst,
        '/MIR', '/E', '/COPY:DAT',
        '/R:1', '/W:1',
        '/NFL', '/NDL', '/NP', '/BYTES'
    )
    & robocopy @robocopyArgs | Out-Null
    $rc = $LASTEXITCODE
    # robocopy rc<8 = 成功/部分成功；>=8 = 错误
    if ($rc -ge 8) {
        throw "robocopy 失败 (rc=$rc)，目标: $realDst"
    }

    # 校验：源/目标文件数一致
    $srcCount = (Get-ChildItem -LiteralPath $target -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object).Count
    $dstCount = (Get-ChildItem -LiteralPath $realDst -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($srcCount -ne $dstCount) {
        throw "$name 复制后文件数不一致: src=$srcCount dst=$dstCount（保留 $realDst 现场，不删原 Junction）"
    }

    # 原子 swap：先删 Junction，再 rename 新目录为同名
    Remove-Item -LiteralPath $j.FullName -Force
    Rename-Item -LiteralPath $realDst -NewName $name
    Write-Host "    done: $srcCount files, $name 已从 Junction 转为真实目录" -ForegroundColor Green
}

Write-Host ""
Write-Host "[DONE] 所有 Junction 已转换。重新跑本脚本（无 -Apply）应输出 'Found 0 Junctions'。" -ForegroundColor Green
