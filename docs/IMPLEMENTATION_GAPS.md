# MM·H3 前端能力补齐实施指南（官方工作流全量对齐）

> 依据：`workflows/` 三份官方 ComfyUI 模板（t2v / i2v / r2v）、ModelScope 官方发布页（`MiniMax/MiniMax-H3`）、项目后端实际执行链路（`backend/`）。
> 结论：核心生成闭环已对齐，仍有 **4 项 P1 差距 + 3 项 P2 差距**。本文档按「现状 → 目标 → 改动点 → 代码草案 → 自测」逐项给出实施指引，供开发者在项目内直接落地。
> 基线提交：三模式页（index/i2v/r2v.html）+ `assets/css/shared.css` + `assets/js/shared.js` 已就绪，后端契约以 `backend/h3/spec.py` 为参数真源。

---

## 0. 差距总览

| 编号 | 级别 | 差距 | 涉及层 | 改动量 |
|---|---|---|---|---|
| G1 | P1 | `ref_image_size`（match/max）前端控件未真正生效 | 后端（comfy_workflow + diffusers） | 小 |
| G2 | P1 | 噪声种子（noise_seed）未暴露，无法固定种子复现 | 前端 + 参数透传 | 小 |
| G3 | P1 | 参考视频自带音轨（ref_video_audios）未建模 | 数据库 + API + 前后端 | 中 |
| G4 | P1 | 输入视频/音频片段时长校验缺失（官方 2–15s/段、同类合计 ≤15s） | 后端（uploads）+ 前端提示 | 中 |
| G5 | P2 | 采样参数（sampler/scheduler/steps/denoise）不可按镜头覆盖 | 后端 + 前端（可选） | 中 |
| G6 | P2 | 提示词指南信息不全（`<d>` 对话标签、保留标签、时间锚点、11 语言） | 前端（tag-guide） | 小 |
| G7 | P2 | i2v「按首帧图像尺寸生成」分支未实现（官方 Use Image Size group） | 后端 + 前端（可选） | 中 |

已核实**无需处理**：SaveVideo 输出路径固定（模板即 `video/MiniMax_H3`，后端 `save_prefix` 可配）；ResolutionSelector 的 0.2–2.0MP 细粒度（模型原生画布为 768p 短边、上限 768×1344，按比例+768P 暴露属正确收敛）；2K（Regenerate-2K 未开源）与 Context-IR（未开源）的降级标注正确。

---

## 1. 前置知识：请求→执行链路（改动时对照）

```
前端页面 (MMH3_PAGE 配置)
  └─ assets/js/shared.js  submitGeneration()
       POST /api/shots/{sid}     (PUT: prompt/mode/duration/aspect/params)
       POST /api/generations     {shot_id, mode, prompt, params, ref_ids}
          └─ backend/routers/generations.py   校验（模式×素材、时长、提示词 7000）
          └─ backend/routers/queue_manager.py 入队（状态机）
          └─ backend/routers/inference.py     _build_params()  ← 参数规范化、seed、首/末帧、refs 分组
             ├─ 引擎 diffusers: _run_diffusers(params)
             └─ 引擎 comfyui:   _run_comfyui(params) → backend/comfy_workflow.py build_prompt()
```

关键文件：

- 参数真源：`backend/h3/spec.py`（任务类型、17k+5 帧公式、分辨率公式、模型名、上限常量）
- 规范化层：`backend/routers/inference.py`（`_build_params` / `_run_diffusers` / `_run_comfyui`）
- ComfyUI 生成器：`backend/comfy_workflow.py`（`build_prompt` / `run_comfyui`）
- 上传/校验：`backend/routers/uploads.py`
- 存储：`backend/database.py`（`shot_refs` 表：`shot_id, asset_id, ref_type, ord`）
- 运行时设置：`backend/settings_store.py`（`SETTABLE_KEYS` / `_DEFAULTS`）
- 前端提交：`assets/js/shared.js`（`getActiveParams` / `submitGeneration` / `doUpload`）
- 前端素材展示：`r2v.html`（ref-block）、`i2v.html`（frame-slots）

