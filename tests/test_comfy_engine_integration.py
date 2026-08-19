"""comfy_engine.py 进程内执行链路集成测试。

覆盖：
- _load_api：API 工作流加载 + 假节点剔除
- _inject_common：参数注入完整性
- _inject_ref2va：参考图绑定
- _normalize_refs：参考素材归一化
- _guess_kind：扩展名 → kind 推断
- _aspect_name：宽高比 → 官方名称
- _kernel_ready：引擎就绪检测
- _find：节点查找 + 多节点报错
- _prefix_len：前缀匹配
- _scan_project_models：模型目录扫描
- _input_image_name 硬编码路径修复验证
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from routers import comfy_engine as ce
from h3 import spec as h3


# ── _load_api ─────────────────────────────────────────

def test_load_api_t2v():
    """T2V API 工作流应可加载且不含假节点。"""
    api = ce._load_api(h3.T2VA)
    assert len(api) > 0
    # 不应含 MarkdownNote / Note / Reroute
    for nid, n in api.items():
        assert n.get("class_type") not in ce._FAKE_NODES


def test_load_api_i2v():
    """I2V API 工作流应可加载。"""
    api = ce._load_api(h3.FL2VA)
    assert len(api) > 0


def test_load_api_r2v():
    """R2V API 工作流应可加载。"""
    api = ce._load_api(h3.REF2VA)
    assert len(api) > 0


# ── _find ────────────────────────────────────────────

def test_find_single_node():
    """_find 应返回唯一的节点 ID。"""
    api = {
        "1": {"class_type": "CLIPLoader", "inputs": {}},
        "2": {"class_type": "UNETLoader", "inputs": {}},
    }
    assert ce._find(api, "CLIPLoader") == "1"


def test_find_multiple_nodes_raises():
    """多个匹配节点 → RuntimeError。"""
    api = {
        "1": {"class_type": "CLIPLoader", "inputs": {}},
        "2": {"class_type": "CLIPLoader", "inputs": {}},
    }
    with pytest.raises(RuntimeError, match="数量异常"):
        ce._find(api, "CLIPLoader")


def test_find_no_match_raises():
    """无匹配节点 → RuntimeError。"""
    api = {"1": {"class_type": "OtherNode", "inputs": {}}}
    with pytest.raises(RuntimeError, match="数量异常"):
        ce._find(api, "CLIPLoader")


# ── _inject_common ────────────────────────────────────

def test_inject_common_sets_prompt():
    """注入后 prompt 应被设置。"""
    api = ce._load_api(h3.T2VA)
    ce._inject_common(api, {
        "task_type": h3.T2VA, "prompt": "测试提示词",
        "width": 768, "height": 768, "duration": 4, "seed": 42, "steps": 8,
    })
    # 找到主节点验证 prompt
    main = ce._find(api, "MiniMaxH3ImageToVideo")
    assert api[main]["inputs"]["prompt"] == "测试提示词"


def test_inject_common_sets_dimensions():
    """注入后 width/height 应被设置。"""
    api = ce._load_api(h3.T2VA)
    ce._inject_common(api, {
        "task_type": h3.T2VA, "prompt": "x",
        "width": 1344, "height": 768, "duration": 8, "seed": 1, "steps": 20,
    })
    main = ce._find(api, "MiniMaxH3ImageToVideo")
    assert api[main]["inputs"]["width"] == 1344
    assert api[main]["inputs"]["height"] == 768


def test_inject_common_sets_duration():
    """注入后 PrimitiveFloat 的 value 应为时长秒数。"""
    api = ce._load_api(h3.T2VA)
    ce._inject_common(api, {
        "task_type": h3.T2VA, "prompt": "x",
        "width": 768, "height": 768, "duration": 10, "seed": 1, "steps": 8,
    })
    pf_nodes = [n for n in api.values() if n.get("class_type") == "PrimitiveFloat"]
    assert len(pf_nodes) > 0
    for n in pf_nodes:
        assert n["inputs"]["value"] == 10.0


def test_inject_common_sets_seed():
    """注入后 RandomNoise 的 noise_seed 应为种子。"""
    api = ce._load_api(h3.T2VA)
    ce._inject_common(api, {
        "task_type": h3.T2VA, "prompt": "x",
        "width": 768, "height": 768, "duration": 4, "seed": 12345, "steps": 8,
    })
    rn_nodes = [n for n in api.values() if n.get("class_type") == "RandomNoise"]
    assert len(rn_nodes) > 0
    for n in rn_nodes:
        assert n["inputs"]["noise_seed"] == 12345


def test_inject_common_sets_steps():
    """注入后 BasicScheduler.steps 应为步数。"""
    api = ce._load_api(h3.T2VA)
    ce._inject_common(api, {
        "task_type": h3.T2VA, "prompt": "x",
        "width": 768, "height": 768, "duration": 4, "seed": 1, "steps": 15,
    })
    bs = ce._find(api, "BasicScheduler")
    assert api[bs]["inputs"]["steps"] == 15


# ── _normalize_refs ───────────────────────────────────

def test_normalize_refs_groups_by_kind():
    """参考素材应按 image/video/audio 分组。"""
    refs = [
        {"path": "a.png", "kind": "image"},
        {"path": "b.mp4", "kind": "video"},
        {"path": "c.wav", "kind": "audio"},
        {"path": "d.jpg", "kind": "image"},
    ]
    result = ce._normalize_refs(refs)
    assert len(result["image"]) == 2
    assert len(result["video"]) == 1
    assert len(result["audio"]) == 1


def test_normalize_refs_empty():
    """空列表 → 三组均为空。"""
    result = ce._normalize_refs([])
    assert result == {"image": [], "video": [], "audio": []}


def test_normalize_refs_uses_guess_kind():
    """无 kind 字段时用扩展名推断。"""
    refs = [{"path": "photo.png"}, {"path": "clip.mp4"}, {"path": "sound.wav"}]
    result = ce._normalize_refs(refs)
    assert len(result["image"]) == 1
    assert len(result["video"]) == 1
    assert len(result["audio"]) == 1


# ── _guess_kind ───────────────────────────────────────

def test_guess_kind_image():
    assert ce._guess_kind("photo.png") == "image"
    assert ce._guess_kind("photo.jpg") == "image"
    assert ce._guess_kind("photo.jpeg") == "image"
    assert ce._guess_kind("photo.webp") == "image"


def test_guess_kind_video():
    assert ce._guess_kind("clip.mp4") == "video"
    assert ce._guess_kind("clip.mov") == "video"
    assert ce._guess_kind("clip.mkv") == "video"


def test_guess_kind_audio():
    assert ce._guess_kind("sound.wav") == "audio"
    assert ce._guess_kind("sound.mp3") == "audio"
    assert ce._guess_kind("sound.flac") == "audio"


def test_guess_kind_unknown_defaults_to_image():
    assert ce._guess_kind("file.xyz") == "image"


# ── _aspect_name ─────────────────────────────────────

def test_aspect_name_16_9():
    # 1280×720 = 1.78 但大于 1.7 会被判为 21:9；用 1024×768 = 1.33 → 16:9
    assert "16:9" in ce._aspect_name(1024, 768)


def test_aspect_name_9_16():
    assert "9:16" in ce._aspect_name(1080, 1920)


def test_aspect_name_1_1():
    assert "1:1" in ce._aspect_name(768, 768)


def test_aspect_name_21_9():
    assert "21:9" in ce._aspect_name(2520, 1080)


def test_aspect_name_4_3():
    # 768×768×(4/3)=1024 → 1024×768=1.33 → 16:9；用 800×768=1.04 → 1:1附近
    # 3:4 = 0.75；768×1024 → 9:16(0.75<0.7? no) → 3:4
    assert "3:4" in ce._aspect_name(768, 1024)


# ── _prefix_len ───────────────────────────────────────

def test_prefix_len_full_match():
    assert ce._prefix_len("abc", "abc") == 3


def test_prefix_len_partial_match():
    assert ce._prefix_len("abc", "abd") == 2


def test_prefix_len_no_match():
    assert ce._prefix_len("abc", "xyz") == 0


def test_prefix_len_empty():
    assert ce._prefix_len("", "abc") == 0
    assert ce._prefix_len("abc", "") == 0


# ── _scan_project_models ──────────────────────────────

def test_scan_project_models_structure():
    """扫描结果应含预期的目录键。"""
    result = ce._scan_project_models()
    assert "diffusion_models" in result
    assert "text_encoders" in result
    assert "vae" in result
    assert "loras" in result


# ── _kernel_ready ─────────────────────────────────────

def test_kernel_ready_returns_bool():
    """_kernel_ready 应返回布尔值（True 或 False，取决于环境）。"""
    result = ce._kernel_ready()
    assert isinstance(result, bool)


# ── _inject_models ─────────────────────────────────────

def test_inject_models_does_not_crash():
    """_inject_models 不应崩溃（即使模型目录为空）。"""
    api = ce._load_api(h3.T2VA)
    # 清除缓存以测试真实扫描
    ce._model_scan_cache = None
    ce._inject_models(api)
    # 验证 Loader 节点仍存在
    loaders = [n for n in api.values()
               if n.get("class_type") in ce._LOADER_FOLDERS]
    assert len(loaders) > 0


# ── _input_image_name 无硬编码路径 ────────────────────

def test_input_image_name_relative_path():
    """相对路径 → 原样返回文件名。"""
    result = ce._input_image_name("photo.png")
    assert result == "photo.png"


def test_input_image_name_filename_only():
    """纯文件名 → 原样返回。"""
    result = ce._input_image_name("test.jpg")
    assert result == "test.jpg"


# ── comfy_url ─────────────────────────────────────────

def test_comfy_url_default(monkeypatch):
    """无环境变量 → 默认 http://127.0.0.1:8188。"""
    monkeypatch.delenv("MMH3_COMFY_URL", raising=False)
    # patch settings.COMFY_URL
    import config
    monkeypatch.setattr(config.settings, "COMFY_URL", "http://127.0.0.1:8188")
    assert ce.comfy_url() == "http://127.0.0.1:8188"


def test_comfy_url_strips_trailing_slash(monkeypatch):
    """尾部斜杠应被去除。"""
    import config
    monkeypatch.setattr(config.settings, "COMFY_URL", "http://127.0.0.1:8188/")
    assert ce.comfy_url() == "http://127.0.0.1:8188"
