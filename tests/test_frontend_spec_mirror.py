"""前端规格镜像护栏：tests/frontend/spec_expected.json ≡ backend/h3/spec.py

为什么需要它：`assets/js/shared.js` 出于历史原因自带一份官方规格实现
（framesForDuration / dimsForResolution / H3_RES_* 表），与 Python 规格层
`backend/h3/spec.py` 是**平行两份**，不共享代码。前端冒烟
（`tests/frontend/smoke.js` 的 [spec mirror] 段）读的就是这份夹具，逐档比对
页面读数；夹具本身若与 spec.py 漂移，前端测试会「跟着一起绿」。本文件把夹具
钉回唯一事实源，规格层一改而夹具没跟着重生成，这里先红。

重生成夹具（改了 spec.py 之后必须重跑，然后跑本测试确认全绿）：

    python - <<'PY'
    import sys, json
    sys.path.insert(0, "backend")
    from h3 import spec as h
    out = {
      "_generated_from": "backend/h3/spec.py —— 勿手改；重生成命令见 tests/test_frontend_spec_mirror.py 的 docstring",
      "duration_min": h.DURATION_MIN, "duration_max": h.DURATION_MAX,
      "frames": {str(d): h.frames_for_duration(d) for d in range(int(h.DURATION_MIN), int(h.DURATION_MAX) + 1)},
      "dims": {p: {a: "%dx%d" % h.dims_for_resolution(p, a) for a in sorted(h.RATIOS)} for p in h.RESOLUTION_PRESETS},
      "ratios": sorted(h.RATIOS), "presets": sorted(h.RESOLUTION_PRESETS),
    }
    open("tests/frontend/spec_expected.json", "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    PY

同一文件还顺手钉住三处「同源同值」常数（提示词上限）：backend/config.py 的
Settings 字段、shared.js 里的 JS 常量、三页模板的 textarea maxlength。
它们一旦分叉，用户会看到「前端没标红、后端却 422」的错位（2026-09-23 #64 修过一次）。
"""
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from h3 import spec as h3  # noqa: E402  官方规格层（单一事实源）

FIXTURE = PROJECT_ROOT / "tests" / "frontend" / "spec_expected.json"
SHARED_JS = PROJECT_ROOT / "assets" / "js" / "shared.js"
SMOKE_JS = PROJECT_ROOT / "tests" / "frontend" / "smoke.js"
PAGES = ("t2v", "i2v", "r2v")


def _fixture() -> dict:
    assert FIXTURE.exists(), f"缺少夹具文件：{FIXTURE}"
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── 夹具完整性：档位/比例/时长三张轴都不能少一档 ──────────────
def test_fixture_axes_are_complete():
    fx = _fixture()
    assert sorted(fx["presets"]) == sorted(h3.RESOLUTION_PRESETS), "夹具分辨率档位集合与 spec.py 不符"
    assert sorted(fx["ratios"]) == sorted(h3.RATIOS), "夹具宽高比集合与 spec.py 不符"
    want_days = [str(d) for d in range(int(h3.DURATION_MIN), int(h3.DURATION_MAX) + 1)]
    assert sorted(fx["frames"], key=int) == sorted(want_days, key=int), "夹具时长覆盖 4–15s 全档"
    for p in fx["presets"]:
        assert sorted(fx["dims"][p]) == sorted(h3.RATIOS), f"{p} 档缺比例"


def test_frames_table_matches_spec():
    fx = _fixture()
    bad = {d: (fx["frames"][d], h3.frames_for_duration(d))
           for d in fx["frames"] if fx["frames"][d] != h3.frames_for_duration(int(d))}
    assert not bad, f"帧数漂移（前端值, spec.py 值）：{bad}"


def test_dims_table_matches_spec():
    fx = _fixture()
    bad = {}
    for p, row in fx["dims"].items():
        for a, want in row.items():
            got = "%dx%d" % h3.dims_for_resolution(p, a)
            if got != want:
                bad[f"{p}/{a}"] = (want, got)
    assert not bad, f"像素换算漂移（夹具值, spec.py 值）：{bad}"


# ── 夹具不是孤儿：前端冒烟确实读它，且逐档比对 ──────────────
def test_smoke_js_consumes_the_fixture():
    src = SMOKE_JS.read_text(encoding="utf-8")
    assert "spec_expected.json" in src, "smoke.js 不再读取规格夹具（护栏失效）"
    assert "SPEC_EXPECT.dims" in src and "SPEC_EXPECT.frames" in src, "smoke.js 未逐档比对帧数与像素"
    assert "[spec mirror]" in src, "smoke.js 缺少 [spec mirror] 段"


# ── JS 侧平行实现的关键常数仍需手工同步，故机器核对 ──────────────
def test_js_spec_tables_mirror_python():
    src = SHARED_JS.read_text(encoding="utf-8")
    js_presets = re.search(r"var H3_RES_PRESETS=\[([^\]]*)\];", src)
    assert js_presets, "shared.js 的 H3_RES_PRESETS 定义形式变了，请同步本测试"
    listed = [s.strip().strip("'\"") for s in js_presets.group(1).split(",") if s.strip()]
    assert sorted(listed) == sorted(h3.RESOLUTION_PRESETS), f"JS 档位表 {listed} ≠ spec.py"

    js_short = re.search(r"var H3_RES_SHORT=\{([^}]*)\};", src)
    assert js_short, "shared.js 的 H3_RES_SHORT 定义形式变了"
    pairs = dict(re.findall(r"'([^']+)':(\d+)", js_short.group(1)))
    assert {k: int(v) for k, v in pairs.items()} == h3.RESOLUTION_SHORT_SIDE, "JS 短边表与 spec.py 不符"

    js_default = re.search(r"var H3_RES_DEFAULT='([^']+)'", src)
    assert js_default and js_default.group(1) == h3.RESOLUTION_DEFAULT, "JS 默认档位与 spec.py 不符"

    js_block = re.search(r"function framesForDuration\(d\)\{[^}]*\}", src)
    assert js_block and re.search(r"24", js_block.group(0)) and "17" in js_block.group(0), \
        "JS 帧长公式不再含 24fps / 17k+5 网格参数"


def test_prompt_char_limit_single_sourced():
    """上限三处载体必须同值：Settings → shared.js 常量 → 模板 maxlength"""
    from config import settings

    limit = int(settings.MAX_PROMPT_CHARS)
    src = SHARED_JS.read_text(encoding="utf-8")
    js = re.search(r"var MAX_PROMPT_CHARS=(\d+);", src)
    assert js, "shared.js 的 MAX_PROMPT_CHARS 定义形式变了，请同步本测试"
    assert int(js.group(1)) == limit, f"JS 上限 {js.group(1)} ≠ Settings {limit}"

    for page in PAGES:
        html = (PROJECT_ROOT / "backend" / "templates" / f"{page}.html").read_text(encoding="utf-8")
        ml = re.search(r'id="promptInput"[^>]*maxlength="(\d+)"', html)
        assert ml, f"{page}.html 的 #promptInput 缺 maxlength"
        assert int(ml.group(1)) == limit, f"{page} maxlength {ml.group(1)} ≠ Settings {limit}"
