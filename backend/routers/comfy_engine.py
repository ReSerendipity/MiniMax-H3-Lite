"""
MM·H3 工作台 — Comfy 推理引擎（B 方案，进程内复用 comfy_kernel 引擎执行官方工作流）

做法：把 MiniMax-H3-lite 任务参数注入到本项目自带的官方 H3 工作流（t2v / i2v / r2v）
的 API 图中，然后**进程内**调用内置的 comfy_kernel 引擎（复制自 aki-v3 ComfyUI）执行：
`folder_paths` 指向项目 model/、workflows/、output/ → `validate_prompt` 校验（含拓扑补全）
→ `PromptExecutor.execute` 采样/解码/合成 mp4 → 从 comfy_kernel output/ 取回产物。

为什么用这套：官方工作流由 ComfyUI 自己的执行器（含 aimdo 动态显存 / tiled 解码 /
SaveVideo 合成）跑通 —— 正确路径；且 comfy_kernel 已内置进项目，**无需外部 ComfyUI 服务**，
实现完全脱离 ComfyUI 独立运行。避免在 C:\\Python312 手动复刻底层导致的内存崩溃（Gotcha #10）。

兼容：当设置了 MMH3_COMFY_URL（保留 HTTP 后端）仍走 HTTP 提交外部 ComfyUI，供联调。
"""
from __future__ import annotations

import asyncio
import os
import json
import logging
import sys
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from h3 import spec as h3

_log = logging.getLogger(__name__)

# 项目内路径（脱离 aki/ComfyUI）——单一事实来源从 config 派生
_BASE_DIR = Path(__file__).resolve().parent.parent.parent        # 项目根
_KERNEL_DIR = _BASE_DIR / "comfy_kernel"                        # 内置 ComfyUI 引擎源码
_WORKFLOW_DIR = _BASE_DIR / "workflows"                        # 官方工作流（项目内）
_WORKFLOW_FILES = {
    h3.T2VA: "video_minimax_h3_t2v.json",
    h3.FL2VA: "video_minimax_h3_i2v.json",
    h3.REF2VA: "video_minimax_h3_r2v.json",
}
_FAKE_NODES = ("MarkdownNote", "Note", "Reroute")

# comfy_kernel 引擎就绪标志（惰性初始化）
_KERNEL_READY = False


def comfy_url() -> str:
    return (settings.COMFY_URL or "http://127.0.0.1:8188").rstrip("/")


# ── ComfyUI HTTP ──────────────────────────────────────────
def _http(method: str, path: str, body=None, timeout: int = 30):
    url = comfy_url() + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ComfyUI {method} {path} 失败 HTTP {e.code}: "
                           f"{e.read().decode('utf-8', 'replace')[:1500]}") from e


def _check_server() -> str:
    status, _ = _http("GET", "/system_stats")
    return f"ComfyUI 连接正常 (HTTP {status})"


# ── 工作流装载 / 注入 ─────────────────────────────────────
def _load_api(task_type: str) -> dict:
    """读取项目内固化的扁平 API 工作流（workflows/api/*.api.json）。

    这些文件由官方 editor(subgraph) 工作流经 Comfy 的 extract_api_prompt 一次性展开，
    已与 comfy_kernel 的 node 名、默认值对齐，运行时无需再依赖外部 ComfyUI / aki 工具。
    """
    wf = _WORKFLOW_FILES[task_type]
    api = json.loads((_WORKFLOW_DIR / "api" / wf.replace(".json", ".api.json"))
                     .read_text(encoding="utf-8"))
    return {nid: n for nid, n in api.items()
            if n.get("class_type") not in _FAKE_NODES}


def _find(api: dict, class_type: str) -> str:
    """按 class_type 找节点 id；有多个则报错（期望唯一）。"""
    ids = [nid for nid, n in api.items() if n.get("class_type") == class_type]
    if len(ids) != 1:
        raise RuntimeError(f"工作流中 {class_type} 节点数量异常: {ids}")
    return ids[0]


