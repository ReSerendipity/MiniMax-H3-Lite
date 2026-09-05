"""inference.py 失败路径补测（测试体系评估报告 2026-09-05 · P2-④）。

覆盖 `_run_diffusers`（inference.py:252-346）此前 0 覆盖的失败编排：
  1. diffusers/torch 依赖缺失 → RuntimeError（安装指引）
  2. 模型权重缺失 → RuntimeError（可操作下载指引，非底层 traceback）
  3. ModularPipeline 拒绝入参 → 别名重试耗尽 → RuntimeError（原错误+签名）
  4. 推理产出空文件/未产出 → RuntimeError（绝不假成功）
以及队列终态失败编排（queue_manager._run_task）：mock run_inference 抛异常 →
任务与镜头状态置 failed 而非永久 processing（评估报告 Q3 场景）。

所有 fake 模块/桩均不触发真实权重加载。
"""
import sys
import types

import pytest

from routers import inference as top_inf  # 顶层形态（queue_manager 实际引用）
from backend.routers import queue_manager


# ── 辅助：伪造 diffusers / torch 模块 ──────────────────────────

def _install_fake_diffusers(monkeypatch, pipe):
    """注入 fake diffusers.ModularPipeline 与 torch，避免真实导入。"""
    fake_diffusers = types.ModuleType("diffusers")
    fake_diffusers.ModularPipeline = type(
        "ModularPipeline", (), {"from_pretrained": classmethod(lambda cls, *a, **k: pipe)}
    )
    fake_torch = types.ModuleType("torch")
    fake_torch.bfloat16 = "fake-bfloat16"
    monkeypatch.setitem(sys.modules, "diffusers", fake_diffusers)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)


def _minimal_params():
    return {
        "task_type": "t2va",
        "mode": "text",
        "prompt": "测试",
        "width": 1344,
        "height": 768,
        "num_frames": 137,
        "fps": 24,
        "audio_sample_rate": 32000,
    }


# ── _run_diffusers 失败路径 ────────────────────────────────────

def test_diffusers_import_error_gives_actionable_message(monkeypatch):
    """依赖缺失 → RuntimeError 带安装指引，绝不假成功。"""
    monkeypatch.setitem(sys.modules, "diffusers", None)
    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.raises(RuntimeError, match="依赖缺失"):
        top_inf._run_diffusers(_minimal_params())


def test_model_missing_gives_download_guidance(monkeypatch, tmp_path):
    """本地权重目录缺失 → RuntimeError 带下载指引（MODEL_PATH 分支）。"""
    _install_fake_diffusers(monkeypatch, pipe=None)  # 导入成功但不应走到加载
    import config as top_config
    monkeypatch.setattr(top_config.settings, "MODEL_PATH", str(tmp_path / "missing_model"))
    with pytest.raises(RuntimeError, match="MMH3_MODEL_PATH|本地权重目录缺失"):
        top_inf._run_diffusers(_minimal_params())


def test_pipeline_typeerror_alias_retry_exhausted(monkeypatch):
    """ModularPipeline 持续 TypeError → 别名重试耗尽 → RuntimeError 含原始错误与签名。"""

    class AlwaysTypeErrorPipe:
        def enable_model_cpu_offload(self):
            pass

        def __call__(self, **kwargs):
            raise TypeError("unexpected keyword argument 'prompt'")

    _install_fake_diffusers(monkeypatch, AlwaysTypeErrorPipe())
    import config as top_config
    monkeypatch.setattr(top_config.settings, "MODEL_PATH", "")
    monkeypatch.setattr(top_inf, "_model_available_locally", lambda model_id: True)
    with pytest.raises(RuntimeError, match="ModularPipeline 拒绝入参"):
        top_inf._run_diffusers(_minimal_params())


def test_empty_output_file_rejected(monkeypatch, tmp_path):
    """推理产出空文件/未产出 → RuntimeError，绝不假成功。"""

    class FakeOutput:
        def save(self, path):
            pass  # 什么都不写 → tmp 文件不存在

    class FakePipe:
        def enable_model_cpu_offload(self):
            pass

        def __call__(self, **kwargs):
            return FakeOutput()

    _install_fake_diffusers(monkeypatch, FakePipe())
    import config as top_config
    monkeypatch.setattr(top_config.settings, "MODEL_PATH", "")
    monkeypatch.setattr(top_config.settings, "ASSETS_DIR", tmp_path)
    monkeypatch.setattr(top_inf, "_model_available_locally", lambda model_id: True)
    with pytest.raises(RuntimeError, match="未产出有效视频文件"):
        top_inf._run_diffusers(_minimal_params())


def test_safe_signature_never_raises():
    """_safe_signature 对任意对象返回字符串，不抛异常。"""
    sig = top_inf._safe_signature(lambda **k: None)
    assert isinstance(sig, str) and sig


# ── 队列终态失败编排（报告 Q3：异常 → failed 而非永久 processing） ──

def test_queue_marks_task_failed_when_inference_raises(client, new_shot, monkeypatch):
    """run_inference 抛异常 → 任务 status=failed + error 落库 + 镜头 failed。"""
    pid, sid = new_shot

    def boom(task_id):
        raise RuntimeError("E2E-FAILURE-MARKER")

    # 双形态模块双 patch（GOTCHAS #23 / conftest mock_inference 同款）：
    # worker 线程走顶层 routers.queue_manager，backend.* 是同文件的另一模块对象。
    import routers.queue_manager as top_qm
    monkeypatch.setattr(top_qm, "run_inference", boom)
    monkeypatch.setattr(queue_manager, "run_inference", boom)
    # 重试次数归零：同一 Settings 实例的两个模块形态都改，避免多跑重试
    import config as top_config
    from backend import config as backend_config
    monkeypatch.setattr(top_config.settings, "TASK_RETRY_MAX", 0)
    monkeypatch.setattr(backend_config.settings, "TASK_RETRY_MAX", 0)

    r = client.post("/api/generations", json={
        "shot_id": sid, "mode": "text", "prompt": "失败路径测试",
        "params": {"duration": 8, "aspect": "16:9"},
        "ref_ids": [],
    })
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    final = None
    for _ in range(50):
        t = client.get(f"/api/generations/{tid}").json()
        if t["status"] in ("completed", "failed"):
            final = t
            break
        import time
        time.sleep(0.2)

    assert final is not None, "任务未在超时内进入终态"
    assert final["status"] == "failed", f"任务应置失败：{final}"
    assert "E2E-FAILURE-MARKER" in (final.get("error") or "")

    shots = client.get(f"/api/projects/{pid}/shots").json()
    assert shots[0]["status"] == "failed", "镜头状态应同步置 failed"
