"""
H3 官方工作流能力 → 框架无关任务规格层。

数据来源：workflows/ 下三份官方 ComfyUI 模板（video_minimax_h3_t2v.json / video_minimax_h3_i2v.json /
video_minimax_h3_r2v.json），以及 MiniMax H3 官方模型卡（modelscope.cn/models/MiniMax/MiniMax-H3）。

本模块不依赖 diffusers / ComfyUI / 任何推理框架，供各后端适配器共享同一份参数契约。
"""

# ── 任务类型 ──────────────────────────────────────
T2VA = "t2va"
FL2VA = "fl2va"
REF2VA = "ref2va"

# 前端 mode → 任务类型（PRD §6.1）
MODE_TO_TASK = {
    "text": T2VA,
    "first_frame": FL2VA,
    "last_frame": FL2VA,
    "first_last": FL2VA,
    "ref": REF2VA,
}

# ── 输出规格（官方，固定不可改） ─────────────────────
FPS = 24
AUDIO_SAMPLE_RATE = 32000
BIT_DEPTH = 8              # CreateVideo: bit_depth=8
OUTPUT_FORMAT = "mp4"      # SaveVideo: format=auto / codec=auto
FRAME_BLOCK = 17           # 17k+5 帧网格
FRAME_MIN = 5

# ── 分辨率（官方 README + ResolutionSelector Size 表，上限 768p 短边） ──
# key = 百万像素(megapixels)，值 = 16:9 下的输出 (宽×高)，multiple=32。
# 0.98 = H3-Base 原生画布（短边 768，capped 768×1344）；H3-Base 只输出 768p。
# 更高分辨率（如 1080p/2K）需 H3-Regenerate-2K 模块，未随开源 Base 提供 → 不作前端档位。
RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "0.4": (864, 480),
    "0.5": (960, 544),
    "0.6": (1056, 608),
    "0.7": (1152, 640),
    "0.8": (1216, 672),
    "0.9": (1280, 736),
    "0.98": (1344, 768),   # H3 原生画布上限（默认且最高）
}
RESOLUTION_DEFAULT = "0.98"   # 官方各工作流默认（H3-Base 原生最高）
RESOLUTION_MULTIPLE = 32      # ResolutionSelector multiple（官方 = 32）
SHORT_SIDE = 768
MAX_DIM = 1344                # H3 原生画布长边上限（capped 768×1344）
# 各档位对应的「短边」（取自官方 Size 表；0.98=原生 768）
RESOLUTION_SHORT_SIDE: dict[str, int] = {
    "0.4": 480, "0.5": 544, "0.6": 608, "0.7": 640, "0.8": 672, "0.9": 736, "0.98": 768,
}

# ── 时长（官方 PrimitiveFloat 连续值 + MathExpr 处理） ──
DURATION_MIN = 4              # 前端 UI 下限（官方模型实际支持 0~15s，UI 从 4s 起）
DURATION_MAX = 15             # 官方模型上限「约 15 秒」


# ── 帧长：官方 ComfyMathExpression 公式 ───────────
def frames_for_duration(duration_seconds: float) -> int:
    """max(5, round(d*24)) + (5 - (max(5, round(d*24)) % 17)) % 17（24fps，17k+5 网格向上对齐）"""
    base = max(FRAME_MIN, round(duration_seconds * FPS))
    return base + (FRAME_MIN - (base % FRAME_BLOCK)) % FRAME_BLOCK


# ── 宽高比 → 分辨率 ───────────────────────────────
RATIOS = {
    "21:9": (21, 9),
    "16:9": (16, 9),
    "4:3": (4, 3),
    "1:1": (1, 1),
    "3:4": (3, 4),
    "9:16": (9, 16),
}


