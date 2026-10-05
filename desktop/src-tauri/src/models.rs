//! 模型就绪检查（非阻断引导）：安装形态下 `model/` 是真实空目录，
//! 权重由用户按 MODEL_SETUP_GUIDE.md 从魔搭社区自行下载放位。
//! 壳启动时扫描各类别目录，缺失/为空时在加载页提示指引，不阻断启动。

use std::path::Path;

/// 与 model/README.md 的链接结构、backend comfy_engine._scan_project_models 的扫描口径一致
pub const MODEL_CATEGORIES: [&str; 4] = ["diffusion_models", "text_encoders", "vae", "loras"];

/// 判定文件名是否为 H3 专属权重（输入应已小写）。
/// model/ 各类别是整类共享目录（开发机 Junction 场景会混入 FLUX/Qwen-Image 等
/// 非 H3 模型），就绪提示必须认「具体 H3 模型」而非任意文件。覆盖现行 9 个
/// 官方文件名：MiniMax_H3_* / minimax_h3_* / qwen3vl_*_minimax_h3_* / h3-*。
fn is_h3_weight(lower_name: &str) -> bool {
    lower_name.contains("minimax_h3") || lower_name.starts_with("h3-")
}

/// 判定某类别目录是否"未就绪"：目录不存在，或顶层无任何有效 H3 权重文件。
/// 顶层占位文件（desktop.ini / put_*_here）与非 H3 模型都不算（对齐
/// model/README.md 第四节与 comfy_engine 注入时的子串匹配口径）。
fn category_not_ready(app_dir: &Path, category: &str) -> bool {
    let dir = app_dir.join("model").join(category);
    if !dir.is_dir() {
        return true;
    }
    match std::fs::read_dir(&dir) {
        Ok(entries) => {
            for entry in entries.flatten() {
                if !entry.path().is_file() {
                    continue;
                }
                let name = entry.file_name().to_string_lossy().to_lowercase();
                if name == "desktop.ini" || name.starts_with("put_") {
                    continue;
                }
                if is_h3_weight(&name) {
                    return false; // 找到任一 H3 权重即视为就绪
                }
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
                .join("MiniMax_H3_FL2VA_pruned_int8_convrot.safetensors"),
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
    fn non_h3_models_do_not_count() {
        // 整类共享目录场景：FLUX/Qwen 等非 H3 模型在场不代表 H3 就绪
        let tmp = tempfile::tempdir().unwrap();
        let vae = tmp.path().join("model").join("vae");
        fs::create_dir_all(&vae).unwrap();
        fs::write(vae.join("flux_1_dev_vae.safetensors"), b"x").unwrap();
        fs::write(vae.join("qwen_image_vae.safetensors"), b"x").unwrap();
        let missing = check_model_dirs(tmp.path());
        assert!(missing.contains(&"vae".to_string()));
        // 放入真正的 H3 权重后即就绪
        fs::write(vae.join("minimax_h3_video_vae_fp16.safetensors"), b"x").unwrap();
        let missing = check_model_dirs(tmp.path());
        assert!(!missing.contains(&"vae".to_string()));
    }

    #[test]
    fn h3_lora_prefix_recognized() {
        // h3-realism-people 系列以 h3- 前缀命名（无 minimax_h3 子串）
        let tmp = tempfile::tempdir().unwrap();
        touch(
            &tmp.path()
                .join("model")
                .join("loras")
                .join("h3-realism-people-t2v-i2v-r2v.safetensors"),
        );
        let missing = check_model_dirs(tmp.path());
        assert!(!missing.contains(&"loras".to_string()));
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