def _inject_common(api: dict, params: dict) -> None:
    """注入宽高/时长/种子/prompt/步数，并修正 clip 模型名。"""
    task = params["task_type"]
    width, height = params["width"], params["height"]

    # 1) 分辨率
    try:
        rs = _find(api, "ResolutionSelector")
        aspect = params.get("aspect_ratio")
        if not aspect:
            aspect = "16:9 (Widescreen)" if width / height > 1.2 else (
                "1:1 (Square)" if abs(width - height) / width < 0.05 else (
                    "9:16 (Vertical)" if height > width else "4:3 (Classic)"))
        api[rs]["inputs"]["aspect_ratio"] = aspect
        api[rs]["inputs"]["megapixels"] = round(width * height / 1e6, 2)
    except RuntimeError:
        pass

    # 2) 主节点 prompt / width / height（ImageToVideo / ReferenceToVideo）
    main_cls = "MiniMaxH3ReferenceToVideo" if task == h3.REF2VA else "MiniMaxH3ImageToVideo"
    main = _find(api, main_cls)
    api[main]["inputs"]["prompt"] = params["prompt"]
    if task == h3.REF2VA:
        api[main]["inputs"].setdefault("ref_image_size", "match")
        # width/height 由 ResolutionSelector 连接提供，这里用 ResolutionSelector 兜底注入
        rs = _find(api, "ResolutionSelector")
        api[rs]["inputs"]["aspect_ratio"] = _aspect_name(width, height)
        api[rs]["inputs"]["megapixels"] = round(width * height / 1e6, 2)
    else:
        api[main]["inputs"]["width"] = width
        api[main]["inputs"]["height"] = height

    # 3) 时长：ComfyMathExpression 的表达式按秒数算帧数，PrimitiveFloat.value 为秒数
    for nid, n in api.items():
        if n.get("class_type") == "PrimitiveFloat":
            api[nid]["inputs"]["value"] = float(params.get("duration") or 4)

    # 4) 种子
    seed = int(params.get("seed") or 0)
    for nid, n in api.items():
        if n.get("class_type") == "RandomNoise":
            api[nid]["inputs"]["noise_seed"] = seed

    # 5) 步数（BasicScheduler.steps）；ref2v 官方 r2v 用 20，t2v 用 8 turbo lora
    try:
        bs = _find(api, "BasicScheduler")
        api[bs]["inputs"]["steps"] = int(params.get("steps") or h3.STEPS)
    except RuntimeError:
        pass

    # 6) 修正模型文件名：API 官方引用（小写 awq 等）可能与项目 model/ 实际文件名不同，
    #    统一改写为项目内实际存在的权重（comfy_kernel folder_paths 已指向项目 model/）。
    _inject_models(api)


# 各 Loader 节点 → 其 combo 输入名 + 对应 folder_paths 目录
_LOADER_FOLDERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "UNETLoader": ("unet_name", ("diffusion_models",)),
    "CLIPLoader": ("clip_name", ("text_encoders", "clip")),
    "VAELoader": ("vae_name", ("vae",)),
    "LoraLoader": ("lora_name", ("loras",)),
}


