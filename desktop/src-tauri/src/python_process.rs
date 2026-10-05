//! Python 后端子进程管理。
//!
//! 启动契约（与 scripts/desktop_launch.py 双向约定）：
//! - 壳以 `python.exe scripts/desktop_launch.py --port N --host 127.0.0.1` 拉起，
//!   端口由 [`crate::port_manager::find_free_port`] 预先抓取，脚本不再自行探测；
//! - stdout/stderr 重定向到 logs/desktop_python_*.log；
//! - 脚本不打开浏览器（WebView 即浏览器）、不 uvicorn reload。
//!
//! 解释器解析链移植自 scripts/clean_launch.py `find_winpython` + start.bat 探测链：
//! MMH3_DESKTOP_PYTHON 覆盖 → 打包 runtime → 仓 .venv → 仓内 WinPython →
//! 兄弟项目共享 WinPython → 系统 CUDA Python → MMH3_EXTRA_PYTHON → PATH 兜底。

use anyhow::{anyhow, Result};
use serde::Serialize;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter};

use crate::port_manager::find_free_port;

/// 壳拉起脚本相对 app_dir 的固定位置（亦是打包布局的判定标记）
pub const LAUNCH_SCRIPT: &str = "scripts/desktop_launch.py";
/// 打包布局下便携运行时的固定目录名
const RUNTIME_DIR_NAME: &str = "runtime";
/// 兄弟项目共享 WinPython 的版本目录（家族约定，对齐 clean_launch.py）
const SIBLING_WPY: [&str; 3] = ["Seedvr2", "TTS_MultiModel", "Image_MultiModel"];

/// 按优先级生成候选 python.exe 路径（不做存在性过滤，便于测试与日志诊断）。
/// 纯函数：环境变量取值由调用方注入。
pub fn python_candidates(
    app_dir: &Path,
    env_override: Option<&str>,
    extra_python: Option<&str>,
    sibling_root: &Path,
) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(p) = env_override {
        if !p.trim().is_empty() {
            out.push(PathBuf::from(p));
        }
    }
    // 打包布局（扁平）：app_dir（=staging 根）下的 runtime/
    out.push(app_dir.join(RUNTIME_DIR_NAME).join("python.exe"));
    // 开发布局：仓内隔离 venv（对齐 clean_launch 优先级 0）
    out.push(app_dir.join(".venv").join("Scripts").join("python.exe"));
    // 仓内 WinPython（对齐 clean_launch 优先级 1 的 WPy64-* glob）
    if let Ok(entries) = std::fs::read_dir(app_dir) {
        let mut dirs: Vec<PathBuf> = entries
            .flatten()
            .map(|e| e.path())
            .filter(|p| {
                p.is_dir()
                    && p.file_name()
                        .map(|n| n.to_string_lossy().starts_with("WPy64-"))
                        .unwrap_or(false)
            })
            .collect();
        dirs.sort();
        for d in dirs {
            out.push(d.join("python").join("python.exe"));
        }
    }
    // 兄弟项目共享 WinPython（对齐 clean_launch 优先级 2）
    for s in SIBLING_WPY {
        out.push(
            sibling_root
                .join(s)
                .join("WPy64-312101")
                .join("python")
                .join("python.exe"),
        );
    }
    // 系统级 CUDA Python（对齐 clean_launch 优先级 3 的家族约定安装位）
    out.push(PathBuf::from(r"C:\Python312\python.exe"));
    if let Some(p) = extra_python {
        if !p.trim().is_empty() {
            out.push(PathBuf::from(p));
        }
    }
    out
}

