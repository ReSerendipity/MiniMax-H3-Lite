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

# ── 输出规格（官方） ──────────────────────────────
FPS = 24
AUDIO_SAMPLE_RATE = 32000
SHORT_SIDE = 768          # 768p 短边
MAX_DIM = 1344            # 官方上限 768×1344
FRAME_BLOCK = 17          # 17k+5 帧网格
FRAME_MIN = 5


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
    """将 [{kind, path}, ...] 按 kind 分组为 {image: [...], video: [...], audio: [...]}"""
    grouped = {"image": [], "video": [], "audio": []}
    for r in refs:
        k = r.get("kind")
        if k in grouped:
            grouped[k].append(r["path"])
    return grouped