def _inject_models(api: dict) -> None:
    """把 Loader 节点的模型文件名改写为项目 model/ 中确实存在的文件名。

    直接扫描项目 model/ 目录（diffusion_models / text_encoders / vae / loras），
    API 引用的官方文件名（小写 awq 等）→ 与项目实际文件名做「子串 / 共同前缀」匹配。
    引擎未可用时不报错（由 validate 兜底）。
    """
    imports = _scan_project_models()
    for nid, n in api.items():
        meta = _LOADER_FOLDERS.get(n.get("class_type"))
        if not meta or not isinstance(n.get("inputs"), dict):
            continue
        input_name, folders = meta
        current = n["inputs"].get(input_name)
        if not isinstance(current, str):
            continue
        candidates = [f for fl in folders for f in (imports.get(fl) or [])]
        if current in candidates:
            continue
        cur_norm = current.lower().replace("-", "").replace("_", "")
        match = None
        for cand in candidates:
            cand_norm = cand.lower().replace("-", "").replace("_", "")
            if cur_norm in cand_norm or cand_norm in cur_norm:
                match = cand
                break
        if match is None:
            best_len, best = 0, None
            for cand in candidates:
                pl = _prefix_len(cur_norm, cand.lower().replace("-", "").replace("_", ""))
                if pl > best_len:
                    best_len, best = pl, cand
            match = best
        if match and match != current:
            n["inputs"][input_name] = match


def _prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


_model_scan_cache = None


def _scan_project_models() -> dict:
    """扫描项目 model/ 目录，返回 {目录名: [文件名]}。结果缓存。"""
    global _model_scan_cache
    if _model_scan_cache is not None:
        return _model_scan_cache
    out = {k: [] for k in ("diffusion_models", "text_encoders", "vae", "loras", "clip")}
    model_dir = _BASE_DIR / "model"
    if model_dir.is_dir():
        for sub, names in out.items():
            d = model_dir / sub
            if d.is_dir():
                names[:] = sorted(p.name for p in d.glob("*") if p.is_file())
    _model_scan_cache = out
    return out


def _kernel_ready() -> bool:
    """进程内引擎是否已初始化（comfy_kernel 可导入 + folder_paths 已装 model 路径）。"""
    try:
        import folder_paths  # noqa: F401
        return True
    except Exception:
        return False


def _aspect_name(w: int, h: int) -> str:
    r = w / h if h else 1
    if r > 1.7:
        return "21:9 (Cinematic)"
    if r > 1.2:
        return "16:9 (Widescreen)"
    if abs(r - 1) < 0.05:
        return "1:1 (Square)"
    if r < 0.7:
        return "9:16 (Vertical)"
    if r < 1.0:
        return "3:4 (Portrait)"
    return "4:3 (Classic)"


def _normalize_refs(refs: list) -> dict:
    """把上传参考归一化为 图片/视频/音频 三类绝对路径。"""
    imgs, vids, auds = [], [], []
    for r in refs or []:
        p = r.get("path") or r.get("url") or ""
        kind = r.get("kind") or r.get("type") or _guess_kind(p)
        if kind == "image":
            imgs.append(p)
        elif kind == "video":
            vids.append(p)
        elif kind == "audio":
            auds.append(p)
    return {"image": imgs, "video": vids, "audio": auds}


