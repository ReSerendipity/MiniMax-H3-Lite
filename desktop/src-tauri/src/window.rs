//! 主窗口构建：加载页起步 → 后端就绪后由 main.rs 导航到 http://127.0.0.1:{port}/。
//! 外部链接一律转交系统默认浏览器；桥接脚本经 initialization_script 注入
//! （对壳页与后端页统一生效）。

use tauri::{AppHandle, Manager, WebviewWindow, WebviewWindowBuilder};

/// 主窗口标签
pub const MAIN_LABEL: &str = "main";
/// 空闲标题
pub const APP_TITLE: &str = "MM·H3 工作台";
/// 前端桥接脚本（编译期内嵌，运行时以 initialization_script 注入）
pub const BRIDGE_JS: &str = include_str!("../../src/desktop-bridge.js");

/// 判断 URL 是否属于应用自身（允许在 WebView 内导航）。
/// 放行：`tauri:`/`about:`/`ipc:`/`data:` 内部协议、`127.0.0.1`/`localhost`（本机后端）。
pub fn is_internal_url(url: &tauri::Url) -> bool {
    match url.scheme() {
        "tauri" | "about" | "ipc" | "data" => true,
        "http" | "https" => matches!(
            url.host_str(),
            Some("127.0.0.1") | Some("localhost") | Some("tauri.localhost") | None
        ),
        _ => false,
    }
}

/// 用系统默认浏览器打开外部链接
pub fn open_external(url: &str) {
    if let Err(e) = open::that(url) {
        log::warn!("打开外部链接失败 {url}: {e}");
    }
}

/// 显示并聚焦主窗口（单实例二次启动兜底）
pub fn show_and_focus(app: &AppHandle) {
    if let Some(win) = app.get_webview_window(MAIN_LABEL) {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
    }
}

/// 构建主窗口：默认尺寸 1280x800 居中，系统边框（v1 不做自绘标题栏）。
pub fn build_main_window(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    let win =
        WebviewWindowBuilder::new(app, MAIN_LABEL, tauri::WebviewUrl::App("index.html".into()))
            .title(APP_TITLE)
            .inner_size(1280.0, 800.0)
            .min_inner_size(1024.0, 640.0)
            .center()
            .resizable(true)
            .initialization_script(BRIDGE_JS)
            .on_navigation(|url| {
                if is_internal_url(url) {
                    true
                } else {
                    open_external(url.as_str());
                    false
                }
            })
            .on_new_window(|url, _features| {
                // target=_blank / window.open 一律系统浏览器
                open_external(url.as_str());
                tauri::webview::NewWindowResponse::Deny
            })
            .build()?;
    Ok(win)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn internal_urls_allowed() {
        assert!(is_internal_url(
            &tauri::Url::parse("tauri://localhost/index.html").unwrap()
        ));
        assert!(is_internal_url(
            &tauri::Url::parse("http://127.0.0.1:18080/").unwrap()
        ));
        assert!(is_internal_url(
            &tauri::Url::parse("http://localhost:18080/i2v").unwrap()
        ));
        assert!(is_internal_url(&tauri::Url::parse("about:blank").unwrap()));
        assert!(is_internal_url(
            &tauri::Url::parse("http://tauri.localhost/index.html").unwrap()
        ));
    }

    #[test]
    fn external_urls_blocked() {
        assert!(!is_internal_url(
            &tauri::Url::parse("https://modelscope.cn/").unwrap()
        ));
        assert!(!is_internal_url(
            &tauri::Url::parse("https://github.com/x").unwrap()
        ));
        assert!(!is_internal_url(
            &tauri::Url::parse("http://192.168.1.5:18080/").unwrap()
        ));
    }

    #[test]
    fn title_constant() {
        assert_eq!(APP_TITLE, "MM·H3 工作台");
    }
}
