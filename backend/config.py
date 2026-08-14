"""
MM·H3 工作台 — 统一配置管理
风格向兄弟项目（Image_MultiModel 等）对齐：集中配置、环境变量覆盖。
"""
import os
from pathlib import Path
from dataclasses import dataclass, field


# 模块级常量，避免 dataclass field default_factory 中的递归
_BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    # ── 路径 ──────────────────────────────────────────────
    BASE_DIR: Path = _BASE_DIR
    DB_PATH: Path = _BASE_DIR / "data" / "mmh3.db"
    ASSETS_DIR: Path = _BASE_DIR / "assets"
    UPLOADS_DIR: Path = _BASE_DIR / "uploads"

    # ── 服务 ──────────────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 18080
    FRONTEND_PORT: int = 8080

    # ── 推理 ──────────────────────────────────────────────
    MODEL_NAME: str = "MiniMaxAI/MiniMax-H3"
    MODEL_PATH: str = ""                      # 本地权重路径，空则从 HF/魔搭拉取
    INFERENCE_BACKEND: str = "diffusers"     # diffusers | comfyui | sglang
    INFERENCE_URL: str = "http://127.0.0.1:8188"
    QUANTIZATION: str = "int8"                # bf16 | int8 | int4 | gguf-q4_k_m
    MAX_CONCURRENCY: int = 1                  # 单机默认串行
    INFERENCE_TIMEOUT: int = 600              # 单任务超时（秒）

    # ── 上传校验 ──────────────────────────────────────────
    MAX_IMAGE_COUNT: int = 9
    MAX_VIDEO_COUNT: int = 3
    MAX_AUDIO_COUNT: int = 3
    MAX_TOTAL_REFS: int = 12
    MAX_UPLOAD_SIZE_MB: int = 200

    # ── 模型规格（对齐 PRD §6.1） ────────────────────────
    SUPPORTED_RATIOS: list = field(default_factory=lambda: ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"])
    SUPPORTED_DURATIONS: list = field(default_factory=lambda: [4, 8, 10, 15])
    SUPPORTED_RESOLUTIONS: list = field(default_factory=lambda: ["768P", "2K"])
    FPS: int = 24
    AUDIO_SAMPLE_RATE: int = 32000
    MAX_PROMPT_CHARS: int = 7000

    # ── 队列 ──────────────────────────────────────────────
    TASK_RETRY_MAX: int = 1
    TASK_TIMEOUT: int = 600

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
        if env.get("MMH3_INFERENCE_BACKEND"):
            s.INFERENCE_BACKEND = env["MMH3_INFERENCE_BACKEND"]
        if env.get("MMH3_INFERENCE_URL"):
            s.INFERENCE_URL = env["MMH3_INFERENCE_URL"]
        if env.get("MMH3_QUANTIZATION"):
            s.QUANTIZATION = env["MMH3_QUANTIZATION"]
        if env.get("MMH3_MAX_CONCURRENCY"):
            s.MAX_CONCURRENCY = max(1, int(env["MMH3_MAX_CONCURRENCY"]))
        return s


settings = Settings.from_env()
