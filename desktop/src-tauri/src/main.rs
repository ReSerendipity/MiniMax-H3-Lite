// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! MM·H3 工作台桌面壳（Tauri v2）。
//! 职责：拉起 Python 后端（scripts/desktop_launch.py）→ 轮询 /api/health →
//! 就绪后把主窗口导航到工作台；退出时回收进程树；模型缺失时非阻断引导。

mod health_check;
mod models;
mod port_manager;
mod python_process;
mod window;

use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{AppHandle, Emitter, Manager, RunEvent};

use python_process::{emit_startup_status, resolve_app_dir, PythonProcess, PythonState};

/// 主窗口导航到后端应用地址
fn navigate_to_app(app: &AppHandle, port: u16) {
    if let Some(win) = app.get_webview_window(window::MAIN_LABEL) {
        let url = format!("http://127.0.0.1:{port}/");
        match url.parse() {
            Ok(url) => {
                let _ = win.navigate(url);
            }
            Err(e) => log::error!("解析导航地址失败 {url}: {e}"),
        }
    }
}

/// 启动 Python 并等待就绪（成功时导航主窗口到后端地址）
async fn start_python_and_load(app: &AppHandle, state: &Arc<PythonState>) {
    emit_startup_status(app, "正在启动 Python 运行时...", None);

    let port = {
        let mut proc = state.process.lock().unwrap();
        match proc.start() {
            Ok(port) => port,
            Err(e) => {
                log::error!("启动 Python 失败: {e}");
                emit_startup_status(
                    app,
                    "启动失败",
                    Some(format!(
                        "Python 启动失败: {e}\n请查看 logs/ 下壳日志与 desktop_python_*.log"
                    )),
                );
                return;
            }
        }
    };

    emit_startup_status(
        app,
        "正在等待服务就绪（首次启动可能需要安装依赖，请耐心等待）...",
        None,
    );

    // 300s：健康端点在依赖齐全时数秒内就绪；裸解释器首启需 pip 安装 requirements
    match health_check::wait_for_ready(port, Duration::from_secs(300)).await {
        Ok(()) => {
            let mut proc = state.process.lock().unwrap();
            proc.mark_running();
            log::info!("Python 服务就绪，端口={port}");
            navigate_to_app(app, port);
        }
        Err(e) => {
            log::error!("Python 启动超时: {e}");
            emit_startup_status(
                app,
                "启动超时",
                Some(format!(
                    "服务启动超时: {e}\n请查看 logs/desktop_python_*.log 了解详情"
                )),
            );
        }
    }
}

/// 后台监控线程：检测 Python 崩溃并自动重启（最多 max_restarts 次）
fn start_watchdog(app: AppHandle, state: Arc<PythonState>) {
    tauri::async_runtime::spawn(async move {
        loop {
            tokio::time::sleep(Duration::from_secs(2)).await;

            let needs_restart = {
                let mut proc = state.process.lock().unwrap();
                matches!(proc.status(), python_process::PythonStatus::Running) && !proc.is_alive()
            };

            if needs_restart {
                log::warn!("检测到 Python 进程崩溃，尝试重启");
                emit_startup_status(&app, "检测到进程崩溃，正在重启...", None);

                let restarted = {
                    let mut proc = state.process.lock().unwrap();
                    proc.try_restart().unwrap_or(false)
                };

                if restarted {
                    let new_port = {
                        let proc = state.process.lock().unwrap();
                        proc.port()
                    };
                    let ready = health_check::wait_for_ready(new_port, Duration::from_secs(60))
                        .await
                        .is_ok();
                    if ready {
                        let mut proc = state.process.lock().unwrap();
                        proc.mark_running();
                        navigate_to_app(&app, new_port);
                        emit_startup_status(&app, "已恢复", None);
                    }
                } else {
                    emit_startup_status(
                        &app,
                        "重启失败",
                        Some("Python 进程多次崩溃，已停止自动重启。请查看 logs/ 下日志后点「重试」。".to_string()),
                    );
                }
            }
        }
    });
}

// ===== Tauri 命令 =====

/// 重试启动命令（加载页错误态按钮调用）
#[tauri::command]
async fn retry_start(
    app: AppHandle,
    state: tauri::State<'_, Arc<PythonState>>,
) -> Result<(), String> {
    {
        let mut proc = state.process.lock().unwrap();
        proc.stop().map_err(|e| e.to_string())?;
    }
    let app_clone = app.clone();
    let state_clone = state.inner().clone();
    tauri::async_runtime::spawn(async move {
        start_python_and_load(&app_clone, &state_clone).await;
    });
    Ok(())
}

/// 打开模型下载指引（模型缺失引导；加载页与主界面均可调用）
#[tauri::command]
fn open_model_guide() -> Result<(), String> {
    let app_dir = resolve_app_dir();
    let candidates = [
        app_dir.join("MODEL_SETUP_GUIDE.md"),
        app_dir
            .join("scripts")
            .join("desktop")
            .join("MODEL_SETUP_GUIDE.md"),
    ];
    let guide = candidates.iter().find(|p| p.is_file()).ok_or_else(|| {
        format!(
            "未找到 MODEL_SETUP_GUIDE.md（查找于 {}）",
            app_dir.display()
        )
    })?;
    open::that(guide).map_err(|e| format!("打开指引失败: {e}"))
}

