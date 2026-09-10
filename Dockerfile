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

# 系统依赖：backend/watermark.py 以子进程调用 ffmpeg / ffprobe。
# apt-get upgrade：基础镜像的 OS 包（如 libpcre2-8-0 10.42-1 未含 2026 安全
# 补丁）会以 HIGH 级被 Trivy gate 拦截（2026-09-05 实证 5 项 pcre2 CVE），
# 升级到 bookworm 最新补丁线一次清偿并防后续同类拦截。
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends \
        ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 升级 pip（构建工具链，越早越好）
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

# 安全升级：修依赖链 HIGH 漏洞（CVE-2025-47273 setuptools 路径穿越、
# GHSA-6v7p-g79w-8964 msgpack 越界读、CVE-2026-59890 setuptools MANIFEST 绕过）。
# ⚠ 必须位于 requirements 安装之后：requirements.txt 未 pin 这两包，传递依赖
# 解析可能把早期升级压回旧版——2026-09-05 Trivy gate 实测复拦即此因。
#
# ⚠ 另注（2026-09-05/06 Trivy gate 取证结论）：CI 门禁最终采用
# docker export 合并视图 + `trivy rootfs` 扫描并 skip pip 的 vendor SBOM
# （pip/_vendor/bom.cdx.json 内含 msgpack 1.1.2/setuptools 70.3.0 声明，
# 曾被 Trivy 误当作扫描目标组件清单）。本层保持纯净升级即可。
RUN pip install --no-cache-dir --upgrade setuptools msgpack

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

# 健康检查：backend/main.py:76 定义 GET /api/health；响应含 model_loaded 真实就绪信号。
# R1/P2-a（评估 v1.0.0 · D1-a 解析 JSON）：HEALTHCHECK 现解析 JSON 的 model_loaded 字段，
# 仅当模型已就绪才返回 0，避免「healthy ≠ 可推理」。
# 注意：模型为惰性加载（首次成功推理后置位 runtime_state.MODEL_LOADED），
# 冷启动后若无推理请求会持续 unhealthy；本仓 restart: unless-stopped 不依据 health 重启，
# 故仅影响监控直觉，不触发重启循环（见 docker-compose.yml:23）。
# H3 模型首次加载常超 2 分钟，冷启动 start-period 300s；预热后 ~10s。SOPS-7 §7。
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=300s \
    CMD python -c "import sys,json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:18080/api/health')); sys.exit(0 if d.get('model_loaded') else 1)"

# 容器内绑定地址（R3 / 问答一 方案 A 的安全落地变体）。
# 容器内 uvicorn 固定绑定 0.0.0.0——这是「部署形态下的等价安全替代」：
#   ① 暴露面完全由 docker-compose `ports` 收口（默认 127.0.0.1:18080:18080）；
#   ② compose 端口发布依赖容器内 0.0.0.0 监听（DNAT 才能投递），故不可改为 127.0.0.1，
#      否则 docker compose up 后对外端口将无响应（致命 footgun）；
#   ③ 裸机侧回环强制（scripts/clean_launch.py._require_loopback + config.py MMH3_HOST
#      fail-fast）保持不变，不可动。
# MMH3_DOCKER_BIND 为「显式、可审计」的部署意图声明（值固定 0.0.0.0）；覆盖为其他值
# 不支持（会破坏端口发布），故此处直接固定而非读取可变开关——既闭合「容器侧无对等控制」
# 的语义缺口，又规避了「默认 127.0.0.1 + 开关翻转」会令标准部署失效的反模式。
ENV MMH3_DOCKER_BIND=0.0.0.0
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "18080"]
