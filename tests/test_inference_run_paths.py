"""inference.py 主执行路径补测（测试体系评估报告 2026-09-05 · P2-④ 冲 80%）。

覆盖 run_inference 主体（inference.py:153-207，此前 0 覆盖）：
  * diffusers 后端：str 结果落盘 + 资产入库 + 缩略图容错
  * comfy / vllm-omni 分支路由（ADR-0002 / ADR-0003）
  * bytes 结果与非法结果（RuntimeError，绝不假成功）
  * _model_available_locally 本地目录分支
  * _scale_ref_images 的 PIL match / max 两种模式
所有引擎均以桩替换，不触发真实权重加载。
"""
from pathlib import Path

import pytest

from routers import inference as top_inf  # 顶层形态（queue_manager 实际引用）


# ── fixtures ──────────────────────────────────────────────────

@pytest.fixture
def inference_env(monkeypatch, temp_db_path, tmp_path):
    """双形态 patch settings（ASSETS_DIR → tmp_path），返回收集断言用容器。"""
    import config as top_config
    from backend import config as backend_config
    calls = {}

    def fake_backend(name):
        def _active():
            return name
        return _active

    monkeypatch.setattr(top_config.settings, "ASSETS_DIR", tmp_path)
    monkeypatch.setattr(backend_config.settings, "ASSETS_DIR", tmp_path)
    calls["tmp_path"] = tmp_path
    calls["set_backend"] = fake_backend
    return calls


def _task_row(task_id="task_probe"):
    return {"id": task_id}


def _seed_task(shot_id="shot_probe", task_id="task_probe"):
    """temp DB 里插入最小任务行（run_inference 需读取任务行构建参数）。"""
    import database
    conn = database.get_db()
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, name) VALUES ('proj_probe', '探针项目')",
    )
    conn.execute(
        "INSERT OR IGNORE INTO shots (id, project_id, name, prompt) VALUES (?, 'proj_probe', '探针镜头', 'p')",
        (shot_id,),
    )
    conn.execute(
        "INSERT OR REPLACE INTO generation_tasks (id, shot_id, mode, payload, status) VALUES (?, ?, 'text', '{\"prompt\": \"探针提示词\"}', 'pending')",
        (task_id, shot_id),
    )
    conn.commit()
    conn.close()


# ── run_inference 主体 ────────────────────────────────────────

def test_run_inference_diffusers_str_result(inference_env, monkeypatch):
    """diffusers 后端返回 str（产物路径）→ 落盘 + 资产入库。"""
    _seed_task()
    tmp_path = inference_env["tmp_path"]
    src = tmp_path / "out.mp4"
    src.write_bytes(b"fake-video")
    monkeypatch.setattr(top_inf, "active_backend", inference_env["set_backend"]("diffusers"))
    monkeypatch.setattr(top_inf, "_run_diffusers", lambda params: str(src))

    result = top_inf.run_inference("task_probe")
    assert result["asset_id"].startswith("ast_")
    assert result["path"].startswith("assets/ast_")
    dest = tmp_path / Path(result["path"]).name
    assert dest.exists() and dest.stat().st_size == len(b"fake-video")

    import database
    conn = database.get_db()
    row = conn.execute("SELECT * FROM assets WHERE id=?", (result["asset_id"],)).fetchone()
    conn.close()
    assert row is not None and row["kind"] == "result"


def test_run_inference_comfy_branch(inference_env, monkeypatch):
    """comfy 后端路由（ADR-0002）。"""
    _seed_task("shot_comfy", "task_comfy")
    import routers.comfy_engine as ce
    monkeypatch.setattr(top_inf, "active_backend", inference_env["set_backend"]("comfy"))
    seen = {}

    def fake_comfy_run(params):
        seen["params"] = params
        return b"fake-comfy-video"

    monkeypatch.setattr(ce, "run", fake_comfy_run)
    result = top_inf.run_inference("task_comfy")
    assert seen["params"]["prompt"]
    dest = inference_env["tmp_path"] / Path(result["path"]).name
    assert dest.read_bytes() == b"fake-comfy-video"


def test_run_inference_vllm_branch(inference_env, monkeypatch):
    """vllm-omni 后端路由（ADR-0003）。"""
    _seed_task("shot_vllm", "task_vllm")
    import routers.vllm_omni_engine as ve
    monkeypatch.setattr(top_inf, "active_backend", inference_env["set_backend"]("vllm-omni"))
    monkeypatch.setattr(ve, "run", lambda params: b"fake-vllm-video")
    result = top_inf.run_inference("task_vllm")
    assert result["asset_id"].startswith("ast_")


def test_run_inference_invalid_result_raises(inference_env, monkeypatch):
    """推理返回不存在的路径 → RuntimeError，绝不假成功。"""
    _seed_task("shot_bad", "task_bad")
    monkeypatch.setattr(top_inf, "active_backend", inference_env["set_backend"]("diffusers"))
    monkeypatch.setattr(top_inf, "_run_diffusers", lambda params: "Z:/no/such/file.mp4")
    with pytest.raises(RuntimeError, match="推理未产出有效文件"):
        top_inf.run_inference("task_bad")


# ── 辅助函数 ──────────────────────────────────────────────────

def test_model_available_locally_true_for_local_dir(monkeypatch, tmp_path):
    """MODEL_PATH 指向含 model_index.json 的目录 → True。"""
    import config as top_config
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model_index.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(top_config.settings, "MODEL_PATH", str(model_dir))
    assert top_inf._model_available_locally(str(model_dir)) is True


def test_extract_thumbnail_missing_ffmpeg_is_silent(tmp_path):
    """ffmpeg 缺失时缩略图提取静默失败，不影响主流程。"""
    missing = tmp_path / "no_such_video.mp4"
    top_inf._extract_thumbnail(str(missing), str(tmp_path / "thumb.jpg"))


def test_scale_ref_images_match_mode(real_png_image, tmp_path):
    """ref_image_size=match：参考图缩放到生成分辨率。"""
    from PIL import Image
    p = tmp_path / "ref.png"
    p.write_bytes(real_png_image)
    out = top_inf._scale_ref_images([str(p)], 1344, 768, "match")
    with Image.open(out[0]) as im:
        assert im.size == (1344, 768)


def test_scale_ref_images_max_mode_caps_short_side(real_png_image, tmp_path):
    """ref_image_size=max：短边不超过 2048。"""
    from PIL import Image
    p = tmp_path / "ref.png"
    p.write_bytes(real_png_image)
    out = top_inf._scale_ref_images([str(p)], 1344, 768, "max")
    with Image.open(out[0]) as im:
        w, h = im.size
        assert min(w, h) <= 2048


def test_scale_ref_images_pil_missing_returns_original(monkeypatch):
    """PIL 缺失时原样返回路径列表（容错分支）。"""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "PIL.Image" or name == "PIL":
            raise ImportError("no PIL")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = top_inf._scale_ref_images(["x.png"], 100, 100, "match")
    assert out == ["x.png"]
