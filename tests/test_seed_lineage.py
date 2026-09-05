"""seed 血缘机制补测（MLOps 评估 2026-09-05 · P1 可复现性血缘断点）。

覆盖：
  * 提交时未带 seed → 服务端生成随机 uint32 seed 并写入 payload.params.seed 落库
  * 提交时显式 seed → 校验后原样落库（重试/续跑/重放复用同一 seed）
  * seed 非法（非整数 / 越界）→ 422，不产生任务
  * run_inference 成功后 seed 回写任务 payload + assets.meta
  * _run_diffusers 消费 seed 构造 torch.Generator；pipeline 不接受 generator 时优雅回退
所有引擎均以桩替换，不触发真实权重加载。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from routers import inference as top_inf


# ── 提交层：seed 生成 / 透传 / 校验 ──────────────────────────

def _submit(client, sid, params):
    return client.post("/api/generations", json={
        "shot_id": sid, "mode": "text", "prompt": "seed 血缘测试",
        "params": params,
    })


def _as_dict(v):
    """API 层 payload 经 row_to_dict 已反序列化为 dict；兼容 str 形态。"""
    return v if isinstance(v, dict) else json.loads(v)


def test_submit_without_seed_generates_and_persists(client, new_shot, mock_inference):
    """未指定 seed → 服务端生成 uint32 随机 seed 并落进 payload。"""
    _, sid = new_shot
    r = _submit(client, sid, {"duration": 5, "aspect": "16:9"})
    assert r.status_code == 200, r.text
    payload = _as_dict(r.json()["payload"])
    seed = payload["params"]["seed"]
    assert isinstance(seed, int) and 0 <= seed < 2**32, f"seed 应为 uint32：{seed}"


def test_submit_with_explicit_seed_passthrough(client, new_shot, mock_inference):
    """显式 seed=42 → 原样落库，重试/重放可复用。"""
    _, sid = new_shot
    r = _submit(client, sid, {"duration": 5, "aspect": "16:9", "seed": 42})
    assert r.status_code == 200, r.text
    payload = _as_dict(r.json()["payload"])
    assert payload["params"]["seed"] == 42


def test_submit_seed_range_validation(client, new_shot):
    """seed 越界（负数 / ≥2^32）→ 422，不产生任务。"""
    _, sid = new_shot
    for bad in (-1, 2**32):
        r = _submit(client, sid, {"duration": 5, "aspect": "16:9", "seed": bad})
        assert r.status_code == 422, f"seed={bad} 应被拒绝：{r.text}"


def test_submit_seed_non_integer_rejected(client, new_shot):
    """seed 非整数 → 422。"""
    _, sid = new_shot
    r = _submit(client, sid, {"duration": 5, "aspect": "16:9", "seed": "abc"})
    assert r.status_code == 422, r.text


# ── 执行层：seed 回写 + Generator 消费 ────────────────────────

@pytest.fixture
def inference_env(monkeypatch, temp_db_path, tmp_path):
    """双形态 patch settings（ASSETS_DIR → tmp_path）。"""
    import config as top_config
    from backend import config as backend_config
    monkeypatch.setattr(top_config.settings, "ASSETS_DIR", tmp_path)
    monkeypatch.setattr(backend_config.settings, "ASSETS_DIR", tmp_path)
    return tmp_path


def _seed_task(shot_id="shot_seed", task_id="task_seed", params=None):
    """temp DB 里插入最小任务行（payload.params 可携带 seed）。"""
    import database
    conn = database.get_db()
    conn.execute("INSERT OR IGNORE INTO projects (id, name) VALUES ('proj_seed', 'seed 项目')")
    conn.execute(
        "INSERT OR IGNORE INTO shots (id, project_id, name, prompt) VALUES (?, 'proj_seed', 'seed 镜头', 'p')",
        (shot_id,),
    )
    payload = json.dumps({"prompt": "seed 回写测试", "params": params or {}, "ref_ids": []}, ensure_ascii=False)
    conn.execute(
        "INSERT OR REPLACE INTO generation_tasks (id, shot_id, mode, payload, status) "
        "VALUES (?, ?, 'text', ?, 'pending')",
        (task_id, shot_id, payload),
    )
    conn.commit()
    conn.close()


def _make_fake_diffusers(monkeypatch, captured, *, reject_generator=False):
    """伪造 diffusers.ModularPipeline：记录入参、产出可 save 的假输出。"""

    class FakePipe:
        def enable_model_cpu_offload(self):
            captured["offloaded"] = True

        def __call__(self, **kwargs):
            if reject_generator and "generator" in kwargs:
                raise TypeError("unexpected keyword argument 'generator'")
            captured["kwargs"] = kwargs
            return SimpleNamespace(save=lambda p: Path(p).write_bytes(b"fake-video"))

    fake_mod = SimpleNamespace(
        ModularPipeline=SimpleNamespace(from_pretrained=lambda *a, **k: FakePipe())
    )
    monkeypatch.setitem(sys.modules, "diffusers", fake_mod)
    monkeypatch.setattr(top_inf, "_model_available_locally", lambda source: True)
    monkeypatch.setattr(top_inf, "active_backend", lambda: "diffusers")


def test_run_inference_writes_seed_back(inference_env, monkeypatch):
    """推理成功后：生效 seed 回写任务 payload.params.seed，并记入 assets.meta。"""
    _seed_task(params={"seed": 7})
    tmp_path = inference_env
    src = tmp_path / "out_seed.mp4"
    src.write_bytes(b"fake-video")
    captured = {}
    _make_fake_diffusers(monkeypatch, captured)

    top_inf.run_inference("task_seed")

    import database
    conn = database.get_db()
    pl = _as_dict(conn.execute(
        "SELECT payload FROM generation_tasks WHERE id='task_seed'"
    ).fetchone()["payload"])
    assert pl["params"]["seed"] == 7, "生效 seed 应回写任务 payload"

    # result_asset_id 由 queue_manager 回填（此处绕过队列），按插入序取最新 result 资产
    meta = _as_dict(conn.execute(
        "SELECT meta FROM assets WHERE kind='result' ORDER BY created_at DESC, rowid DESC LIMIT 1"
    ).fetchone()["meta"])
    assert meta["seed"] == 7, "资产 meta 应记录 seed"
    conn.close()


def test_diffusers_consumes_seed_generator(inference_env, monkeypatch):
    """diffusers 路径：params.seed=42 → generator.manual_seed 为 42 并传入 pipeline。"""
    import torch
    _seed_task(params={"seed": 42})
    src = inference_env / "out_gen.mp4"
    src.write_bytes(b"fake-video")
    captured = {}
    _make_fake_diffusers(monkeypatch, captured)

    top_inf.run_inference("task_seed")

    gen = captured["kwargs"].get("generator")
    assert gen is not None, "pipeline 入参应包含 generator"
    assert isinstance(gen, torch.Generator)
    assert gen.initial_seed() == 42


def test_diffusers_falls_back_without_generator_support(inference_env, monkeypatch):
    """pipeline 不接受 generator（旧版 diffusers）→ 剔除后重试成功，不阻断推理。"""
    _seed_task(params={"seed": 42})
    src = inference_env / "out_fallback.mp4"
    src.write_bytes(b"fake-video")
    captured = {}
    _make_fake_diffusers(monkeypatch, captured, reject_generator=True)

    result = top_inf.run_inference("task_seed")
    assert result["asset_id"].startswith("ast_")
    assert "generator" not in captured["kwargs"], "回退后不应再传 generator"


def test_legacy_task_without_seed_gets_time_based_seed(inference_env, monkeypatch):
    """存量任务（payload 无 seed）→ _build_params 仍生成 uint32 回退 seed 且回写。"""
    _seed_task(params={})
    src = inference_env / "out_legacy.mp4"
    src.write_bytes(b"fake-video")
    captured = {}
    _make_fake_diffusers(monkeypatch, captured)

    top_inf.run_inference("task_seed")

    import database
    conn = database.get_db()
    pl = _as_dict(conn.execute(
        "SELECT payload FROM generation_tasks WHERE id='task_seed'"
    ).fetchone()["payload"])
    seed = pl["params"]["seed"]
    assert isinstance(seed, int) and 0 <= seed < 2**32
    conn.close()