/// 从候选中取第一个真实存在的解释器；全部缺席时回退 PATH 上的 `python`。
pub fn resolve_python_exe(app_dir: &Path) -> PathBuf {
    let env = |k: &str| std::env::var(k).ok();
    let sibling_root = env("MMH3_SIBLING_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| app_dir.parent().unwrap_or(app_dir).to_path_buf());
    python_candidates(
        app_dir,
        env("MMH3_DESKTOP_PYTHON").as_deref(),
        env("MMH3_EXTRA_PYTHON").as_deref(),
        &sibling_root,
    )
    .into_iter()
    .find(|p| p.is_file())
    .unwrap_or_else(|| PathBuf::from("python"))
}

/// Python 进程状态
#[derive(Debug, Clone, Serialize)]
pub enum PythonStatus {
    Stopped,
    Starting,
    Running,
    Crashed,
}

/// Python 子进程管理器
pub struct PythonProcess {
    child: Option<Child>,
    port: u16,
    app_dir: PathBuf,
    log_dir: PathBuf,
    status: PythonStatus,
    restart_count: u32,
    max_restarts: u32,
}

impl PythonProcess {
    pub fn new(app_dir: PathBuf, log_dir: PathBuf) -> Self {
        Self {
            child: None,
            port: 0,
            app_dir,
            log_dir,
            status: PythonStatus::Stopped,
            restart_count: 0,
            max_restarts: 3,
        }
    }

    /// 启动 Python 子进程，返回分配的端口
    pub fn start(&mut self) -> Result<u16> {
        let port = find_free_port()?;
        self.port = port;

        let python_exe = resolve_python_exe(&self.app_dir);
        let start_script = self.app_dir.join(LAUNCH_SCRIPT);
        if !start_script.exists() {
            return Err(anyhow!(
                "启动脚本不存在: {}（请确认安装完整）",
                start_script.display()
            ));
        }

        std::fs::create_dir_all(&self.log_dir)?;
        let log_file = self.log_dir.join(format!(
            "desktop_python_{}.log",
            chrono::Local::now().format("%Y%m%d_%H%M%S")
        ));
        let log_writer = std::fs::File::create(&log_file)?;

        let child = Command::new(&python_exe)
            .arg(&start_script)
            .arg("--port")
            .arg(port.to_string())
            .arg("--host")
            .arg("127.0.0.1")
            .current_dir(&self.app_dir)
            .stdout(Stdio::from(log_writer.try_clone()?))
            .stderr(Stdio::from(log_writer))
            .env("PYTHONNOUSERSITE", "1")
            .env("PYTHONUNBUFFERED", "1")
            .creation_flags(0x08000000) // CREATE_NO_WINDOW
            .spawn()?;
        log::info!(
            "Python 进程已启动，PID={}，端口={}，解释器={}，日志={}",
            child.id(),
            port,
            python_exe.display(),
            log_file.display()
        );
        self.child = Some(child);
        self.status = PythonStatus::Starting;
        Ok(port)
    }

    /// 标记为运行中（并清零重启计数）
    pub fn mark_running(&mut self) {
        self.status = PythonStatus::Running;
        self.restart_count = 0;
    }

    /// 检查进程是否存活
    pub fn is_alive(&mut self) -> bool {
        if let Some(child) = &mut self.child {
            match child.try_wait() {
                Ok(None) => true,
                Ok(Some(status)) => {
                    log::warn!("Python 进程已退出，状态={status}");
                    false
                }
                Err(_) => false,
            }
        } else {
            false
        }
    }

    /// 尝试重启（受 max_restarts 限制）；耗尽后标记 Crashed 并返回 false
    pub fn try_restart(&mut self) -> Result<bool> {
        if self.restart_count >= self.max_restarts {
            self.status = PythonStatus::Crashed;
            return Ok(false);
        }
        self.restart_count += 1;
        log::info!(
            "正在重启 Python 进程（第 {}/{} 次）",
            self.restart_count,
            self.max_restarts
        );
        self.stop()?;
        self.start()?;
        Ok(true)
    }

    /// 停止 Python 进程（杀整棵进程树）。
    /// 本后端没有 /api/system/shutdown 端点，且依赖断点续跑（resume_unfinished_tasks）
    /// 兜底硬杀场景，因此直接 taskkill /T /F；孤儿扫描仅按本应用脚本路径过滤。
    pub fn stop(&mut self) -> Result<()> {
        if let Some(mut child) = self.child.take() {
            let pid = child.id();
            #[cfg(windows)]
            {
                let ok = Command::new("taskkill")
                    .args(["/PID", &pid.to_string(), "/T", "/F"])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .status()
                    .map(|s| s.success())
                    .unwrap_or(false);
                if !ok {
                    let _ = child.kill();
                }
            }
            #[cfg(not(windows))]
            {
                let _ = child.kill();
            }
            let _ = child.wait();
            log::info!("Python 进程树已停止（根 PID={pid}）");
        }
        // 兜底：清除持有本应用启动脚本的残留 python 进程（含父进程已退出的孤儿）
        #[cfg(windows)]
        {
            let marker = format!("{0}\\scripts\\desktop_launch.py", self.app_dir.display());
            let esc = marker.replace('\'', "''");
            let ps = format!(
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {{ $_.CommandLine -like '*{esc}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"
            );
            let _ = Command::new("powershell")
                .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", &ps])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
            log::info!("已扫描清除本应用残留 python 进程");
        }
        self.status = PythonStatus::Stopped;
        Ok(())
    }

    pub fn port(&self) -> u16 {
        self.port
    }

    pub fn status(&self) -> PythonStatus {
        self.status.clone()
    }
}

/// 全局共享的 Python 进程管理器
pub struct PythonState {
    pub process: Mutex<PythonProcess>,
}

/// 启动事件负载（加载页监听 `startup-status`）
#[derive(Serialize, Clone)]
struct StartupStatus {
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

/// 向主窗口发送启动状态
pub fn emit_startup_status(app: &AppHandle, message: &str, error: Option<String>) {
    let _ = app.emit(
        "startup-status",
        StartupStatus {
            message: message.to_string(),
            error,
        },
    );
}

/// 纯函数：按可执行文件路径解析应用目录（扁平打包布局）；
/// 无法判定（如开发态 target/release）返回 None，由调用方回退开发模式。
/// 布局契约：exe 与 scripts/desktop_launch.py 同根（staging 根即应用根，
/// backend 的 _BASE_DIR=backend 父目录=该根）。
pub fn resolve_app_dir_from_exe(exe: &Path) -> Option<PathBuf> {
    let exe_dir = exe.parent()?;
    if exe_dir.join(LAUNCH_SCRIPT).exists() {
        return Some(exe_dir.to_path_buf());
    }
    None
}

/// 解析应用代码目录
pub fn resolve_app_dir() -> PathBuf {
    // 1. 打包布局（扁平）——见 resolve_app_dir_from_exe。
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = resolve_app_dir_from_exe(&exe) {
            return dir;
        }
    }
    // 2. 开发模式：CARGO_MANIFEST_DIR 上溯到项目根（desktop/src-tauri → 项目根）
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn tmp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(name);
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn flat_layout_returns_exe_dir() {
        let d = tmp("mmh3_appdir_flat");
        fs::create_dir_all(d.join("scripts")).unwrap();
        fs::write(d.join("scripts").join("desktop_launch.py"), b"# stub").unwrap();
        let got = resolve_app_dir_from_exe(&d.join("MMH3Workbench.exe"));
        assert_eq!(got, Some(d.clone()));
        let _ = fs::remove_dir_all(&d);
    }

    #[test]
    fn bare_shell_dir_returns_none() {
        let d = tmp("mmh3_appdir_bare");
        assert!(resolve_app_dir_from_exe(&d.join("MMH3Workbench.exe")).is_none());
        let _ = fs::remove_dir_all(&d);
    }

    #[test]
    fn candidate_order_env_runtime_venv_wpy_sibling_system() {
        let d = tmp("mmh3_candidates");
        fs::create_dir_all(d.join("runtime")).unwrap();
        fs::write(d.join("runtime").join("python.exe"), b"").unwrap();
        fs::create_dir_all(d.join(".venv").join("Scripts")).unwrap();
        fs::write(d.join(".venv").join("Scripts").join("python.exe"), b"").unwrap();
        fs::create_dir_all(d.join("WPy64-312101").join("python")).unwrap();
        fs::write(
            d.join("WPy64-312101").join("python").join("python.exe"),
            b"",
        )
        .unwrap();
        let sibling_root = tmp("mmh3_candidates_sib");
        fs::create_dir_all(
            sibling_root
                .join("Seedvr2")
                .join("WPy64-312101")
                .join("python"),
        )
        .unwrap();
        fs::write(
            sibling_root
                .join("Seedvr2")
                .join("WPy64-312101")
                .join("python")
                .join("python.exe"),
            b"",
        )
        .unwrap();

        let cands = python_candidates(
            &d,
            Some(r"D:\explicit\python.exe"),
            Some(r"E:\extra\python.exe"),
            &sibling_root,
        );
        let names: Vec<String> = cands.iter().map(|p| p.display().to_string()).collect();
        // 顺序断言：显式覆盖 → runtime（嵌套→扁平）→ .venv → 仓内 WPy64 → 兄弟 → 系统 → extra
        let i = |s: &str| names.iter().position(|n| n.contains(s)).unwrap();
        assert!(i("explicit") < i("runtime"));
        assert!(i("runtime") < i(".venv"));
        assert!(i(".venv") < i("WPy64-312101"));
        assert!(names.iter().any(|n| n.contains("Seedvr2")));
        assert!(names.iter().any(|n| n.contains(r"C:\Python312")));
        assert!(i("C:\\Python312") < i("E:\\extra"));
        let _ = fs::remove_dir_all(&d);
        let _ = fs::remove_dir_all(&sibling_root);
    }

    #[test]
    fn resolve_prefers_first_existing() {
        let d = tmp("mmh3_resolve_first");
        fs::create_dir_all(d.join(".venv").join("Scripts")).unwrap();
        fs::write(d.join(".venv").join("Scripts").join("python.exe"), b"").unwrap();
        let got = resolve_python_exe(&d);
        assert!(got.ends_with("python.exe"));
        assert!(got.to_string_lossy().contains(".venv"));
        let _ = fs::remove_dir_all(&d);
    }
}
