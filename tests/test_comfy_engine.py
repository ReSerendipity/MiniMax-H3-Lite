"""comfy_engine（B 方案，ComfyUI HTTP 提交官方工作流）单测：
- 任务 → 官方工作流映射（t2va→t2v, fl2va→i2v, ref2va→r2v）
- 工作流 editor→API 转换 + 假节点剔除
- 参数注入（分辨率/时长/种子/prompt/clip 名）
- Comfy URL 解析
不连接真实 ComfyUI、不跑推理。
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from routers import comfy_engine as ce
from h3 import spec as h3


def _scan_for(models_dir):
    """返回 models 目录下存在的文件名集合，用于断言注入引用匹配。"""
    found = set()
    if models_dir.is_dir():
        for p in models_dir.rglob("*.safetensors"):
            found.add(p.name)
    return found


def test_task_to_workflow_mapping():
    """三任务应映射到对应官方工作流文件。"""
    assert ce._WORKFLOW_FILES[h3.T2VA] == "video_minimax_h3_t2v.json"
    assert ce._WORKFLOW_FILES[h3.FL2VA] == "video_minimax_h3_i2v.json"
    assert ce._WORKFLOW_FILES[h3.REF2VA] == "video_minimax_h3_r2v.json"


def test_load_api_strips_fake_nodes():
    """加载官方工作流后不应残留 MarkdownNote 等前端假节点。"""
    for task in (h3.T2VA, h3.FL2VA, h3.REF2VA):
        api = ce._load_api(task)
        for nid, n in api.items():
            assert n["class_type"] not in ce._FAKE_NODES, (task, nid, n["class_type"])
        assert len(api) >= 15, (task, len(api))


def test_workflows_exist():
    """官方工作流文件应在 aki 目录存在。"""
    for task in (h3.T2VA, h3.FL2VA, h3.REF2VA):
        assert (ce._WORKFLOW_DIR / ce._WORKFLOW_FILES[task]).is_file()


def test_inject_prompt_ratio_and_seed():
    """注入 prompt/综合分辨率/种子到主节点。"""
    for task, main_cls in ((h3.T2VA, "MiniMaxH3ImageToVideo"),
                           (h3.FL2VA, "MiniMaxH3ImageToVideo"),
                           (h3.REF2VA, "MiniMaxH3ReferenceToVideo")):
        api = ce._load_api(task)
        ce._inject_common(api, {
            "task_type": task, "prompt": "hello", "width": 768, "height": 768,
            "duration": 4, "seed": 7, "steps": 8})
        main = ce._find(api, main_cls)
        assert api[main]["inputs"]["prompt"] == "hello"
        if task != h3.REF2VA:
            assert api[main]["inputs"]["width"] == 768
            assert api[main]["inputs"]["height"] == 768
        seed_seen = [n["inputs"]["noise_seed"] for n in api.values()
                     if n.get("class_type") == "RandomNoise"]
        assert 7 in seed_seen


def test_inject_duration_into_primitive_float():
    """PrimitiveFloat 秒数应注入为请求时长（驱动 ComfyMathExpression 帧数）。"""
    api = ce._load_api(h3.T2VA)
    ce._inject_common(api, {"task_type": h3.T2VA, "prompt": "x", "width": 768,
                            "height": 768, "duration": 6, "seed": 1, "steps": 8})
    pf = [n["inputs"].get("value") for n in api.values()
          if n.get("class_type") == "PrimitiveFloat"]
    assert 6.0 in pf, pf


# 官方工作流里写死的 clip 名（backend/workflows/api/*.api.json 的 CLIPLoader 输入）
_OFFICIAL_CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
# 项目实际分发的 clip 文件名。取自 model/README.md 的 text_encoders 行；
# model/ 被 .gitignore 整体排除（README 也不入库），故在此内联为常量并注明出处。
_PROJECT_CLIP = "qwen3vl_32b_minimax_h3_abliterated_nvfp4.safetensors"


@pytest.fixture
def fake_project_root(tmp_path):
    """合成一个"项目根"，只含 model/text_encoders/<0 字节占位文件>。

    为什么把树造在 tmp 而不是提交到 tests/fixtures/：
      - `_scan_project_models()` 写死读 `_BASE_DIR / "model"`，目录名 `model` 不可改；
      - `.gitignore:166` 的 `model/` 按目录名匹配**任意层级**，`tests/fixtures/model/`
        同样被排除；`.gitignore:114` 另有全局 `*.safetensors`。
        实测 `git check-ignore -v tests/fixtures/model/text_encoders/probe.safetensors`
        → `.gitignore:166:model/`。要提交就得加 3 条形如
        `!tests/fixtures/model/**` 的反向规则，而那会削弱"权重永不入库"这条不变量。
    所以这里在 tmp 里造同名结构：托管 runner 与本地行为一致，仓库里没有任何
    .safetensors，也不需要动忽略规则。
    """
    d = tmp_path / "model" / "text_encoders"
    d.mkdir(parents=True)
    (d / _PROJECT_CLIP).write_bytes(b"")  # 占位：只需要文件名可被扫到
    old_base, old_cache = ce._BASE_DIR, ce._model_scan_cache
    ce._BASE_DIR = tmp_path
    ce._model_scan_cache = None           # 缓存必须清，否则读到真实项目的空扫描结果
    try:
        yield tmp_path
    finally:
        ce._BASE_DIR = old_base
        ce._model_scan_cache = old_cache


def test_scan_project_models_reads_project_root(fake_project_root):
    """真实扫描路径：应扫出 text_encoders 下的文件名（不需要权重内容）。"""
    imports = ce._scan_project_models()
    assert imports["text_encoders"] == [_PROJECT_CLIP], imports["text_encoders"]
    assert imports["diffusion_models"] == []
    assert imports["vae"] == []


def test_clip_name_pinned_to_existing(fake_project_root):
    """三个任务的 clip 名都应被改写为项目里确实存在的文件。

    原实现在 model/ 无权重时 pytest.skip —— 而 CI 与任何干净检出都没有权重，
    所以这条断言在托管 runner 上从未真正执行过。改为对合成项目根跑，
    三任务 × 真实工作流 JSON × 真实注入逻辑，全程不碰 model/。
    """
    for task in (h3.T2VA, h3.FL2VA, h3.REF2VA):
        api = ce._load_api(task)
        cl = ce._find(api, "CLIPLoader")
        assert api[cl]["inputs"]["clip_name"] == _OFFICIAL_CLIP, \
            f"{task}: 工作流里的 clip 名已变更，请同步 _OFFICIAL_CLIP 与本用例断言"
        ce._inject_common(api, {"task_type": task, "prompt": "x", "width": 768,
                                "height": 768, "duration": 4, "seed": 1, "steps": 8})
        name = api[cl]["inputs"]["clip_name"]
        assert name == _PROJECT_CLIP, f"{task}: 注入结果 {name} 不是项目实际存在的文件"


def test_clip_name_matches_real_weights_if_present():
    """若本机 model/ 真有权重，则注入结果必须落在真实文件集合里（保留原强度）。"""
    project_model_dir = Path(__file__).resolve().parent.parent / "model"
    clip_files = _scan_for(project_model_dir)
    if not clip_files:
        pytest.skip(f"项目 model/ 目录无权重文件: {project_model_dir}")
    for task in (h3.T2VA, h3.FL2VA, h3.REF2VA):
        api = ce._load_api(task)
        ce._inject_common(api, {"task_type": task, "prompt": "x", "width": 768,
                                "height": 768, "duration": 4, "seed": 1, "steps": 8})
        cl = ce._find(api, "CLIPLoader")
        name = api[cl]["inputs"]["clip_name"]
        assert name in clip_files, f"{task}: clip {name} 不在项目 model/ 里"


def test_guess_kind_by_extension():
    assert ce._guess_kind("a.png") == "image"
    assert ce._guess_kind("b.mp4") == "video"
    assert ce._guess_kind("c.wav") == "audio"


def test_ref2va_inject_images():
    """r2v 应用 LoadImage 槽绑定参考图。"""
    api = ce._load_api(h3.REF2VA)
    refs = [{"kind": "image", "path": "x1.png"}, {"kind": "image", "path": "x2.png"}]
    ce._inject_common(api, {"task_type": h3.REF2VA, "prompt": "p", "width": 768,
                            "height": 768, "duration": 4, "seed": 1, "steps": 8,
                            "refs": refs})
    ce._inject_ref2va(api, {"task_type": h3.REF2VA, "prompt": "p", "refs": refs})
    main = api[ce._find(api, "MiniMaxH3ReferenceToVideo")]
    bound = [k for k in main["inputs"] if k.startswith("ref_images.")]
    assert len(bound) == 2, bound


def test_comfy_url():
    """Comfy URL 解析（默认 8188，MMH3_COMFY_URL 可覆盖）。"""
    assert ce.comfy_url() == "http://127.0.0.1:8188"
    ce.settings.COMFY_URL = "http://1.2.3.4:9999"
    assert ce.comfy_url() == "http://1.2.3.4:9999"
    ce.settings.COMFY_URL = "http://127.0.0.1:8188"
