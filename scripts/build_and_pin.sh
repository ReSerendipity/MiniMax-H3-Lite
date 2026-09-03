#!/usr/bin/env bash
# scripts/build_and_pin.sh — Linux/macOS 端的 build + tag + digest 固化
#
# 等价于 scripts/build_and_pin.ps1（Windows PowerShell 版）；
# 唯一区别是 shell 语法不同。
#
# 用法：
#   ./scripts/build_and_pin.sh                      # 默认 tag 2.9.1-cu130
#   ./scripts/build_and_pin.sh --tag 2.9.1-cu130-rc1
#   ./scripts/build_and_pin.sh --compose-file docker-compose.dev.yml
#
# 详见 build_and_pin.ps1 注释。本文件保持极简，逻辑都委托给 docker compose + docker inspect。

set -euo pipefail

TAG="2.9.1-cu130"
COMPOSE_FILE="docker-compose.yml"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag) TAG="$2"; shift 2 ;;
        --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker 不在 PATH" >&2
    exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "ERROR: compose 文件不存在: $COMPOSE_FILE" >&2
    exit 1
fi

echo "==> docker compose build（首次约 10-20 分钟）"
docker compose -f "$COMPOSE_FILE" build

echo "==> 解析 source image..."
SOURCE_IMAGE="$(docker compose -f "$COMPOSE_FILE" config --images | head -1 | tr -d '[:space:]')"
if [ -z "$SOURCE_IMAGE" ]; then
    echo "ERROR: docker compose config --images 返回空" >&2
    exit 1
fi
echo "  source: $SOURCE_IMAGE"

TARGET_IMAGE="minimax-h3-lite:$TAG"
echo "==> docker tag $SOURCE_IMAGE $TARGET_IMAGE"
docker tag "$SOURCE_IMAGE" "$TARGET_IMAGE"

echo "==> docker inspect 拿 image ID"
IMAGE_ID="$(docker inspect --format='{{.Id}}' "$TARGET_IMAGE" | tr -d '[:space:]')"
if [[ ! "$IMAGE_ID" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    echo "ERROR: image ID 格式异常: '$IMAGE_ID'" >&2
    exit 1
fi
echo "  digest: $IMAGE_ID"

PINNED_FILE="$REPO_ROOT/docker-compose.pinned.yml"
cat > "$PINNED_FILE" <<EOF
# docker-compose.pinned.yml — digest 固化覆盖层
#
# 自动生成自 scripts/build_and_pin.sh 于 $(date -u +%Y-%m-%dT%H:%M:%SZ)
# source : $SOURCE_IMAGE
# target : $TARGET_IMAGE
# digest : $IMAGE_ID
#
# 用法：
#   docker compose -f $COMPOSE_FILE -f docker-compose.pinned.yml up -d

services:
  mmh3:
    image: ${TARGET_IMAGE}@${IMAGE_ID}
EOF
echo "==> 写入 $PINNED_FILE"

echo ""
echo "[DONE] 构建 + digest 固化完成"
echo "  启动命令："
echo "    docker compose -f $COMPOSE_FILE -f docker-compose.pinned.yml up -d"
echo "  端到端冒烟："
echo "    ./scripts/verify_image.sh   (Windows: pwsh scripts/verify_image.ps1)"
