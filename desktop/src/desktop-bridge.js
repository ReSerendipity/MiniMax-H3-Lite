/*
 * MM·H3 桌面壳前端桥接（desktop-bridge.js）
 * ------------------------------------------------------------------
 * 由 Tauri 侧通过 `initialization_script` 注入主窗口（见
 * src-tauri/src/window.rs），因此不依赖 CDN 或 withGlobalTauri 的
 * window.__TAURI__：直接走内核注入的 `window.__TAURI_INTERNALS__` IPC 通道。
 *
 * 设计约束：
 * 1. 浏览器模式降级：纯浏览器（start.bat + Chrome）打开时
 *    `window.__TAURI_INTERNALS__` 不存在，本脚本整体 no-op，绝不报错。
 * 2. 主应用运行在后端源 http://127.0.0.1:PORT，其页面没有 window.__TAURI__，
 *    但初始化脚本已注入 __TAURI_INTERNALS__，故 IPC 可用
 *    （capabilities/main.json 已放行本机源）。
 * 3. v1 契约：命令 retry_start / open_model_guide / get_model_status；
 *    事件 startup-status / model-guide（消费方为壳自带加载页 index.html）。
 *    后端页面的深度集成（标题忙闲/任务通知等，对齐 TTS 桥接）留待后续版本。
 */
(function () {
  "use strict";
  var I = window.__TAURI_INTERNALS__;
  if (!I || typeof I.invoke !== "function") {
    // 浏览器模式：静默退出，壳功能全部降级为不启用
    return;
  }
  if (window.__MMH3_DESKTOP_BRIDGE__) return; // 幂等：避免 init 脚本重复执行
  window.__MMH3_DESKTOP_BRIDGE__ = true;

  function invoke(cmd, args) {
    return I.invoke(cmd, args || {});
  }

  // 暴露给控制台/后端页面脚本（非必需，便于调试与后续集成）
  window.__mmh3Shell = {
    invoke: invoke,
    openModelGuide: function () { return invoke("open_model_guide"); },
    modelStatus: function () { return invoke("get_model_status"); },
  };
})();
