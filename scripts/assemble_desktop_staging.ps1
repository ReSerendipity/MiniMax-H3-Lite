# assemble_desktop_staging.ps1 — 桌面发版 staging 组装（发版周期阶段 2）
#
# 布局契约（与 scripts/installer/setup.nsi、壳 resolve_app_dir 双向约定）：
#   staging\（扁平布局：staging 根即应用根，backend 的 _BASE_DIR 指向此处）
#   ├─ MMH3Workbench.exe        壳二进制（cargo build --release 产物改名）
#   ├─ MODEL_SETUP_GUIDE.md     模型下载指引（根级，壳 open_model_guide 打开它）
#   ├─ version.json             {version, built_at} 发版核验用
#   ├─ backend\ workflows\ assets\ scripts\   git archive HEAD 装跟踪路径
#   ├─ comfy_kernel\            属 .gitignore 的 vendored 目录，从磁盘 robocopy
#   ├─ requirements*.txt start.bat LICENSE NOTICE THIRD_PARTY_NOTICES.md README.md
#   ├─ runtime\                 便携 Python 运行时（-RuntimeDir 指定；无则必须 -SkipRuntime）
#   ├─ model\                   四类别的真实空目录（权重不打包，用户按指引自行下载）
#   └─ data\ logs\ uploads\     空占位目录（运行期生成物落这里）
#
# 用法示例：
#   powershell -File scripts\assemble_desktop_staging.ps1 -SkipRuntime
#   powershell -File scripts\assemble_desktop_staging.ps1 -RuntimeDir D:\runtime\python
#
# 滚动清理铁律：staging 位于 dist\（gitignored），发版归档后应整体删除。
#Requires -Version 5.1
param(
    [string]$Version = "",
    [string]$ShellExe = "",
    [string]$RuntimeDir = "",
    [switch]$SkipRuntime,
    [string]$OutputDir = "",
    [string]$ComfyKernelDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

# ── 默认值解析 ────────────────────────────────────────────────
if (-not $Version) {
    $pkg = Get-Content (Join-Path $RepoRoot "package.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $Version = $pkg.version
}
if (-not $ShellExe) {
    $ShellExe = Join-Path $RepoRoot "desktop\src-tauri\target\release\mmh3-desktop.exe"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $RepoRoot "dist\desktop\staging"
}
if (-not $ComfyKernelDir) {
    $ComfyKernelDir = Join-Path $RepoRoot "comfy_kernel"
}

# ── 前置校验 ──────────────────────────────────────────────────
if (-not (Test-Path $ShellExe)) {
    throw "壳二进制不存在: $ShellExe（先在 desktop\src-tauri 下 cargo build --release）"
}
$exeVersion = (Get-Item $ShellExe).VersionInfo.ProductVersion
Write-Host "[INFO] 壳 ProductVersion=$exeVersion，目标版本=$Version"
if ($exeVersion -ne $Version) {
    throw "壳 ProductVersion($exeVersion) 与目标版本($Version)不一致——请同步 tauri.conf.json / Cargo.toml / package.json 后重建"
}
if (-not $SkipRuntime -and -not $RuntimeDir) {
    throw "必须指定 -RuntimeDir（便携运行时目录）或 -SkipRuntime（开发冒烟变体）"
}
if ($RuntimeDir -and -not (Test-Path (Join-Path $RuntimeDir "python.exe"))) {
    throw "-RuntimeDir 下未找到 python.exe: $RuntimeDir"
}
if (-not (Test-Path $ComfyKernelDir)) {
    throw "comfy_kernel 不存在（vendored 目录仅本机在位）: $ComfyKernelDir"
}

# ── 清场重建 ──────────────────────────────────────────────────
if (Test-Path $OutputDir) {
    # 先改名再删：防手滑路径错删
    $graveyard = "$OutputDir.__deleting__"
    if (Test-Path $graveyard) { Remove-Item $graveyard -Recurse -Force }
    Rename-Item $OutputDir $graveyard
    Remove-Item $graveyard -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

# ── 1. 壳二进制改名入位 ───────────────────────────────────────
Copy-Item $ShellExe (Join-Path $OutputDir "MMH3Workbench.exe") -Force
Write-Host "[OK] MMH3Workbench.exe"

# ── 2. 应用代码：git archive（只含跟踪文件，天然避开权重/缓存） ──
# 扁平布局：staging 根即应用根（backend 的 _BASE_DIR=backend 父目录=staging 根，
# data/model/assets/comfy_kernel 全部在根下），与壳 resolve_app_dir 的 flat 分支一致。
$archivePaths = @(
    "backend", "workflows", "assets", "scripts",
    "requirements.txt", "requirements-lock.txt",
    "start.bat", "LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "README.md"
)
$tmpTar = Join-Path $env:TEMP "mmh3-app-$Version.tar"
git -C $RepoRoot archive --format=tar --output="$tmpTar" HEAD -- @archivePaths
if ($LASTEXITCODE -ne 0) { throw "git archive 失败" }
# 必须用系统自带 bsdtar：Git Bash 的 MSYS tar 会把 C:\ 目标路径当远程主机（Cannot connect to C:）
$Tar = Join-Path $env:SystemRoot "System32\tar.exe"
& $Tar -xf "$tmpTar" -C "$OutputDir"
if ($LASTEXITCODE -ne 0) { throw "tar 解包失败" }
Remove-Item $tmpTar -Force
Write-Host "[OK] 跟踪代码（git archive：backend/workflows/assets/scripts + 根文件）"

# ── 3. comfy_kernel：vendored 于 .gitignore，必须从磁盘复制 ────
robocopy $ComfyKernelDir (Join-Path $OutputDir "comfy_kernel") /E /NFL /NDL /NJH /NJS `
    /XD __pycache__ .pytest_cache .mypy_cache .ruff_cache .git /XF "*.pyc" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy comfy_kernel 失败（exit=$LASTEXITCODE）" }
$LASTEXITCODE = 0
Write-Host "[OK] comfy_kernel\（磁盘复制，排除缓存）"

# ── 4. runtime（可选）─────────────────────────────────────────
if ($RuntimeDir) {
    robocopy $RuntimeDir (Join-Path $OutputDir "runtime") /E /NFL /NDL /NJH /NJS `
        /XD __pycache__ .pytest_cache | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy runtime 失败（exit=$LASTEXITCODE）" }
    $LASTEXITCODE = 0
    Write-Host "[OK] runtime\（便携运行时）"
} else {
    Write-Host "[WARN] -SkipRuntime：staging 不含运行时，安装后需用户自备 Python 环境"
}

# ── 5. model 空目录 + 指引 + 占位目录 ─────────────────────────
foreach ($cat in @("diffusion_models", "text_encoders", "vae", "loras")) {
    New-Item -ItemType Directory -Path (Join-Path $OutputDir "model\$cat") -Force | Out-Null
}
Copy-Item (Join-Path $RepoRoot "scripts\desktop\MODEL_SETUP_GUIDE.md") `
    (Join-Path $OutputDir "MODEL_SETUP_GUIDE.md") -Force
foreach ($d in @("data", "logs", "uploads")) {
    New-Item -ItemType Directory -Path (Join-Path $OutputDir $d) -Force | Out-Null
}
Write-Host "[OK] model\ 四类别空目录 + MODEL_SETUP_GUIDE.md + data/logs/uploads 占位"

# ── 6. version.json ───────────────────────────────────────────
@{ version = $Version; built_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz") } |
    ConvertTo-Json | Set-Content (Join-Path $OutputDir "version.json") -Encoding UTF8
Write-Host "[OK] version.json"

# ── 汇总 ──────────────────────────────────────────────────────
$sizeGB = [math]::Round(((Get-ChildItem $OutputDir -Recurse -File | Measure-Object Length -Sum).Sum) / 1GB, 2)
Write-Host ""
Write-Host "=== staging 组装完成: $OutputDir（$sizeGB GB，版本 $Version） ==="
Write-Host "下一步: makensis 打 Setup → scripts\make_desktop_volumes.ps1 打数据分卷（详见 docs/agents/RELEASE_PROFILE.md 阶段2）"
