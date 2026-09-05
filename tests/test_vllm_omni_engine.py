"""vllm_omni_engine 适配器补测（测试体系评估报告 2026-09-05 · P3-⑦）。

此前 0% 覆盖（ADR-0003 Proposed，未弃用 → 纳入补测范围）。覆盖 `run()` 全分支：
  * httpx 依赖缺失 → RuntimeError（安装指引）
  * 非 200 响应 → RuntimeError（含状态码与响应片段）
  * JSON 响应含 url → 二次下载落盘
  * JSON 响应无 url → RuntimeError（绝不假成功）
  * video/mp4 直出字节流 → 直接落盘
  * 连接异常 → RuntimeError + 临时文件清理
  * 空产出（0 字节）→ RuntimeError
全部以 fake httpx 模块桩替换，不发起真实网络请求。
"""
import sys
import types
from pathlib import Path

import pytest

from routers import vllm_omni_engine as ve


# ── fake httpx 基建 ──────────────────────────────────────────

class _FakeResp:
    """最小响应桩：status_code / headers / json() / content。"""

    def __init__(self, status_code=200, json_data=None, content=b"", ctype="video/mp4"):
        self.status_code = status_code
        self._json = json_data
        self.content = content
        self.headers = {"content-type": ctype}

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def _install_fake_httpx(monkeypatch, post_resp, get_resp=None, post_exc=None):
    """注入 fake httpx 模块：Client.post 返回 post_resp（或抛 post_exc），
    第二个 Client（下载用）的 .get 返回 get_resp。记录调用以供断言。"""
    calls = {"post_url": None, "post_payload": None, "get_url": None}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None):
            calls["post_url"] = url
            calls["post_payload"] = json
            if post_exc is not None:
                raise post_exc
            return post_resp

        def get(self, url):
            calls["get_url"] = url
            return get_resp

    fake = types.ModuleType("httpx")
    fake.Client = _FakeClient
    monkeypatch.setitem(sys.modules, "httpx", fake)
    return calls


@pytest.fixture
def assets_dir(tmp_path, monkeypatch):
    """双形态 patch ASSETS_DIR → tmp_path（vllm 模块读顶层 config.settings）。"""
    import config as top_config
    from backend import config as backend_config
    monkeypatch.setattr(top_config.settings, "ASSETS_DIR", tmp_path)
    monkeypatch.setattr(backend_config.settings, "ASSETS_DIR", tmp_path)
    return tmp_path


def _params(**over):
    base = {
        "task_type": "t2va",
        "prompt": "测试提示词",
        "width": 1344,
        "height": 768,
        "num_frames": 96,
        "fps": 24,
    }
    base.update(over)
    return base


# ── run() 分支 ───────────────────────────────────────────────

def test_httpx_missing_gives_install_hint(monkeypatch, assets_dir):
    """httpx 缺失 → RuntimeError 带安装指引。"""
    monkeypatch.setitem(sys.modules, "httpx", None)
    with pytest.raises(RuntimeError, match="pip install httpx"):
        ve.run(_params())


def test_non_200_rejected(monkeypatch, assets_dir):
    """非 200 响应 → RuntimeError 含状态码。"""
    _install_fake_httpx(monkeypatch, post_resp=_FakeResp(status_code=503, content=b"oops", ctype="text/plain"))
    with pytest.raises(RuntimeError, match="非 200.*503"):
        ve.run(_params())


def test_json_response_downloads_video(monkeypatch, assets_dir):
    """JSON 响应含 url → 二次 GET 下载字节落盘。"""
    calls = _install_fake_httpx(
        monkeypatch,
        post_resp=_FakeResp(json_data={"url": "http://vllm/asset/abc.mp4"}, ctype="application/json"),
        get_resp=_FakeResp(content=b"fake-vllm-video"),
    )
    out = ve.run(_params())
    assert calls["get_url"] == "http://vllm/asset/abc.mp4"
    assert calls["post_url"].endswith("/v1/videos")
    written = Path(out)
    assert written.exists() and written.stat().st_size == len(b"fake-vllm-video")


