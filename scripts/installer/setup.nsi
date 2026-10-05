; setup.nsi — MM·H3 工作台 NSIS 安装器（发版周期阶段 2/3）
; ------------------------------------------------------------------
; 形态对齐家族 TTS-MultiModel：currentUser 免管安装 + 数据 7z 分卷安装期解压。
; 遵守 docs/CODING_STANDARDS.md：禁止写死本机工具/数据路径，
; 全部 SRC/OUT/7za/ICON 位置均可用 makensis -D 覆盖（见下方 !ifndef）。
;
; 典型调用（在 scripts\installer 下执行）：
;   makensis -DAPP_VERSION=2.5.1 setup.nsi
;
; 编译前置：staging（assemble_desktop_staging.ps1）与数据分卷
;（make_desktop_volumes.ps1）必须先就位——File 指令在编译期读分卷文件。

Unicode true
ManifestDPIAware true

!ifndef APP_VERSION
  !define APP_VERSION "2.5.1"
!endif
!define APP_NAME "MMH3Workbench"
!define APP_TITLE "MM·H3 工作台"
!define APP_PUBLISHER "MMH3 Workbench"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\MMH3Workbench"
!ifndef ESTIMATED_SIZE_KB
  !define ESTIMATED_SIZE_KB 350000   ; 不含 runtime/模型 的粗估安装体积（KB）
!endif

; ── 可覆盖路径（相对本脚本目录；-D 覆盖示例见文件头）────────────
!ifndef SRC_DIR
  !define SRC_DIR "..\..\dist\desktop\staging"
!endif
!ifndef OUT_DIR
  !define OUT_DIR "..\..\dist\desktop"
!endif
; 数据分卷所在目录（make_desktop_volumes.ps1 产出在 dist\desktop\，与 staging 同级）
!ifndef DATA_DIR
  !define DATA_DIR "${OUT_DIR}"
!endif
!ifndef SETUP_NAME
  !define SETUP_NAME "Setup-MMH3Workbench-${APP_VERSION}.exe"
!endif
!ifndef SRC_7ZA
  !define SRC_7ZA "7za.exe"
!endif
!ifndef SRC_ICON
  !define SRC_ICON "..\..\desktop\src-tauri\icons\icon.ico"
!endif

Name "${APP_TITLE} ${APP_VERSION}"
OutFile "${OUT_DIR}\${SETUP_NAME}"
InstallDir "$LOCALAPPDATA\Programs\MMH3Workbench"
InstallDirRegKey HKCU "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show

!include "MUI2.nsh"
!define MUI_ICON "${SRC_ICON}"
!define MUI_UNICON "${SRC_ICON}"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

; VI 元数据（右键属性/卸载列表展示）；VIProductVersion 要求四段
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "FileDescription" "${APP_TITLE} 安装程序"
VIAddVersionKey "FileVersion" "${APP_VERSION}.0"
VIAddVersionKey "LegalCopyright" "Apache-2.0（代码）；模型权重归 MiniMax H3 Community License 约束"

!macro KillRunning
  nsExec::Exec `taskkill /IM ${APP_NAME}.exe /F`
  ; 兜底清掉持有本应用启动脚本的残留 python 进程（升级/重装前）
  ; NSIS 字符串中 `$` 需写作 `$$`，否则 $_. 被当作脚本变量展开
  nsExec::Exec `powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $$_.CommandLine -like '*desktop_launch.py*' } | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }"`
  Sleep 800
!macroend

; ── 安装前告知（发版周期阶段 3 断言点：必须点确定才能继续）──────
Function .onInit
  MessageBox MB_OK|MB_ICONINFORMATION \
    "安装前请知悉：$\r$\n$\r$\n1. 本安装包不含模型权重（官方模型约 90.2GB）。安装完成后，请按安装目录下的《模型下载与放置指引》(MODEL_SETUP_GUIDE.md) 从魔搭社区下载并放入 model\ 对应子目录；$\r$\n$\r$\n2. 程序将安装到当前用户目录（无需管理员权限）；$\r$\n$\r$\n3. 视频生成需要 NVIDIA CUDA GPU 支持；$\r$\n$\r$\n4. 代码遵循 Apache-2.0；模型权重受 MiniMax H3 Community License 约束（详见 NOTICE）。"
  ReadRegStr $R0 HKCU "${UNINST_KEY}" ""
  StrCmp $R0 "" +2
  StrCpy $INSTDIR $R0