---

## G1 — ref_image_size 接线（P1）

### 现状
- 前端 `r2v.html` 有 match/max 控件，`shared.js getActiveParams()` 会把 `params.ref_image_size` 放进生成请求。
- 后端 `backend/comfy_workflow.py:168` 使用 `resolve_setting("ref_image_size", settings.REF_IMAGE_SIZE)` —— 读取**全局设置**，忽略请求参数。
- `_run_diffusers` 完全没有消费 ref_image_size。
- **后果**：用户切换 match/max 无效，实际永远走全局默认（`settings.json` 或 `"match"`）。

### 目标
请求级 `params.ref_image_size` 优先生效；diffusers 后端按语义执行。

### 改动点

**1) `backend/routers/inference.py` — `_build_params()` 返回值追加：**

```python
"ref_image_size": params.get("ref_image_size") or resolve_setting("ref_image_size", settings.REF_IMAGE_SIZE),
```

（在文件顶部确认已 import `resolve_setting`；与 seed 同款写法，缺省回退全局。）

**2) `backend/comfy_workflow.py` — 两处：**

```python
# build_prompt 内（node 20）已经是 task["ref_image_size"]，保持；
# run_comfyui 组装 task 时改为「请求级优先」：
"ref_image_size": task.get("ref_image_size") or resolve_setting("ref_image_size", settings.REF_IMAGE_SIZE),
```

**3) `backend/routers/inference.py` — `_run_diffusers`（ref2va 分支）实现语义：**

先确认安装的 diffusers（0.39.0）`ModularPipeline` 是否接受 `ref_image_size` 参数：

```python
import inspect
sig = inspect.signature(pipe.__call__)
print("ref_image_size" in sig.parameters)   # True → 直接透传 inputs["ref_image_size"]
```

- 若支持：`inputs["ref_image_size"] = params.get("ref_image_size")`（按官方 diffusers 文档，可能为 `"match"|"max"` 字符串，实现前查该版本源码确认枚举值）。
- 若不支持（更可能）：在调用前对参考图像做缩放，语义对齐官方模板：
  - `match`：缩放到生成分辨率（更快）；
  - `max`：短边保持 ≤2048（更强身份保真）。
  参考实现（PIL；需在 `requirements.txt` 增加 `pillow`，或改用 ffmpeg scale 滤镜避免新依赖）：

```python
from PIL import Image
def _scale_ref_images(paths, width, height, mode):
    out = []
    for p in paths:
        im = Image.open(p)
        if mode == "match":
            im = im.resize((width, height), Image.LANCZOS)
        else:  # max: 短边 ≤2048，等比缩放
            w, h = im.size
            short = min(w, h)
            if short > 2048:
                k = 2048 / short
                im = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
        dst = p  # 或写入临时目录避免覆盖原资产
        im.convert("RGB").save(dst)
        out.append(dst)
    return out
```

**4) 前端**：无需改动（已在发送）。仅确认 `r2v.html` 提交路径（`shared.js getActiveParams` 的 `p.ref_image_size` 分支）未被后续重构破坏。

### 自测
1. `data/settings.json` 设 `"ref_image_size": "max"`；UI 选 match 提交 → 抓 `POST /api/generations` 的 `params.ref_image_size` 为 `"match"`；ComfyUI 后端生成的 prompt 中 node 20 `inputs.ref_image_size` 应为 `"match"`（diffusers 后端则按 match 缩放）。
2. 反向（设置 match、UI 选 max）应得 `"max"`，证明请求级优先。

---

## G2 — 噪声种子输入（P1）

