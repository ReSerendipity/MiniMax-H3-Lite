"""
MM·H3 工作台 — 统一配置管理
风格向兄弟项目 (Image_MultiModel 等) 对齐：集中配置、环境变量覆盖。
"""
import os
from pathlib import Path
from dataclasses import dataclass, field

from h3.spec import (
    MODELS as H3_MODELS,
    SAMPLER_NAME as H3_SAMPLER,
    SCHEDULER as H3_SCHEDULER,
    STEPS as H3_STEPS,
    DENOISE as H3_DENOISE,
    RESOLUTION_PRESETS as H3_RESOLUTION_PRESETS,
    RESOLUTION_DEFAULT as H3_RESOLUTION_DEFAULT,
    DURATION_MIN as H3_DURATION_MIN,
    DURATION_MAX as H3_DURATION_MAX,
    RATIOS as H3_RATIOS,
)


# 模块级常量，避免 dataclass field default_factory 中的递归
_BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    # ── 路径 ──────────────────────────────────────────────
    BASE_DIR: Path = _BASE_DIR
    DB_PATH: Path = _BASE_DIR / "data" / "mmh3.db"
    ASSETS_DIR: Path = _BASE_DIR / "assets"
    UPLOADS_DIR: Path = _BASE_DIR / "uploads"

    # ── 服务 (单端口:Jinja2 页面 + API + 静态资源统一由 FastAPI 提供) ──
    HOST: str = "127.0.0.1"
    PORT: int = 18080

    # ── 推理 ──────────────────────────────────────────────
    MODEL_NAME: str = "MiniMaxAI/MiniMax-H3"
    MODEL_PATH: str = ""                      # 本地权重路径，空则从 HF/魔搭拉取
    INFERENCE_BACKEND: str = "diffusers"     # diffusers | comfy（B 方案：进程内复用 ComfyUI 内核）
    QUANTIZATION: str = "int8"                # bf16 | int8 | int4 | gguf-q4_k_m
    MAX_CONCURRENCY: int = 1                  # 单机默认串行
    INFERENCE_TIMEOUT: int = 600              # 单任务超时 (秒)
    COMFY_SOURCE_DIR: str = ""                # (保留) Comfy 内核源码目录
    COMFY_URL: str = "http://127.0.0.1:8188"  # ComfyUI HTTP 服务地址（B 方案经此提交官方工作流）

    # ── 官方 H3 模型文件名 (默认来自 h3.spec，可环境变量覆盖) ──
    MODEL_FL2VA: str = H3_MODELS["fl2va"]
    MODEL_REF2VA: str = H3_MODELS["ref2va"]
    MODEL_CLIP: str = H3_MODELS["clip"]
    MODEL_VAE_VIDEO: str = H3_MODELS["vae_video"]
    MODEL_VAE_AUDIO: str = H3_MODELS["vae_audio"]

    # ── 采样默认值 (官方模板) ──────────────────────────
    SAMPLER_NAME: str = H3_SAMPLER
    SCHEDULER: str = H3_SCHEDULER
    STEPS: int = H3_STEPS
    DENOISE: float = H3_DENOISE

    # ── 保存配置 ──────────────────────────────────────────
    SAVE_PREFIX: str = "mmh3"
    REF_IMAGE_SIZE: str = "match"

    # ── 上传校验 ──────────────────────────────────────────
    MAX_IMAGE_COUNT: int = 9
    MAX_VIDEO_COUNT: int = 3
    MAX_AUDIO_COUNT: int = 3
    MAX_TOTAL_REFS: int = 12
    MAX_UPLOAD_SIZE_MB: int = 200

    # ── 模型规格 (对齐官方工作流，spec.py 为单一事实来源) ────
    SUPPORTED_RATIOS: list = field(default_factory=lambda: list(H3_RATIOS.keys()))
    SUPPORTED_DURATIONS: list = field(default_factory=lambda: list(range(H3_DURATION_MIN, H3_DURATION_MAX + 1)))
    SUPPORTED_DURATION_MIN: int = H3_DURATION_MIN
    SUPPORTED_DURATION_MAX: int = H3_DURATION_MAX
    RESOLUTION_PRESETS: dict = field(
        default_factory=lambda: {
            k: {"label": f"{k}MP", "width": v[0], "height": v[1]} for k, v in H3_RESOLUTION_PRESETS.items()
        }
    )
    RESOLUTION_DEFAULT: str = H3_RESOLUTION_DEFAULT
    FPS: int = 24
    AUDIO_SAMPLE_RATE: int = 32000
    OUTPUT_BIT_DEPTH: int = 8            # 固定输出(官方 CreateVideo bit_depth)
    OUTPUT_FORMAT: str = "mp4"           # 固定输出(官方 SaveVideo format=auto)
    MAX_PROMPT_CHARS: int = 7000

    # ── 队列 ──────────────────────────────────────────────
    TASK_RETRY_MAX: int = 1
    TASK_TIMEOUT: int = 600

    # ── 断点续跑 (checkpoint #7) ───────────────────────────
    CHECKPOINT_DIR: Path = _BASE_DIR / "data" / "checkpoints"
    CHECKPOINT_EVERY: int = 5                    # 每完成 N 个镜头保存一次进度

    def __post_init__(self):
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # 允许环境变量覆盖
    @classmethod
    def from_env(cls) -> "Settings":
        s = cls()
        env = os.environ
        if env.get("MMH3_HOST"):
            s.HOST = env["MMH3_HOST"]
        if env.get("MMH3_PORT"):
            s.PORT = int(env["MMH3_PORT"])
        if env.get("MMH3_MODEL_PATH"):
            s.MODEL_PATH = env["MMH3_MODEL_PATH"]
        if env.get("MMH3_COMFY_SOURCE_DIR"):
            s.COMFY_SOURCE_DIR = env["MMH3_COMFY_SOURCE_DIR"]
        if env.get("MMH3_COMFY_URL"):
            s.COMFY_URL = env["MMH3_COMFY_URL"]
        if env.get("MMH3_INFERENCE_BACKEND"):
            s.INFERENCE_BACKEND = env["MMH3_INFERENCE_BACKEND"]
        if env.get("MMH3_QUANTIZATION"):
            s.QUANTIZATION = env["MMH3_QUANTIZATION"]
        if env.get("MMH3_MAX_CONCURRENCY"):
            s.MAX_CONCURRENCY = max(1, int(env["MMH3_MAX_CONCURRENCY"]))
        for env_key, attr in (
            ("MMH3_MODEL_FL2VA", "MODEL_FL2VA"),
            ("MMH3_MODEL_REF2VA", "MODEL_REF2VA"),
            ("MMH3_MODEL_CLIP", "MODEL_CLIP"),
            ("MMH3_MODEL_VAE_VIDEO", "MODEL_VAE_VIDEO"),
            ("MMH3_MODEL_VAE_AUDIO", "MODEL_VAE_AUDIO"),
        ):
            if env.get(env_key):
                setattr(s, attr, env[env_key])
        return s


settings = Settings.from_env()
