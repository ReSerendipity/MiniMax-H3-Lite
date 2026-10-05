use anyhow::{anyhow, Result};
use std::time::Duration;

/// 探测本机后端健康端点是否就绪。
/// 契约：backend/main.py 的 `GET /api/health` 返回 `{"status": "ok", ...}`。
/// 注意 `model_loaded` 与就绪无关（权重按需加载），不做等待条件。
pub async fn check_ready(port: u16) -> Result<()> {
    let url = format!("http://127.0.0.1:{port}/api/health");
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()?;
    let resp = client.get(&url).send().await?;
    if !resp.status().is_success() {
        return Err(anyhow!("健康检查失败: HTTP {}", resp.status()));
    }
    let body: serde_json::Value = resp
        .json()
        .await
        .map_err(|e| anyhow!("解析健康检查响应失败: {e}"))?;
    if body.get("status").and_then(|v| v.as_str()) == Some("ok") {
        Ok(())
    } else {
        Err(anyhow!("健康检查未通过: status != ok"))
    }
}

/// 轮询等待服务就绪（500ms 间隔），超时返回错误。
pub async fn wait_for_ready(port: u16, timeout: Duration) -> Result<()> {
    let start = std::time::Instant::now();
    let mut last_error = String::new();

    while start.elapsed() < timeout {
        match check_ready(port).await {
            Ok(()) => return Ok(()),
            Err(e) => {
                last_error = e.to_string();
                tokio::time::sleep(Duration::from_millis(500)).await;
            }
        }
    }

    Err(anyhow!(
        "服务启动超时（{}秒）: {}",
        timeout.as_secs(),
        last_error
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn wait_times_out_on_closed_port() {
        // 绑定后释放，得到一个大概率无监听的端口；短超时应报错而非 panic
        let port = crate::port_manager::find_free_port().unwrap();
        let result = wait_for_ready(port, Duration::from_millis(700)).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("超时"));
    }
}
