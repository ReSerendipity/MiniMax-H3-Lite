//! 模型就绪检查（非阻断引导）：安装形态下 `model/` 是真实空目录，
//! 权重由用户按 MODEL_SETUP_GUIDE.md 从魔搭社区自行下载放位。
//! 壳启动时扫描各类别目录，缺失/为空时在加载页提示指引，不阻断启动。

use std::path::Path;

/// 与 model/README.md 的链接结构、backend comfy_engine._scan_project_models 的扫描口径一致
pub const MODEL_CATEGORIES: [&str; 4] = ["diffusion_models", "text_encoders", "vae", "loras"];

/// 判定某类别目录是否"未就绪"：目录不存在，或顶层无任何有效权重文件。
/// 顶层占位文件（desktop.ini / put_*_here）不算有效权重（对齐 model/README.md 第四节）。
fn category_not_ready(app_dir: &Path, category: &str) -> bool {
    let dir = app_dir.join("model").join(category);
    if !dir.is_dir() {
        return true;
    }
    match std::fs::read_dir(&dir) {
        Ok(entries) => {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().to_lowercase();
                if !entry.path().is_file() {
                    continue;
                }
                if name == "desktop.ini" || name.starts_with("put_") {
                    continue;
                }
                return false; // 找到任一有效文件即视为就绪
            }
            true
        }
        Err(_) => true,
    }
}

/// 返回未就绪的模型类别名列表；空列表 = 全部就绪。
pub fn check_model_dirs(app_dir: &Path) -> Vec<String> {
    MODEL_CATEGORIES
        .iter()
        .filter(|c| category_not_ready(app_dir, c))
        .map(|c| c.to_string())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn touch(path: &Path) {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).unwrap();
        }
        fs::write(path, b"stub").unwrap();
    }

    #[test]
    fn missing_dirs_reported() {
        let tmp = tempfile::tempdir().unwrap();
        let missing = check_model_dirs(tmp.path());
        assert_eq!(
            missing,
            MODEL_CATEGORIES
                .iter()
                .map(|c| c.to_string())
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn populated_category_is_ready() {
        let tmp = tempfile::tempdir().unwrap();
        touch(
            &tmp.path()
                .join("model")
                .join("diffusion_models")
                .join("h3.safetensors"),
        );
        let missing = check_model_dirs(tmp.path());
        assert_eq!(
            missing,
            vec![
                "text_encoders".to_string(),
                "vae".to_string(),
                "loras".to_string()
            ]
        );
    }

    #[test]
    fn placeholder_files_do_not_count() {
        let tmp = tempfile::tempdir().unwrap();
        let cat = tmp.path().join("model").join("vae");
        fs::create_dir_all(&cat).unwrap();
        fs::write(cat.join("desktop.ini"), b"x").unwrap();
        fs::write(cat.join("put_versions_here"), b"x").unwrap();
        let missing = check_model_dirs(tmp.path());
        assert!(missing.contains(&"vae".to_string()));
    }
}
