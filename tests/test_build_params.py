"""_build_params 规范化层单测（不依赖真实模型）：
- G3 配对音轨 → refs.paired_video 解析
- G7 跟随首帧图像尺寸 → width/height 换算（768p 短边 + 32/2 倍数 + 1344 封顶）
- G2/G5 种子与采样参数透传、ref_image_size 请求级优先

使用 conftest.py fixtures 简化测试代码。
"""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from routers.inference import _build_params


def _upload(client, sid, filename, mime, content, paired_with=None):
    """辅助上传函数"""
    data = {"shot_id": sid}
    if paired_with:
        data["paired_with"] = paired_with
    r = client.post("/api/upload", files={"file": (filename, content, mime)}, data=data)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _task_row(sid, mode, ref_ids, params):
    """构建任务行数据"""
    return {
        "shot_id": sid,
        "mode": mode,
        "payload": json.dumps({"prompt": "测试提示词", "params": params, "ref_ids": ref_ids}, ensure_ascii=False),
    }


def _real_png(w, h):
    """生成真实 PNG 图像数据"""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 90, 60)).save(buf, format="PNG")
    return buf.getvalue()


def test_pairing_resolution(client, new_project, new_shot, mock_ffprobe, h3_spec):
    """G3：配对音轨解析——refs 中配对音频带 paired_video，独立音频为 None。"""
    sid = new_shot[1]

    vid = _upload(client, sid, "clip.mp4", "video/mp4", b"fake")
    paid = _upload(client, sid, "track.wav", "audio/wav", b"fake", paired_with=vid)
    aid = _upload(client, sid, "standalone.wav", "audio/wav", b"fake")

    params = _build_params(_task_row(sid, "ref", [vid, paid, aid], {"duration": 8, "aspect": "16:9"}))

    by_id = {r["id"]: r for r in params["refs"]}
    assert params["task_type"] == "ref2va"
    assert by_id[paid]["paired_video"] == vid, "配对音频应解析出 paired_video"
    assert by_id[aid]["paired_video"] is None, "独立音频不应有配对"
    assert by_id[vid]["kind"] == "video"

    # 分组结果含 ref_video_audios（成对）
    grouped = h3_spec.group_refs(params["refs"])
    assert len(grouped["ref_video_audios"]) == 1
    assert grouped["ref_video_audios"][0]["video"] == by_id[vid]["path"]
    assert grouped["ref_video_audios"][0]["audio"] == by_id[paid]["path"]


def test_follow_first_frame_size(client, new_project, new_shot, real_png_image):
    """G7：首帧 1080×1920（竖图）→ 768×1344（短边 768，多倍数 2 对齐，1344 封顶）。"""
    sid = new_shot[1]

    iid = _upload(client, sid, "portrait.png", "image/png", _real_png(1080, 1920))

    # 默认（不跟随）：按比例 16:9 计算 → 1344×768
    base = _build_params(_task_row(sid, "first_frame", [iid], {"duration": 8, "aspect": "16:9"}))
    assert (base["width"], base["height"]) == (1344, 768)

    # 跟随首帧：竖图 → 768×1344
    follow = _build_params(_task_row(sid, "first_frame", [iid], {"duration": 8, "aspect": "16:9", "size_mode": "follow_first"}))
    assert (follow["width"], follow["height"]) == (768, 1344), (follow["width"], follow["height"])
    assert follow["first_image"] is not None


def test_seed_and_sampling_passthrough(client, new_project, new_shot):
    """G2/G5：种子、采样覆盖、ref_image_size 请求级透传。"""
    sid = new_shot[1]

    params = _build_params(_task_row(sid, "text", [], {
        "duration": 8, "aspect": "16:9",
        "seed": 42, "sampler": "euler", "steps": 25, "denoise": 0.9, "ref_image_size": "max",
    }))
    assert params["task_type"] == "t2va"
    assert params["seed"] == 42
    assert params["sampler_name"] == "euler"
    assert params["steps"] == 25
    assert params["denoise"] == 0.9
    assert params["ref_image_size"] == "max"


def test_seed_fallback_is_deterministic():
    """AI/ML 评估 P2 · 可复现性：payload 无 seed 时由任务 ID 确定性派生。

    旧实现为 time-based（同任务重跑 seed 漂移）；改为任务 ID 哈希派生后，
    同任务断点续跑 / 重放复用同一 seed。显式 seed 仍优先。
    """
    base = {
        "id": "task_a",
        "shot_id": "s",
        "mode": "text",
        "payload": json.dumps({"prompt": "p", "params": {"duration": 8, "aspect": "16:9"}, "ref_ids": []}),
    }
    p1 = _build_params(dict(base))
    p2 = _build_params(dict(base))
    assert p1["seed"] == p2["seed"], "同任务 ID 重跑应得到同一 seed（确定性兜底）"
    assert isinstance(p1["seed"], int) and 0 <= p1["seed"] < 2**32

    # 不同任务 ID → 不同 seed（来源区分）
    other = dict(base)
    other["id"] = "task_b"
    assert _build_params(other)["seed"] != p1["seed"], "不同任务 ID 应得到不同 seed"

    # 显式 seed 优先于派生
    explicit = dict(base)
    explicit["payload"] = json.dumps(
        {"prompt": "p", "params": {"duration": 8, "aspect": "16:9", "seed": 99}, "ref_ids": []}
    )
    assert _build_params(explicit)["seed"] == 99


def test_model_missing_preflight(tmp_path, monkeypatch):
    """模型缺失预检：无权重 → 不可用；缺失报错必须给出可操作指引（MMH3_MODEL_PATH / HF_HUB_OFFLINE）。"""
    from routers import inference as inf

    # 空 MODEL_PATH + HF 缓存无该 repo → 不可用（离线/联网都只读本地缓存）
    monkeypatch.setattr(inf.settings, "MODEL_PATH", "")
    monkeypatch.setattr("huggingface_hub.scan_cache_dir", lambda: SimpleNamespace(repos=[]))
    assert inf._model_available_locally("MiniMaxAI/MiniMax-H3") is False

    # 本地目录缺 model_index.json → 不可用；补上后 → 可用
    monkeypatch.setattr(inf.settings, "MODEL_PATH", str(tmp_path))
    assert inf._model_available_locally(str(tmp_path)) is False
    (tmp_path / "model_index.json").write_text("{}")
    assert inf._model_available_locally(str(tmp_path)) is True

    # 缺失报错应包含可操作指引（HF id 分支：含 HF_HUB_OFFLINE 与 MMH3_MODEL_PATH）
    monkeypatch.setattr(inf.settings, "MODEL_PATH", "")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    err = str(inf._model_missing_error("MiniMaxAI/MiniMax-H3"))
    assert "MMH3_MODEL_PATH" in err and "HF_HUB_OFFLINE" in err

    # 本地路径缺失时报错同样给出 MMH3_MODEL_PATH 指引
    monkeypatch.setattr(inf.settings, "MODEL_PATH", str(tmp_path))
    err_local = str(inf._model_missing_error(str(tmp_path)))
    assert "MMH3_MODEL_PATH" in err_local