FunctionEnd

Section "Install"
  !insertmacro KillRunning
  SetOutPath "$INSTDIR"

  ; 壳与根级文件
  File "${SRC_DIR}\MMH3Workbench.exe"
  File "${SRC_DIR}\MODEL_SETUP_GUIDE.md"
  File "${SRC_DIR}\version.json"

  ; 安装期解压工具与数据分卷（分卷由 make_desktop_volumes.ps1 产出）
  File "${SRC_7ZA}"
  File "${DATA_DIR}\MMH3Workbench-Data.7z.*"

  DetailPrint "解压数据分卷（app/runtime/model 等，视体积需数分钟）..."
  nsExec::ExecToLog `"$INSTDIR\7za.exe" x -y -o"$INSTDIR" "$INSTDIR\MMH3Workbench-Data.7z.001"`
  Pop $0
  StrCmp $0 "error" extract_failed
  IntCmp $0 0 extract_ok extract_failed extract_failed
extract_failed:
  Abort "数据解压失败（exit=$0），安装已中止。请重试或检查数据分卷完整性（SHA256SUMS）。"
extract_ok:
  DetailPrint "数据解压完成"

  ; 清理安装期中间物
  Delete "$INSTDIR\7za.exe"
  Delete "$INSTDIR\MMH3Workbench-Data.7z.*"

  ; 7z 不保留空目录：补齐运行期占位
  CreateDirectory "$INSTDIR\model\diffusion_models"
  CreateDirectory "$INSTDIR\model\text_encoders"
  CreateDirectory "$INSTDIR\model\vae"
  CreateDirectory "$INSTDIR\model\loras"
  CreateDirectory "$INSTDIR\data"
  CreateDirectory "$INSTDIR\logs"
  CreateDirectory "$INSTDIR\uploads"

  ; 快捷方式
  CreateDirectory "$SMPROGRAMS\${APP_TITLE}"
  CreateShortcut "$SMPROGRAMS\${APP_TITLE}\${APP_TITLE}.lnk" "$INSTDIR\${APP_NAME}.exe"
  CreateShortcut "$DESKTOP\${APP_TITLE}.lnk" "$INSTDIR\${APP_NAME}.exe"

  ; HKCU 卸载键（阶段 3 断言：DisplayVersion）
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP_TITLE}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${APP_NAME}.exe"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINST_KEY}" "QuietUninstallString" "$INSTDIR\Uninstall.exe /S"
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
  WriteRegStr HKCU "${UNINST_KEY}" "EstimatedSize" "${ESTIMATED_SIZE_KB}"

  DetailPrint "安装完成。首次启动请按 MODEL_SETUP_GUIDE.md 就位模型权重。"
SectionEnd

Section "Uninstall"
  !insertmacro KillRunning
  MessageBox MB_YESNO|MB_ICONQUESTION \
    "是否同时删除模型权重与生成数据？$\r$\n$\r$\n【否】仅卸载程序，保留 model\（约 90GB 权重）、data\、uploads\、assets\ 中你的数据；$\r$\n【是】删除整个安装目录，全部数据不可恢复。" \
    IDYES uninst_all IDNO uninst_prog
uninst_all:
  RMDir /r "$INSTDIR"
  Goto uninst_keys
uninst_prog:
  ; 仅卸载程序本体（扁平布局下 code/data 同根，「保留」= 其余文件全部留在原地）
  Delete "$INSTDIR\${APP_NAME}.exe"
  Delete "$INSTDIR\MODEL_SETUP_GUIDE.md"
  Delete "$INSTDIR\version.json"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
uninst_keys:
  Delete "$SMPROGRAMS\${APP_TITLE}\${APP_TITLE}.lnk"
  RMDir "$SMPROGRAMS\${APP_TITLE}"
  Delete "$DESKTOP\${APP_TITLE}.lnk"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