### 现状
- 官方模板 `RandomNoise` 有 `noise_seed` widget（默认 randomize）。
- 后端 `_build_params` 已有 `"seed": params.get("seed") or int(time.time()*1000) % (2**32)` —— **后端已支持**，diffusers 与 comfy_workflow 均消费 `task["seed"]`。
- 前端三个模式页均无种子控件，等于每次随机（与模板 randomize 一致），但**无法固定种子复现**。

### 目标
三页参数栏增加「种子」行：输入框（留空 = 随机），附带「随机」小按钮一键重新随机；数值随镜头参数持久化。

### 改动点

**1) 三页 HTML**（index/i2v/r2v.html 右侧参数栏，放在「时长」行之后）：

```html
<div class="p-row"><span class="k">种子</span>
  <span class="v">
    <input type="text" id="seedInput" class="seed-in" inputmode="numeric" placeholder="留空=随机" title="固定噪声种子，留空则每次随机">
    <button class="seg" id="seedRand" type="button" title="生成随机种子">随机</button>
  </span>
</div>
```

（`.seed-in` 样式在 `shared.css` 已存在；`.seg` 按钮沿用参数 chip 观感。）

**2) `assets/js/shared.js`：**

- `getActiveParams()` 追加：

```js
var si = $('seedInput');
if (si && si.value.trim() !== '') {
  var seed = parseInt(si.value.trim(), 10);
  if (!isNaN(seed)) p.seed = seed;
}
```

- `readbackParams()` 追加回填（放在 resPx 更新附近）：

```js
var si = $('seedInput');
if (si) si.value = (params.seed != null) ? String(params.seed) : '';
```

- 绑定随机按钮（init 区）：

```js
var sr = $('seedRand');
if (sr) sr.addEventListener('click', function () {
  var si = $('seedInput');
  if (si) si.value = String(Math.floor(Math.random() * 2 ** 32));
});
```

- 注意：`readbackParams` 里 `.p-row` 回填循环会遍历到「种子」行——该行没有 `.seg.on` 语义，确认循环用 `opts = r.querySelectorAll('.seg:not(.disabled)')` 时不会误清空输入框（输入框不是 `.seg`，天然跳过；若担心，可在循环里 `if (k === '种子') return;`）。

### 自测
- 填固定种子（如 `168866841893410`）→ 提交 → 后端任务 payload 含 seed；同参数同种子连跑两次，若引擎确定则结果帧一致（diffusers 在相同硬件/权重下应可复现）。
- 留空 → payload 无 seed 字段，后端时间随机。

---

## G3 — 参考视频自带音轨 ref_video_audios（P1）

### 现状
- 官方 `MiniMaxH3ReferenceToVideo` 节点输入含 `ref_videos.ref_video_i` 与 `ref_video_audios.ref_video_audio_i`（**下标对齐 = 视频 i 的同步音轨**，官方注释：每个参考视频可携带自己的配声音轨），另有独立 `ref_audios`（≤3）。
- 本项目：`spec.py group_refs` 只分 image/video/audio；`comfy_workflow.py` 只生成 `ref_videos`/`ref_audios`，无 `ref_video_audios`；前端上传时音频一律为独立音频。
- 发布页示例明确：`<Audio 1>` 可以是 `<Video 1>` 的同步音轨（"the synchronized audio track of <Video 1>, providing the background music"，且可用 `partially_copy` 复用）。

### 目标
支持「参考视频 + 其同步音轨」成对建模：上传时可指定某音频为某视频的音轨；生成时按官方节点语义成对输出；独立音频照旧。

### 方案（最小改动、向后兼容）

**1) 数据库 `backend/database.py` — `shot_refs` 增加配对列（幂等迁移）：**

```sql
-- CREATE TABLE IF NOT EXISTS shot_refs 之后追加：
ALTER TABLE shot_refs ADD COLUMN pair_asset_id TEXT;   -- 音频 → 其所属视频资产 id
```