def _guess_kind(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return "image"
    if ext in (".mp4", ".mov", ".webm", ".mkv"):
        return "video"
    if ext in (".wav", ".mp3", ".flac", ".aac", ".ogg"):
        return "audio"
    return "image"


def _inject_ref2va(api: dict, params: dict) -> None:
    """把参考素材注入 r2v 工作流的 LoadImage / LoadVideo。
    官方 r2v 只有 2 个 LoadImage 槽；参考视频/音频需经 LoadVideo/LoadAudio 接入 ReferenceToVideo。
    当前先支持图片参考（<=2 张，替换现有 LoadImage），视频/音频参考见扩展说明。
    """
    refs = _normalize_refs(params.get("refs") or [])
    imgs = refs["image"]

    load_img_ids = [nid for nid, n in api.items() if n.get("class_type") == "LoadImage"]
    main = _find(api, "MiniMaxH3ReferenceToVideo")
    # 先清空现有图片连接，再按需绑定
    for k in [k for k in api[main]["inputs"] if k.startswith("ref_images.")]:
        del api[main]["inputs"][k]
    for i, ip in enumerate(imgs[:2]):
        if i < len(load_img_ids):
            api[load_img_ids[i]]["inputs"]["image"] = _input_image_name(ip)
            api[main]["inputs"][f"ref_images.ref_image_{i}"] = [load_img_ids[i], 0]
    if len(imgs) > 2:
        # 官方节点单输入只能接 2 张，多张需复合——暂以文本提示告知
        api[main]["inputs"]["prompt"] = (api[main]["inputs"].get("prompt", "")
                                         + f"\nNOTE: {len(imgs)} reference images provided "
                                           f"(only first 2 used by workflow).")


def _input_image_name(path: str) -> str:
    """ComfyUI 的 image 输入是相对 input 目录的文件名。传入绝对路径时需先拷贝进输入目录，
    返回文件名。若已是纯文件名则原样返回。"""
    if not Path(path).is_absolute():
        return Path(path).name
    import shutil
    dest = Path(r"C:\Users\Doro\APP\ComfyUI-aki-v3\ComfyUI\input")
    dest.mkdir(parents=True, exist_ok=True)
    name = f"mmh3_{uuid.uuid4().hex}" + Path(path).suffix
    shutil.copy(path, dest / name)
    return name


# ── 进程内 comfy_kernel 引擎 ─────────────────────────────
# 复制自 ComfyUI 内核，随项目分发，运行时不再需要外部 ComfyUI 服务。
_engine = None            # PromptExecutor（复用实例，省去重复初始化）
_nodes = None             # nodes 模块（缓存 moudle 引用）
_server_stub = None


class _MinimalServer:
    """PromptExecutor 依赖的最小 server 接口（send_sync / queue_updated / last_node_id）。"""
    client_id = None
    last_node_id = None
    last_prompt_id = None

    def send_sync(self, *args, **kwargs):
        pass

    def queue_updated(self, *args, **kwargs):
        pass


def _ensure_kernel() -> tuple:
    """初始化（仅一次）：把 comfy_kernel 加入 sys.path、绑定项目 model/ 路径、
    注册全部内置节点、构造 PromptExecutor。返回 (executor, nodes)。"""
    global _engine, _nodes, _server_stub
    if _engine is not None:
        return _engine, _nodes

    if not _KERNEL_DIR.is_dir():
        raise RuntimeError(f"内置 Comfy 引擎缺失：{_KERNEL_DIR}（comfy_kernel 未随项目分发）")
    if str(_KERNEL_DIR) not in sys.path:
        sys.path.insert(0, str(_KERNEL_DIR))

    # 显存策略：在 comfy 模块级读取 args 之前设置，保证加载主模型/文本编码器时走
    # lowvram 卸载（12GB 卡跑 20GB UNET+17GB CLIP+VAE 必须，否则采样阶段 CUDA OOM）。
    # 此设置必须在任何 `import comfy.*` 之前（model_management 在 import 时读 args）。
    from comfy import cli_args as _cli
    _cli.args.lowvram = True
    _cli.args.novram = False
    _cli.args.preview_method = None
    _cli.args.vram_headroom = max((float(getattr(_cli.args, "vram_headroom", 0) or 0)), 1.0)
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    import folder_paths as fp
    model_dir = _BASE_DIR / "model"
    # 绑定项目 model/ 各子目录到 ComfyUI 的模型目录（幂等）
    for folder, rel in (("diffusion_models", "diffusion_models"),
                        ("text_encoders", "text_encoders"),
                        ("vae", "vae"),
                        ("loras", "loras")):
        p = model_dir / rel
        if p.is_dir():
            fp.add_model_folder_path(folder, str(p))
    # 输出目录：本项目 assets/generated（SaveVideo 写这里，无需轮询外部 output/）
    _out = settings.ASSETS_DIR / "generated"
    _out.mkdir(parents=True, exist_ok=True)
    fp.set_output_directory(str(_out))

    # 启用 DynamicVRAM（comfy-aimdo）：让 20GB H3 模型按层落盘到 12GB 卡（不装也可能 OOM）。
    # 对齐 ComfyUI 完整启动时的做法（main.py dynamic_vram_supported 分支）。
    try:
        import comfy.model_management as _mmng
        import comfy.model_patcher as _mp
        import comfy.memory_management as _memmg
        import comfy_aimdo.control as _ctl
        if _mmng.is_nvidia():
            # 必须先 init() 加载底层 DLL，再 init_devices 绑定设备
            if _ctl.init():
                devs = list(_mmng.get_all_torch_devices())
                try:
                    ok = _ctl.init_devices(
                        (d.index, int(_cli.args.vram_headroom * 1024 ** 3)) for d in devs)
                except TypeError:
                    ok = _ctl.init_devices(d.index for d in devs)
                if ok:
                    _mp.CoreModelPatcher = _mp.ModelPatcherDynamic
                    _memmg.aimdo_enabled = True
                    # 关键：execution.py 等模块在 control.init() 之前就 import 了
                    # comfy_aimdo.model_vbar / model_prefetch，其顶层 `lib = control.lib`
                    # 快照为 None。这里 reload，让它们重新拿到已加载的 lib。
                    import importlib as _imp
                    for _sub in ("comfy_aimdo.model_vbar", "comfy_aimdo.host_buffer",
                                 "comfy_aimdo.vram_buffer", "comfy_aimdo.torch"):
                        try:
                            _imp.reload(_imp.import_module(_sub))
                        except Exception:
                            pass
                    _log.info("DynamicVRAM（comfy-aimdo）已启用")
                else:
                    _log.warning("DynamicVRAM 设备初始化失败（回退 legacy 显存管理）")
    except Exception as _e:
        _log.warning("DynamicVRAM 初始化失败（回退 legacy 显存管理）：%s", _e)

    import asyncio as _asyncio
    import nodes
    _asyncio.run(nodes.init_extra_nodes(init_custom_nodes=False, init_api_nodes=False))
    _nodes = nodes

    import execution
    _server_stub = _MinimalServer()
    _engine = execution.PromptExecutor(
        _server_stub,
        cache_type=execution.CacheType.NONE,
        cache_args={"lru": 0, "ram": 2.0, "ram_inactive": 2.0},
    )
    return _engine, _nodes


def _run_in_process(api: dict, timeout: int | None = None) -> str:
    """进程内执行 API 工作流，返回 mp4 绝对路径。失败抛 RuntimeError。"""
    executor, nodes = _ensure_kernel()
    nodes.interrupt_processing(False)

    import execution
    pid = str(uuid.uuid4())
    valid = asyncio.run(execution.validate_prompt(pid, api, None))
    if not valid[0]:
        raise RuntimeError("工作流校验失败: " + json.dumps(valid[1], ensure_ascii=False)[:1500])
    outputs_to_execute = valid[2]

    executor.execute(api, pid, {}, outputs_to_execute)
    if not executor.success:
        errs = [m for m in executor.status_messages if m[0] in ("execution_error", "execution_interrupted")]
        raise RuntimeError("进程内 Comfy 引擎执行失败: " + json.dumps(errs, ensure_ascii=False)[:1500])

    # 从 executor.history_result 输出里找 SaveVideo 的 mp4 产物
    # （videos 含 absolute_path 或 output 目录相对 filename）
    mp4s = []
    out_dir = Path(settings.ASSETS_DIR / "generated")
    for node_out in (executor.history_result.get("outputs") or {}).values():
        if not isinstance(node_out, dict):
            continue
        for key, val in node_out.items():
            items = val if isinstance(val, list) else [val]
            for it in items:
                if not isinstance(it, dict):
                    continue
                ap = it.get("absolute_path") or it.get("path") or it.get("filename")
                if not ap or not str(ap).endswith(".mp4"):
                    continue
                p = Path(ap)
                if not p.is_absolute():
                    p = out_dir / p.name
                if p.exists():
                    mp4s.append(p)
    if not mp4s:
        # 兜底：直接在输出目录里找最新 mp4（SaveVideo 默认已写入）
        mp4s = [p for p in out_dir.rglob("*.mp4")]
    if not mp4s:
        raise RuntimeError("进程内 Comfy 引擎未产出 mp4: "
                           + json.dumps(executor.history_result.get("outputs") or {}, default=str)[:1500])
    mp4s.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)
    return str(mp4s[-1])


