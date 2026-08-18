"""H3 规格层一致性测试：与三份官方工作流 JSON 对齐 + 引擎切换冒烟

使用 conftest.py fixtures 简化测试代码。
"""
import json
import sys
from pathlib import Path

# 将项目根目录加入路径
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
def test_frames_for_duration(h3_spec):
    assert h3_spec.frames_for_duration(4) == 107, f"4s: {h3_spec.frames_for_duration(4)}"
    assert h3_spec.frames_for_duration(8) == 192, f"8s: {h3_spec.frames_for_duration(8)}"
    assert h3_spec.frames_for_duration(10) == 243, f"10s: {h3_spec.frames_for_duration(10)}"
    assert h3_spec.frames_for_duration(15) == 362, f"15s: {h3_spec.frames_for_duration(15)}"


# ── 测试：分辨率规范 ────────────────────────────────
def test_resolution_for_multiple_2(h3_spec):
    w, h = h3_spec.resolution_for("16:9", multiple=2)
    assert w % 2 == 0 and h % 2 == 0, f"diffusers even: ({w}, {h})"
    assert w >= h and w <= h3_spec.MAX_DIM and h == h3_spec.SHORT_SIDE


def test_resolution_for_multiple_32(h3_spec):
    w, h = h3_spec.resolution_for("16:9", multiple=32)
    assert w % 32 == 0 and h % 32 == 0, f"comfyui 32-multiple: ({w}, {h})"
    assert w >= h and w <= h3_spec.MAX_DIM and h == h3_spec.SHORT_SIDE


def test_resolution_capped(h3_spec):
    """21:9 宽屏应有足够宽度，但不超过 MAX_DIM"""
    w, h = h3_spec.resolution_for("21:9", multiple=2)
    assert w <= h3_spec.MAX_DIM, f"21:9 width {w} > MAX_DIM {h3_spec.MAX_DIM}"


# ── 测试：mode → task_type 映射 ─────────────────────
def test_mode_mapping(h3_spec):
    assert h3_spec.MODE_TO_TASK["text"] == h3_spec.T2VA
    assert h3_spec.MODE_TO_TASK["first_frame"] == h3_spec.FL2VA
    assert h3_spec.MODE_TO_TASK["last_frame"] == h3_spec.FL2VA
    assert h3_spec.MODE_TO_TASK["first_last"] == h3_spec.FL2VA
    assert h3_spec.MODE_TO_TASK["ref"] == h3_spec.REF2VA


# ── 测试：引擎切换冒烟 ──────────────────────────────
def test_engine_registry_imports():
    from engine_registry import list_engines, active_backend, ENGINES
    engs = list_engines()
    assert len(engs) == len(ENGINES), f"expected {len(ENGINES)} engines, got {len(engs)}"
    for e in engs:
        assert e["name"] in ENGINES
        assert "active" in e
        assert "implemented" in e
    assert active_backend() in ENGINES


def test_engine_switch_persistence(monkeypatch):
    """切换引擎并持久化后回读（当前仅支持 diffusers）"""
    import tempfile
    import json
    from pathlib import Path

    from engine_registry import switch_backend
    from settings_store import resolve

    # 创建临时文件作为数据存储路径
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_settings_file = Path(f.name)

    try:
        # 确保环境变量不干扰
        monkeypatch.delenv("MMH3_INFERENCE_BACKEND", raising=False)

        # 桩化 load/save 函数以使用临时文件
        def mock_load():
            try:
                return json.loads(temp_settings_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}

        def mock_save(data: dict):
            temp_settings_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        monkeypatch.setattr("settings_store._load", mock_load)
        monkeypatch.setattr("settings_store._save", mock_save)

        # 当前仅有 diffusers 引擎，切换自身→自证明有效
        result = switch_backend("diffusers")
        assert result["name"] == "diffusers"
        assert resolve("inference_backend") == "diffusers"
    finally:
        # 清理临时文件
        if temp_settings_file.exists():
            temp_settings_file.unlink()


def test_health_backend_field(client):
    """/api/health 应包含 backend 与 backend_requires_external"""
    h = client.get("/api/health").json()
    assert "backend" in h, f"health missing 'backend': {h}"
    assert "backend_requires_external" in h, f"health missing 'backend_requires_external': {h}"
    assert h["backend"] in ("diffusers", "comfyui", "sglang")


def test_engines_endpoint(client):
    """GET /api/engines 返回完整可用引擎列表"""
    r = client.get("/api/engines")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "engines" in data
    assert "active" in data
    assert "locked" in data
    assert len(data["engines"]) >= 1