（SQLite 不支持 `ADD COLUMN IF NOT EXISTS`，用 try/except OperationalError 包住，或查询 PRAGMA table_info 判断。建表语句把新列一并写入 CREATE TABLE，保证全新库直接可用。）

**2) 上传 API `backend/routers/uploads.py`：**

- `upload_ref` 增加可选表单字段 `paired_with: str = Form(default="")`：
  - 仅 `kind == "audio"` 允许配对；
  - 校验 `paired_with` 指向的资产存在且 `kind == "video"`，且与本次上传属于同一 shot；
  - 写入 `shot_refs.pair_asset_id`。
- 保持旧调用兼容（不传 paired_with 即独立音频）。

**3) 镜头列表 `backend/routers/shots.py`：**

- `list_shots` 的 refs 查询 `SELECT a.id, a.kind, a.mime, a.meta, r.pair_asset_id ...`，返回项追加 `"paired_video": r["pair_asset_id"]`（audio 才有值）。

**4) 参数真源 `backend/h3/spec.py`：**

- `group_refs(refs)` 追加返回 `ref_video_audios`：

```python
def group_refs(refs: list[dict]) -> dict:
    grouped = {"image": [], "video": [], "audio": []}
    video_by_id = {}
    for r in refs:
        k = r.get("kind")
        if k in grouped:
            grouped[k].append(r["path"])
            if k == "video":
                video_by_id[r["id"]] = r["path"]
    paired = []
    for r in refs:
        if r.get("kind") == "audio" and r.get("paired_video"):
            vid = r["paired_video"]
            if vid in video_by_id:
                paired.append({"video": video_by_id[vid], "audio": r["path"]})
    grouped["ref_video_audios"] = paired
    return grouped
```

**5) ComfyUI 生成器 `backend/comfy_workflow.py`：**

- `build_prompt` ref2va 分支，在 ref_videos 之后按下标对齐补 `ref_video_audios.ref_video_audio_{i}`：

```python
# 先把成对关系按视频顺序对齐到 ref_videos 下标
pair_audio_by_video = {}          # video_path -> audio_path
for p in task.get("ref_video_audios", []):
    pair_audio_by_video[p["video"]] = p["audio"]

for i, name in enumerate(task.get("ref_videos", [])):
    nid = str(50 + i)
    n[nid] = {"class_type": task["load_video_node"], "inputs": {"video": name}}
    ref_inputs[f"ref_videos.ref_video_{i}"] = [nid, 0]
    audio_path = pair_audio_by_video.get(name)
    if audio_path:
        anid = str(55 + i)
        n[anid] = {"class_type": task["load_audio_node"], "inputs": {"audio": audio_path}}
        ref_inputs[f"ref_video_audios.ref_video_audio_{i}"] = [anid, 0]
```

- `run_comfyui` 组装 task：`"ref_video_audios": group_refs(...)["ref_video_audios"]`（在 refs 分组处一并产出；注意 group_refs 输入需含 id/paired_video 字段，当前 `_build_params` 的 refs 只带 id/kind/path，需在 `_build_params` 里补 `paired_video`）。

**6) diffusers `_run_diffusers`：**

- ref2va 分支：

```python
grouped = h3.group_refs(params["refs"])
if grouped["image"]:   inputs["ref_images"] = grouped["image"]
if grouped["video"]:   inputs["ref_videos"] = grouped["video"]
if grouped["audio"]:   inputs["ref_audios"] = grouped["audio"]
if grouped["ref_video_audios"]:
    # 若 ModularPipeline 支持配对音轨参数则透传；否则按顺序拆出独立列表
    inputs["ref_video_audios"] = grouped["ref_video_audios"]   # 查 0.39.0 签名，见 G1 的 inspect 方法
```

**7) 前端 `r2v.html` + `shared.js`：**