# ── 提交 / 轮询 / 落盘 ────────────────────────────────────
def _submit(api: dict) -> str:
    status, body = _http("POST", "/prompt", {"prompt": api}, timeout=60)
    return body["prompt_id"]


def _wait(prompt_id: str, timeout: int = 1800) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        try:
            status, h = _http("GET", f"/history/{prompt_id}", timeout=15)
        except RuntimeError as e:
            # 历史尚未写入通常属正常（新提交）——仅当明确报错时才中断
            if "404" in str(e) or "not found" in str(e).lower():
                time.sleep(2)
                continue
            raise
        if prompt_id in h:
            entry = h[prompt_id]
            st = entry.get("status", {})
            if st.get("completed"):
                return entry.get("outputs", {})
            if st.get("status_str") == "error":
                raise RuntimeError("ComfyUI 任务失败: "
                                   + json.dumps(st.get("messages", st), ensure_ascii=False)[:1500])
        time.sleep(3)
    raise TimeoutError(f"ComfyUI 任务 {prompt_id} 超时（>{timeout}s）")


# 仅供 HTTP 旧路径：外部 ComfyUI 的输出目录（进程内路径不走这里）
_HTTP_OUT_DIR = Path(r"C:\Users\Doro\APP\ComfyUI-aki-v3\ComfyUI\output")


