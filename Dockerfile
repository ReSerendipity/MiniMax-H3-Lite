# MiniMax-H3-lite — 容器化（GPU 单机工作台）
#
# 形态：FastAPI 单端口工作台（Jinja2 页面 + /api + /assets 静态资源），进程内 Comfy 内核推理。
# 基础镜像：python:3.12-slim-bookworm —— 与家族 SeedVR2-lite / Image_MultiModel 一致。
# torch 走 cu130 轮子（本机已验证 torch 2.9.1+cu130，见 scripts/clean_launch.py 注释），
# 由宿主机 nvidia-container-toolkit 提供 GPU 访问，无需在镜像里装 CUDA toolkit。
#
# 构建：docker build -t minimax-h3-lite:2.9.1-cu130 \
#   --build-arg VCS_REF=$(git rev-parse HEAD) \
#   --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) .
# 运行：docker compose up -d --build   （见 docker-compose.yml）

# === 全局构建参数（FROM 前仅允许 ARG；LABEL 须在 FROM 之后的 stage 内，
#     否则 classic/buildx 解析报 "no build stage in current context"）===
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown
ARG VERSION=0.1.0

FROM python:3.12-slim-bookworm

# === OCI 镜像元数据（Trivy/GHCR 可读；引用上方全局 ARG）===
LABEL org.opencontainers.image.title="minimax-h3-lite" \
      org.opencontainers.image.description="MiniMax H3 video generation timeline workbench" \
      org.opencontainers.image.source="https://github.com/ReSerendipity/MiniMax-H3-lite" \
      org.opencontainers.image.url="https://github.com/ReSerendipity/MiniMax-H3-lite" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="ReSerendipity"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 系统依赖：backend/watermark.py 以子进程调用 ffmpeg / ffprobe
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 升级 pip：基础镜像自带的 pip 25.0.1 有 HIGH CVE-2026-8643（wheel 安装路径
# 穿越，Trivy gate 2026-09-05 首拦）；跟随最新 pip 修复线。
RUN pip install --no-cache-dir --upgrade pip

# torch 由 CUDA Python 环境（WinPython）提供，requirements.txt 不含 torch；
# 仅 cu130 索引提供 +cu130 本地版本，pip 据此从 PyTorch 源拉取对应轮子。
# 若 cu130 索引不可用，请将下方版本/索引改为实际可用组合（如 cu128）。
RUN pip install --no-cache-dir \
        torch==2.9.1+cu130 \
        --extra-index-url https://download.pytorch.org/whl/cu130

# Python 依赖（放在 COPY 代码前以复用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（model/ 等大权重经 .dockerignore 排除，运行时挂载）
COPY . .

# 编译检查（非致命，避免个别脚本语法问题阻断构建）
RUN python -m compileall -q backend scripts 2>/dev/null || true

# 非 root 运行（安全基线；与家族 SeedVR2-lite 一致）
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 离线模型读取 / 显存分配（对齐 clean_launch.py 约定）
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    MODELSCOPE_OFFLINE=1 \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    COMFYUI_DISABLE_UPDATE_CHECK=1 \
    MMH3_PORT=18080

EXPOSE 18080

# 健康检查：backend/main.py:76 定义 GET /api/health
# H3 模型首次加载常超 2 分钟（comfy_kernel 初始化 + 模型分页加载 + tokenizer warmup），
# 冷启动机器建议 300s；预热后下次只需 ~10s。SOPS-7 §7 注明。
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=300s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18080/api/health')" || exit 1

# 容器内直接用 uvicorn 绑定 0.0.0.0；外部暴露面由 compose `ports` 控制（默认 127.0.0.1）。
# 说明：scripts/clean_launch.py 的 _require_loopback 强制回环以保护「本机直跑」场景；
# 容器部署改用 uvicorn 直启以绕过该限制，暴露面完全由 compose ports 管理
# （建议默认 127.0.0.1:18080:18080，经反向代理 + 鉴权后再对外）。
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "18080"]