/// 查询当前缺失的模型类别（加载页加载时主动拉取，避免与事件竞态）
#[tauri::command]
fn get_model_status() -> Vec<String> {
    models::check_model_dirs(&resolve_app_dir())
}

/// 壳日志大小上限与备份份数（防止无限增长）
const SHELL_LOG_MAX_BYTES: u64 = 5 * 1024 * 1024;
const SHELL_LOG_BACKUPS: u32 = 3;

/// 滚动壳日志：mmh3-desktop-shell.log -> .log.1 -> .log.2 -> .log.3，删除最旧
fn rotate_shell_log(path: &std::path::Path) {
    let oldest = path.with_extension(format!("log.{}", SHELL_LOG_BACKUPS));
    let _ = std::fs::remove_file(&oldest);
    for i in (1..SHELL_LOG_BACKUPS).rev() {
        let from = path.with_extension(format!("log.{i}"));
        let to = path.with_extension(format!("log.{}", i + 1));
        if from.exists() {
            let _ = std::fs::rename(&from, &to);
        }
    }
    let _ = std::fs::rename(path, path.with_extension("log.1"));
}

/// 简易双写日志：stdout + logs\mmh3-desktop-shell.log（release 模式下 stdout 不可见，
/// 文件侧是壳排障的唯一入口）
struct DualLogger {
    file: Mutex<Option<std::fs::File>>,
    path: Mutex<Option<std::path::PathBuf>>,
}

impl log::Log for DualLogger {
    fn enabled(&self, _metadata: &log::Metadata) -> bool {
        true
    }
    fn log(&self, record: &log::Record) {
        use std::io::Write;
        let line = format!(
            "[{}] [{}] {}",
            chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
            record.level(),
            record.args()
        );
        let mut out = std::io::stdout();
        let _ = writeln!(out, "{line}");
        if let Ok(mut guard) = self.file.lock() {
            if let Some(f) = guard.as_mut() {
                if let Ok(meta) = f.metadata() {
                    if meta.len() > SHELL_LOG_MAX_BYTES {
                        let rotate_path = self.path.lock().ok().and_then(|p| p.clone());
                        if let Some(p) = rotate_path {
                            let _ = f.flush();
                            *guard = None;
                            rotate_shell_log(&p);
                            if let Ok(nf) = std::fs::OpenOptions::new()
                                .create(true)
                                .append(true)
                                .open(&p)
                            {
                                *guard = Some(nf);
                            }
                        }
                    }
                }
                if let Some(f) = guard.as_mut() {
                    let _ = writeln!(f, "{line}");
                }
            }
        }
    }
    fn flush(&self) {
        use std::io::Write;
        if let Ok(mut guard) = self.file.lock() {
            if let Some(f) = guard.as_mut() {
                let _ = f.flush();
            }
        }
    }
}

/// 初始化日志：RUST_LOG 可覆盖级别（debug/trace/warn/error）
fn init_logging() {
    let file = resolve_app_dir()
        .join("logs")
        .join("mmh3-desktop-shell.log");
    if let Some(parent) = file.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let f = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&file)
        .ok();
    let logger = DualLogger {
        file: Mutex::new(f),
        path: Mutex::new(Some(file)),
    };
    if let Err(e) = log::set_boxed_logger(Box::new(logger)) {
        eprintln!("日志初始化失败: {e}");
    }
    let level = std::env::var("RUST_LOG")
        .unwrap_or_else(|_| "info".to_string())
        .to_lowercase();
    log::set_max_level(match level.as_str() {
        "debug" => log::LevelFilter::Debug,
        "trace" => log::LevelFilter::Trace,
        "warn" => log::LevelFilter::Warn,
        "error" => log::LevelFilter::Error,
        _ => log::LevelFilter::Info,
    });
}

fn setup(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let app_handle = app.handle().clone();

    let app_dir = resolve_app_dir();
    let log_dir = app_dir.join("logs");
    log::info!("应用目录: {}", app_dir.display());
    log::info!("日志目录: {}", log_dir.display());

    let python_state = Arc::new(PythonState {
        process: Mutex::new(PythonProcess::new(app_dir.clone(), log_dir)),
    });
    app.manage(python_state.clone());

    // 模型就绪检查（非阻断）：缺失时通知加载页展示下载指引
    let missing_models = models::check_model_dirs(&app_dir);
    if !missing_models.is_empty() {
        log::warn!("模型类别未就绪: {}", missing_models.join(", "));
        let _ = app_handle.emit("model-guide", &missing_models);
    }

    window::build_main_window(&app_handle)?;

    // 启动 Python
    {
        let app_clone = app_handle.clone();
        let state_clone = python_state.clone();
        tauri::async_runtime::spawn(async move {
            start_python_and_load(&app_clone, &state_clone).await;
        });
    }
    // 崩溃监控
    start_watchdog(app_handle.clone(), python_state);

    Ok(())
}

fn main() {
    init_logging();

    tauri::Builder::default()
        // 单实例：二次启动聚焦现有窗口而不是开新实例
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            window::show_and_focus(app);
        }))
        .invoke_handler(tauri::generate_handler![
            retry_start,
            open_model_guide,
            get_model_status,
        ])
        .setup(setup)
        .build(tauri::generate_context!())
        .expect("启动 Tauri 应用失败")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                // 退出兜底：停止 Python 子进程树，避免孤儿进程
                let state = app.state::<Arc<PythonState>>();
                let mut proc = state.process.lock().unwrap();
                let _ = proc.stop();
            }
        });
}
