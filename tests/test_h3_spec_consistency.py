"""H3 规格层一致性测试：与三份官方工作流 JSON 对齐 + 引擎切换冒烟"""
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from h3 import spec as h3


# ── 辅助：读取 JSON 工作流中的子图节点 ──────────────
def _load_workflow(name: str) -> dict:
    path = PROJECT_ROOT / "workflows" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    # t2v/i2v 模板是子图格式（nodes 在 definitions.subgraphs[0].nodes）；
    # r2v 模板是扁平格式（nodes 在顶层），两者统一归一化。
    sub = data.get("definitions", {}).get("subgraphs", [{}])[0]
    raw = sub.get("nodes") or data.get("nodes") or []
    return {n["id"]: n for n in raw}


def _get_widget(nodes: dict, nid: int, key: str):
    """从节点 widgets_values_named 或 widgets_values 中取值"""
    n = nodes.get(nid)
    if not n:
        return None
    named = n.get("widgets_values_named", {})
    return named.get(key)


# ── 测试：规格层模型文件名与官方模板一致 ──────────────
def test_model_filenames_t2v():
    """t2v/i2v 模板使用 fl2va 权重"""
    nodes = _load_workflow("video_minimax_h3_t2v.json")
    unet = _get_widget(nodes, 6, "unet_name")
    assert unet, "official t2v template: no UNETLoader node 6"
    assert unet == h3.MODELS["fl2va"], f"expected fl2va, got {unet}"


def test_model_filenames_i2v():
    """i2v 模板使用 fl2va 权重"""
    nodes = _load_workflow("video_minimax_h3_i2v.json")
    unet = _get_widget(nodes, 6, "unet_name")
    assert unet, "official i2v template: no UNETLoader node 6"
    assert unet == h3.MODELS["fl2va"], f"expected fl2va, got {unet}"


def test_model_filenames_r2v():
    """r2v 模板使用 ref2va 权重"""
    nodes = _load_workflow("video_minimax_h3_r2v.json")
    unet = _get_widget(nodes, 127, "unet_name")
    assert unet, "official r2v template: no UNETLoader node 127"
    assert unet == h3.MODELS["ref2va"], f"expected ref2va, got {unet}"


def test_clip_model_name():
    """三份模板均使用相同的 CLIP 模型"""
    for name in ("video_minimax_h3_t2v.json", "video_minimax_h3_i2v.json", "video_minimax_h3_r2v.json"):
        nodes = _load_workflow(name)
        clip = _get_widget(nodes, 13, "clip_name") if "t2v" in name or "i2v" in name else _get_widget(nodes, 128, "clip_name")
        if not clip:
            clip = _get_widget(nodes, 13, "clip_name") or _get_widget(nodes, 128, "clip_name")
        assert clip, f"no CLIP widget in {name}"
        assert clip == h3.MODELS["clip"], f"expected {h3.MODELS['clip']}, got {clip}"


def test_vae_video_model():
    """三份模板均使用相同的 video VAE"""
    for name in ("video_minimax_h3_t2v.json", "video_minimax_h3_i2v.json", "video_minimax_h3_r2v.json"):
        nodes = _load_workflow(name)
        vae = _get_widget(nodes, 11, "vae_name") or _get_widget(nodes, 119, "vae_name")
        assert vae, f"no video VAE widget in {name}"
        assert vae == h3.MODELS["vae_video"], f"expected {h3.MODELS['vae_video']}, got {vae}"


def test_vae_audio_model():
    """三份模板均使用相同的 audio VAE"""
    for name in ("video_minimax_h3_t2v.json", "video_minimax_h3_i2v.json", "video_minimax_h3_r2v.json"):
        nodes = _load_workflow(name)
        vae = _get_widget(nodes, 24, "vae_name") or _get_widget(nodes, 120, "vae_name")
        assert vae, f"no audio VAE widget in {name}"
        assert vae == h3.MODELS["vae_audio"], f"expected {h3.MODELS['vae_audio']}, got {vae}"