def resolution_for(aspect: str, short_side: int = SHORT_SIDE, multiple: int = 2) -> tuple[int, int]:
    """
    由宽高比计算 (width, height)：短边 = short_side（768），长边按比例计算，
    取 multiple 的倍数（diffusers 用 2 取偶，ComfyUI 用 32 对齐 ResolutionSelector），
    长边上限 MAX_DIM（1344）。
    """
    w, h = RATIOS.get(aspect, (16, 9))
    if w >= h:
        width = short_side * w / h
        height = short_side
    else:
        height = short_side * h / w
        width = short_side

    def _round_multi(v: float, m: int) -> int:
        v = max(int(v), m)
        v = ((v + m - 1) // m) * m
        return min(v, MAX_DIM)

    return (_round_multi(width, multiple), _round_multi(height, multiple))


def dims_for_resolution(preset: str | None, aspect: str | None = None, multiple: int = RESOLUTION_MULTIPLE) -> tuple[int, int]:
    """
    由官方分辨率档位 + 宽高比计算 (width, height)。
    - 16:9（或无 aspect）→ 返回档位在官方 Size 表里的精确尺寸。
    - 其它比例 → 用该档位的「短边」按比例换算，round 到 multiple(=32)，
      长边封顶 MAX_DIM(1344)（H3-Base 原生画布上限）。
    """
    if not preset or preset not in RESOLUTION_PRESETS:
        preset = RESOLUTION_DEFAULT
    if not aspect or aspect == "16:9":
        return RESOLUTION_PRESETS[preset]

    short = RESOLUTION_SHORT_SIDE.get(preset, SHORT_SIDE)
    w, h = RATIOS.get(aspect, (16, 9))
    if w >= h:
        width = short * w / h
        height = short
    else:
        height = short * h / w
        width = short

    def _rc(v: float) -> int:
        v = max(int(v), multiple)
        v = ((v + multiple - 1) // multiple) * multiple
        return min(v, MAX_DIM)

    return (_rc(width), _rc(height))


# ── 官方模型文件名（来自官方模板 + 模型卡） ────────
MODELS = {
    "fl2va": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "ref2va": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "vae_video": "minimax_h3_video_vae_fp16.safetensors",
    "vae_audio": "minimax_h3_audio_vae_fp32.safetensors",
}

# 官方模板中的 CLIPLoader type / UNETLoader weight_dtype / 采样默认值
CLIP_TYPE = "minimax"
UNET_WEIGHT_DTYPE = "default"
SAMPLER_NAME = "res_multistep"
SCHEDULER = "simple"
STEPS = 20
DENOISE = 1.0

# r2v 模板建议：参考密集时 beta/normal 调度器通常优于 simple
REF2VA_SCHEDULER = "normal"

# ── 参考素材上限（官方 + PRD §6.1） ───────────────
MAX_REF_IMAGES = 9
MAX_REF_VIDEOS = 3
MAX_REF_AUDIOS = 3
MAX_REF_TOTAL = 12


# ── 工具 ─────────────────────────────────────────
def group_refs(refs: list[dict]) -> dict:
    """将 [{kind, path, id, paired_video}, ...] 按 kind 分组为
    {image: [...], video: [...], audio: [...], ref_video_audios: [{video, audio}, ...]}
    ref_video_audios：音频配对到视频的同步音轨（下标对齐 ref_videos）。
    """
    grouped = {"image": [], "video": [], "audio": [], "ref_video_audios": []}
    video_by_id = {}
    for r in refs:
        k = r.get("kind")
        if k in ("image", "video", "audio"):
            grouped[k].append(r["path"])
            if k == "video" and r.get("id"):
                video_by_id[r["id"]] = r["path"]
    # 配对音轨：音频 paired_video 指向某个视频 id → 成对输出
    paired = []
    pair_audio_by_video = {}  # video_path -> audio_path
    for r in refs:
        if r.get("kind") == "audio" and r.get("paired_video"):
            vid = r["paired_video"]
            if vid in video_by_id:
                vpath = video_by_id[vid]
                apath = r["path"]
                pair_audio_by_video[vpath] = apath
                paired.append({"video": vpath, "audio": apath})
    grouped["ref_video_audios"] = paired
    return grouped