- 素材列表（`.rm-item`）为「视频」项追加操作：「＋配同步音轨」→ 打开文件选择（accept=audio/*）→ 上传时在 FormData 加 `paired_with=<该视频 asset id>`（`doUpload` 增加可选 pairedWith 参数，构造 fd 时 `fd.append('paired_with', ...)`）。
- 已配对项显示为 `Video 1 + Audio 1（音轨）` 或独立标签；`renderRefs` 渲染时读取 `r.paired_video` 标注配对关系。
- `submitGeneration` 的 ref_ids 保持全部素材 id（后端按 pair 关系分组，顺序由前端 ref_ids 决定：建议视频与其音轨相邻、视频在前音轨在后）。

### 自测
- 上传 video A + audio B（paired_with=A）→ shots 接口返回 B.paired_video=A。
- 提交 ref 生成 → ComfyUI prompt 同时含 `ref_videos.ref_video_0` 与 `ref_video_audios.ref_video_audio_0`，且指向同一视频/音轨。
- 旧数据/旧调用不回退：不传 paired_with 时行为与现状完全一致。

---

## G4 — 输入片段时长校验（P1）

### 现状
- `uploads.py` 只校验：格式（mime/扩展名）、大小（`MAX_UPLOAD_SIZE_MB`）、数量上限（图≤9/视频≤3/音频≤3/混合≤12）、音频须配图或视频。
- 官方规格：视频/音频**每段 2–15s**，视频类合计 ≤15s，音频类合计 ≤15s。当前不校验 → 超长片段会在推理阶段失败，且失败信息不友好。

### 目标
上传时对 video/audio 探测时长并校验；前端在参考素材区标注限制。

### 改动点

**1) `backend/routers/uploads.py` — 新增时长探测（复用 ffmpeg 生态）：**

```python
def _probe_duration(path: Path) -> float | None:
    """ffprobe 探测时长；不可用/失败返回 None（由调用方决定策略）。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None
```

- 在 `upload_ref` 落盘后、写资产记录前调用（仅 kind in video/audio）：

```python
dur = _probe_duration(dest)
if dur is not None:
    if dur < 2 or dur > 15:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"{kind_label}时长需在 2–15 秒内，当前 {dur:.1f}s")
    # 同类合计 ≤15s（查 shot 下同 kind 已有片段 + 本次）
    total = dur + _existing_kind_duration(shot_id, kind)
    if total > 15:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"{kind_label}合计时长超限（≤15s），当前合计 {total:.1f}s")
```

- `_existing_kind_duration`：查询 shot 下同 kind 资产的时长（assets.meta 里存 `duration`，上传时写入 meta，见下）。
- 探测失败策略（**决策点**）：建议 `dur is None` 时放行但写入 meta `"duration": null` 并允许前端显示「时长未知」；若希望严格，可改为 422「无法探测时长」。二选一并在代码注释标明。
- 上传时把 duration 写入 `assets.meta`：`json.dumps({"original_name": ..., "duration": dur})`。

**2) 前端提示**（`r2v.html` 参考素材块的 `bridge-note` 或 `ref-sub`）：

```
视频/音频每段 2–15s，同类合计 ≤15s；超限上传将被拒绝。
```

（后端 422 的 message 已透传，前端 alert 展示即可，无需前端预校验。）

### 自测
- 上传 20s 音频 → 422 且文件已清理（不留孤儿资产）。
- 上传 10s + 8s 视频 → 第二个 422「合计超限」。
- ffmpeg/ffprobe 缺失环境 → 走放行策略并标注「时长未知」。

---

## G5 — 采样参数按镜头覆盖（P2，可选）

### 现状
- 官方模板把 `sampler_name`（res_multistep）、`scheduler`（simple；r2v 建议 beta/normal）、`steps`（20）、`denoise`（1.0）作为节点可调参数。
- 本项目为**全局** `data/settings.json`（`SETTABLE_KEYS` 含 sampler/scheduler/steps/denoise），前端只读展示「官方模板规格」。

### 方案 A（推荐，改动最小）
保持前端只读，把「如何调整采样参数」写进 `docs/PRD.md` 或 README：

```json
// data/settings.json
{ "sampler": "res_multistep", "scheduler": "normal", "steps": 20, "denoise": 1.0 }
```

（`r2v` 模式后端已自动用 `h3.REF2VA_SCHEDULER = "normal"`，见 `inference.py _run_comfyui`。）

### 方案 B（完全对齐，按需实施）
镜头级覆盖：

1. `spec.py` 增加常量：`SAMPLER_NAME / SCHEDULER / STEPS / DENOISE`（已有）。
2. `inference.py _build_params`：`"sampler_name": params.get("sampler") or resolve_setting("sampler", settings.SAMPLER_NAME)`（steps/denoise 同理；scheduler 注意 r2v 默认仍是 normal，覆盖仅当用户显式传值）。
3. `comfy_workflow.py`：`run_comfyui` 的 `task["sampler_name"]` 已用 `resolve_setting`，改为 `task.get(...) or resolve_setting(...)` 同款优先。
4. diffusers：若 ModularPipeline 接受 sampler/scheduler 参数则透传；否则忽略并在文档说明「diffusers 后端暂不支持采样器覆盖」。
5. 前端：右栏新增可折叠「高级参数」区（默认收起，与模型清单同级）：Sampler（res_multistep / dpmpp_2m / euler 等按引擎支持度下拉）、Scheduler（simple/beta/normal）、Steps（1–50 数字）、Denoise（0–1 步进 0.05）；空值 = 用全局。`getActiveParams` 仅在非空时写入。

### 自测
- UI 设 scheduler=normal 提交 r2v → ComfyUI prompt BasicScheduler 的 scheduler 为 normal；不设 → 全局值。
- 验证 diffusers 后端忽略覆盖时前端提示文案正确。

---

## G6 — 提示词指南信息补全（P2）

### 现状
`r2v.html` 的 tag-guide 只提示 Picture/Video/Audio 标签 + 措辞敏感；`i2v.html` 无时间锚点提示；官方指南中的对话标签、保留标签、11 种语言未覆盖。

### 目标（文案级改动，不改逻辑）

**1) `r2v.html` tag-guide 的 `.tg-note` 增补（替换/追加）：**

```
· 对话：用 <d>[English] 台词...</d> 包裹指定语言（稳定支持：中文/英文/法/德/意/日/韩/葡/俄/西/阿拉伯）。
· 保留程度：fully_preserved（完全保留身份/画面）、partially_copy（部分复用，如沿用 <Audio 1> 的配乐）、reference（仅参考，如借 <Audio 2> 的音色）——写进提示词可显著提升 ref2va 的遵循度。
· 参考标签按连接顺序编号：<Picture 1> / <Video 1> / <Audio 1>；视频的同步音轨引用同一 Audio 标签。
```

**2) `i2v.html` 新增一行引导（放在 `#i2vNote` 下或 foot-note）：**

```
· 时间锚点写法：At 0.00s, <Picture 1> is fully referenced. 之后按 [Shot 1]...[Shot N] 分段描述时间与镜头。
```

**3) 可选：在 `r2v.html` tag-guide 顶部给出官方 Context-IR 提示词结构（说明可手写近似）：**

```
subject_definitions → summary → retention_analysis → detailed_description → overall_soundscape → non_diegetic_music
```

（H3-Context-IR 未开源；此结构供手写提示词时对齐官方组织方式。）

### 自测
- 三页无布局溢出；r2v 页 tag-guide 在窄侧栏下可滚动/换行正常。
- 文案不含占位符、不含 emoji 图标。

---

## G7 — i2v「按首帧图像尺寸生成」（P2，可选）

### 现状
- 官方 i2v 模板含 `ImageScaleToTotalPixels` + `GetImageSize`（“Use Image Size” group）：把首帧图缩到 1MP 并以其尺寸生成。
- 本项目：`_build_params` 按 `aspect + 768P 短边` 计算 width/height，不感知首帧图尺寸。

### 目标（可选开关）
i2v 页「生成尺寸」选择：`768P 短边（默认）` / `跟随首帧图像尺寸`。

### 改动点

**1) 上传时记录图像尺寸**（`uploads.py`，kind=image 时用 PIL 或 ffmpeg 读宽高写入 `assets.meta.width/height`；G1 若已引入 pillow 则直接复用）：

```python
try:
    from PIL import Image
    with Image.open(dest) as im:
        meta["width"], meta["height"] = im.size
except Exception:
    pass
```

**2) `shots.py`** refs 返回项透出 `meta.width/height`（当前只透传 original_name，把 width/height 一并带上）。

**3) `inference.py _build_params`** fl2va 分支，当镜头 `params.size_mode == "follow_first"` 且存在首帧图：

```python
if task_type == h3.FL2VA and params.get("size_mode") == "follow_first":
    dims = refs_meta.get(first_image_id)   # 从 assets.meta 读取
    if dims:
        # 短边对齐 768、长边 ≤1344、32 倍数（复用 spec.resolution_for 思路）
        sw = 768; cap = 1344; m = 32
        w, h = dims["width"], dims["height"]
        if w >= h:
            nw, nh = sw * w / h, sw
        else:
            nh, nw = sw * h / w, sw
        width  = min(round_up(nw, m), cap)
        height = min(round_up(nh, m), cap)
```

（`round_up` 即 spec.resolution_for 内 `_round_multi` 的复制；可与官方模板 1MP + multiple=32 对齐或直接 768p 短边。）

**4) 前端 `i2v.html`**：帧模式下方加一行 `生成尺寸`：`768P 短边（默认）` / `跟随首帧`；`shared.js getActiveParams` 写入 `p.size_mode`；`readbackParams` 回填。

### 自测
- 上传竖图首帧 + 选「跟随首帧」→ 任务 width/height 按 9:16 系输出（768×1344 封顶）。
- 默认模式行为与现状完全一致。

---

## 2. 实施顺序与回归

建议顺序（依赖最少者先行）：

```
G1 → G2 → G4 → G6 → G3 → G5 → G7
```

每完成一项：

1. **前端**：`node --check assets/js/shared.js`（语法）；改动三页 HTML 后目检结构。
2. **后端**：`python -m pytest tests/ -q`（现有 `test_h3_spec_consistency.py` 会校验公式一致性——**若改 spec.py 必须先跑它**）。
3. **链路**：复用 `C:\Users\Doro\.qwenworkcn\workspace\msudqycm5muaibyk\smoke2.js`（jsdom + mock 后端），新增断言覆盖本次改动（如 seed 回填、配对渲染）。
4. **回归验收（全部完成后）**：
   - 三页 file:// 与 `node server.js` 均可打开；模式切换/高亮正常。
   - 首访展示壳弹层 + 持久化 + 外观菜单切换不回退。
   - t2v/i2v/r2v 生成闭环（提交→队列→回填）可用；错误信息如实透传。
   - 素材上传：格式/大小/数量/（新增）时长校验生效；错误文件不留孤儿资产。
   - 明暗主题、响应式、可访问性（aria/键盘）抽查通过。

---

## 3. 参考资料

- 官方发布页（能力/规格/提示词标签/保留标签/11 语言）：https://modelscope.cn/models/MiniMax/MiniMax-H3
- 三份官方工作流（节点与参数真源）：
  - `workflows/video_minimax_h3_t2v.json`
  - `workflows/video_minimax_h3_i2v.json`
  - `workflows/video_minimax_h3_r2v.json`
- 官方提示词指南（Context-IR 结构、时间锚点、对话标签）：HuggingFace `MiniMaxAI/MiniMax-H3/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md`
- 项目契约：`backend/h3/spec.py`、`docs/PRD.md`（§6 能力边界 / §8 API 契约）