def test_json_payload_duration_mapping(monkeypatch, assets_dir):
    """payload 映射：duration = num_frames / fps = 96/24 = 4.0，任务类型透传。"""
    calls = _install_fake_httpx(
        monkeypatch,
        post_resp=_FakeResp(content=b"v"),
    )
    ve.run(_params())
    payload = calls["post_payload"]
    assert payload["duration"] == 4.0
    assert payload["task_type"] == "t2va"
    assert payload["prompt"] == "测试提示词"
    assert payload["width"] == 1344 and payload["height"] == 768


def test_json_without_url_rejected(monkeypatch, assets_dir):
    """JSON 响应缺 video url → RuntimeError，绝不假成功。"""
    _install_fake_httpx(
        monkeypatch,
        post_resp=_FakeResp(json_data={"unexpected": 1}, ctype="application/json"),
    )
    with pytest.raises(RuntimeError, match="无 video url"):
        ve.run(_params())


def test_binary_content_written_directly(monkeypatch, assets_dir):
    """video/mp4 字节流直出 → 直接落盘。"""
    _install_fake_httpx(monkeypatch, post_resp=_FakeResp(content=b"binary-video-bytes"))
    out = ve.run(_params())
    assert Path(out).read_bytes() == b"binary-video-bytes"


def test_connection_error_wrapped_and_tmp_cleaned(monkeypatch, assets_dir):
    """网络异常 → RuntimeError 包装 + 临时产物清理。"""
    _install_fake_httpx(monkeypatch, post_resp=None, post_exc=ConnectionError("refused"))
    with pytest.raises(RuntimeError, match="vllm-omni 推理失败"):
        ve.run(_params())
    leftovers = list(assets_dir.glob("tmp_*.mp4"))
    assert leftovers == [], f"临时文件应被清理：{leftovers}"


def test_empty_output_rejected(monkeypatch, assets_dir):
    """产出 0 字节 → RuntimeError，绝不假成功。"""
    _install_fake_httpx(monkeypatch, post_resp=_FakeResp(content=b""))
    with pytest.raises(RuntimeError, match="未产出有效视频文件"):
        ve.run(_params())


def test_download_non_200_rejected(monkeypatch, assets_dir):
    """JSON url 二次下载返回非 200 → RuntimeError（下载失败分支）。"""
    _install_fake_httpx(
        monkeypatch,
        post_resp=_FakeResp(json_data={"url": "http://vllm/x.mp4"}, ctype="application/json"),
        get_resp=_FakeResp(status_code=404, content=b"gone", ctype="text/plain"),
    )
    with pytest.raises(RuntimeError, match="下载 vllm-omni 视频失败.*404"):
        ve.run(_params())


def test_write_failure_cleans_tmp_file(monkeypatch, assets_dir):
    """落盘写失败 → RuntimeError 包装，且已创建的临时文件被清理（except 分支 unlink）。"""

    def boom_write(self, data):
        self.touch()  # 先创建文件，模拟写一半失败
        raise IOError("disk full")

    _install_fake_httpx(monkeypatch, post_resp=_FakeResp(content=b"partial"))
    monkeypatch.setattr(Path, "write_bytes", boom_write)
    with pytest.raises(RuntimeError, match="vllm-omni 推理失败"):
        ve.run(_params())
    assert list(assets_dir.glob("tmp_*.mp4")) == [], "临时文件应被清理"


def test_refs_and_frame_images_mapped_into_payload(monkeypatch, assets_dir):
    """refs 分组（image/video/audio）+ first/last_image 均进入请求 payload。"""
    calls = _install_fake_httpx(
        monkeypatch,
        post_resp=_FakeResp(content=b"v"),
    )
    params = _params(
        refs=[
            {"kind": "image", "path": "/a.png"},
            {"kind": "video", "path": "/b.mp4"},
            {"kind": "audio", "path": "/c.wav"},
            {"kind": "image", "path": "/d.png"},  # 第二张图也应收进 reference_images
        ],
        first_image="/first.png",
        last_image="/last.png",
    )
    out = ve.run(params)
    payload = calls["post_payload"]
    assert payload["reference_images"] == ["/a.png", "/d.png"]
    assert payload["reference_videos"] == ["/b.mp4"]
    assert payload["reference_audios"] == ["/c.wav"]
    assert payload["first_image"] == "/first.png"
    assert payload["last_image"] == "/last.png"
    assert Path(out).exists()