# ── 测试：帧长公式 ──────────────────────────────────
def test_frames_for_duration():
    assert h3.frames_for_duration(4) == 107, f"4s: {h3.frames_for_duration(4)}"
    assert h3.frames_for_duration(8) == 192, f"8s: {h3.frames_for_duration(8)}"
    assert h3.frames_for_duration(10) == 243, f"10s: {h3.frames_for_duration(10)}"
    assert h3.frames_for_duration(15) == 362, f"15s: {h3.frames_for_duration(15)}"


# ── 测试：分辨率规范 ────────────────────────────────
def test_resolution_for_multiple_2():
    w, h = h3.resolution_for("16:9", multiple=2)
    assert w % 2 == 0 and h % 2 == 0, f"diffusers even: ({w}, {h})"
    assert w >= h and w <= h3.MAX_DIM and h == h3.SHORT_SIDE


def test_resolution_for_multiple_32():
    w, h = h3.resolution_for("16:9", multiple=32)
    assert w % 32 == 0 and h % 32 == 0, f"comfyui 32-multiple: ({w}, {h})"
    assert w >= h and w <= h3.MAX_DIM and h == h3.SHORT_SIDE


def test_resolution_capped():
    """21:9 宽屏应有足够宽度，但不超过 MAX_DIM"""
    w, h = h3.resolution_for("21:9", multiple=2)
    assert w <= h3.MAX_DIM, f"21:9 width {w} > MAX_DIM {h3.MAX_DIM}"


# ── 测试：mode → task_type 映射 ─────────────────────
def test_mode_mapping():
    assert h3.MODE_TO_TASK["text"] == h3.T2VA
    assert h3.MODE_TO_TASK["first_frame"] == h3.FL2VA
    assert h3.MODE_TO_TASK["last_frame"] == h3.FL2VA
    assert h3.MODE_TO_TASK["first_last"] == h3.FL2VA
    assert h3.MODE_TO_TASK["ref"] == h3.REF2VA


# ── 测试：引擎切换冒烟 ──────────────────────────────
def test_engine_registry_imports():
    from engine_registry import list_engines, active_backend, switch_backend, ENGINES
    engs = list_engines()
    assert len(engs) == len(ENGINES), f"expected {len(ENGINES)} engines, got {len(engs)}"
    for e in engs:
        assert e["name"] in ENGINES
        assert "active" in e
        assert "implemented" in e
    assert active_backend() in ENGINES


def test_engine_switch_persistence(tmp_path, monkeypatch):
    """切换引擎并持久化后回读（当前仅 diffusers 一种）"""
    from engine_registry import switch_backend, active_backend, list_engines
    from settings_store import resolve

    # 确保环境变量不干扰
    monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)
    
    # 当前只有 diffusers 一个引擎，确认它存在且可用
    engines = list_engines()
    assert any(e["name"] == "diffusers" for e in engines), "diffusers engine missing"
    
    # 切换到 diffusers → 持久化
    result = switch_backend("diffusers")
    assert result["name"] == "diffusers"
    assert resolve("inference_backend") == "diffusers"


def test_health_backend_field():
    """/api/health 应包含 backend 与 backend_requires_external"""
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        h = c.get("/api/health").json()
        assert "backend" in h, f"health missing 'backend': {h}"
        assert "backend_requires_external" in h, f"health missing 'backend_requires_external': {h}"
        assert h["backend"] == "diffusers", f"expected diffusers but got {h['backend']}"
        assert h["backend_requires_external"] is False, "diffusers should not require external service"


def test_engines_endpoint():
    """GET /api/engines 返回完整可用引擎列表（当前仅 diffusers）"""
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        r = c.get("/api/engines")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "engines" in data
        assert "active" in data
        assert "locked" in data
        # 目前只有 diffusers 一个引擎
        engine_names = [e["name"] for e in data["engines"]]
        assert "diffusers" in engine_names
        assert len(data["engines"]) >= 1