def _freshest_output(outputs: dict) -> Path:
    """从 /history 输出里找 mp4 路径（SaveVideo 产出，含音轨）。"""
    out_dir = _HTTP_OUT_DIR
    best = None
    for node_out in outputs.values():
        imgs = node_out.get("images") or []
        for im in imgs:
            if str(im.get("filename", "")).endswith(".mp4"):
                p = out_dir / im["filename"]
                if best is None or p.stat().st_mtime > best.stat().st_mtime:
                    best = p
    if best is None:
        raise RuntimeError("ComfyUI 未返回 mp4 产物: " + json.dumps(outputs, default=str))
    return best


# ── 入口：run(params) → mp4 绝对路径 ──────────────────────
def run(params: dict) -> str:
    """执行官方 H3 工作流，返回 mp4 路径。失败抛 RuntimeError（任务如实 failed）。

    默认走**进程内** comfy_kernel 引擎（完全脱离外部 ComfyUI）；
    仅当显式设置了 MMH3_COMFY_URL 时才走 HTTP 提交外部 ComfyUI（联调用）。
    """
    task_type = params["task_type"]
    api = _load_api(task_type)
    _inject_common(api, params)
    if task_type == h3.REF2VA:
        _inject_ref2va(api, params)

    # 判断用哪种后端：显式环境变量才走 HTTP，否则进程内
    internal = True
    import os as _os
    env_url = _os.environ.get("MMH3_COMFY_URL", "").strip()
    if env_url:
        _check_server()
        pid = _submit(api)
        outputs = _wait(pid, timeout=int(settings.INFERENCE_TIMEOUT or 1800))
        src = _freshest_output(outputs)
        _log.info("Comfy 后端: HTTP → 外部 ComfyUI")
        internal = False
    else:
        src = Path(_run_in_process(api))

    out_dir = settings.ASSETS_DIR / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"h3_{task_type}_{uuid.uuid4().hex}.mp4"
    dst.write_bytes(src.read_bytes())
    if dst.stat().st_size == 0:
        raise RuntimeError(f"{'进程内 Comfy 引擎' if internal else 'ComfyUI'}产物为 0 字节")
    return str(dst)
