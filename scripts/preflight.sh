#!/usr/bin/env bash
# scripts/preflight.sh — 首次 `docker compose up` 之前的宿主侧自检（Linux 部署目标）
#
# 触发场景：用户把仓库部署到 Linux 主机（不是 Windows Docker Desktop），
# 容器内 appuser(uid=1000) 要写 ./data ./uploads ./outputs 三个 bind-mount；
# 宿主机若属主不符，容器内会 Permission denied。
#
# 用法：
#   sudo ./scripts/preflight.sh
# 或先 chown 再跑（推荐用 sudo，本脚本对属主不符的目录会自动 chown -R 1000:1000）
#
# Windows 主机跑本脚本无意义（NTFS 用 ACL，不用 chown）；脚本会直接提示跳过。

set -euo pipefail

APP_UID=1000
APP_GID=1000
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# === 1. 平台守卫 ===
case "$(uname -s 2>/dev/null || echo Windows)" in
    Linux|Darwin)
        echo "[preflight] 平台: $(uname -s)"
        ;;
    *)
        echo "[preflight] 非 POSIX 平台（Windows?），跳过属主调整；请用 Docker Desktop 自动 UID 映射"
        echo "[preflight] 仍继续检查 model/ 子目录..."
        SKIP_CHOWN=1
        ;;
esac

# === 2. 准备 + chown data/uploads/outputs ===
for d in data uploads outputs; do
    path="$REPO_ROOT/$d"
    if [ ! -d "$path" ]; then
        echo "[preflight] $d/ 不存在，自动 mkdir -p"
        mkdir -p "$path"
    fi
    if [ "${SKIP_CHOWN:-0}" = "1" ]; then
        echo "[preflight] $d/ 跳过 chown（非 POSIX 平台）"
        continue
    fi
    cur_uid=$(stat -c '%u' "$path" 2>/dev/null || stat -f '%u' "$path")
    if [ "$cur_uid" = "$APP_UID" ]; then
        echo "[preflight] $d/ 已是 uid=$APP_UID ✓"
    else
        echo "[preflight] $d/ 属主为 uid=$cur_uid，chown -R $APP_UID:$APP_GID ..."
        chown -R "$APP_UID:$APP_GID" "$path"
    fi
done

# === 3. 校验 model/ 子目录 ===
model="$REPO_ROOT/model"
if [ ! -d "$model" ]; then
    echo "[FAIL] model/ 不存在 — 容器内读不到权重；请把权重放到 $model 后再 up" >&2
    exit 1
fi
echo "[preflight] 检查 model/ 子目录..."
missing=()
empty=()
for sub in diffusion_models loras text_encoders vae; do
    if [ ! -d "$model/$sub" ]; then
        missing+=("$sub")
        continue
    fi
    # du -sb 给字节数；阈值 1MB 视为"几乎空"
    size=$(du -sb "$model/$sub" 2>/dev/null | cut -f1)
    size=${size:-0}
    size_gb=$(awk -v b="$size" 'BEGIN{printf "%.2f", b/1073741824}')
    if [ "$size" -lt 1048576 ]; then
        empty+=("$sub (${size_gb}GB)")
    else
        echo "  model/$sub ✓ ${size_gb}GB"
    fi
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "[WARN] model/ 缺失子目录: ${missing[*]}" >&2
fi
if [ ${#empty[@]} -gt 0 ]; then
    echo "[WARN] model/ 以下子目录几乎为空（< 1MB）: ${empty[*]}" >&2
    echo "        容器内启动后会读不到权重；先把 .safetensors 放进对应目录" >&2
fi

# === 4. compose 文件 bind-mount 源存在性快速校验（可选） ===
if command -v python3 >/dev/null 2>&1; then
    if [ -f "$REPO_ROOT/scripts/check_compose_mounts.py" ]; then
        echo "[preflight] 跑 compose bind-mount 源存在性门禁..."
        if python3 "$REPO_ROOT/scripts/check_compose_mounts.py"; then
            echo "[preflight] compose 挂载检查通过 ✓"
        else
            echo "[FAIL] compose 里有 bind-mount 源不存在，请先修 docker-compose.yml 再 up" >&2
            exit 1
        fi
    fi
fi

echo ""
echo "[preflight] OK — 可以执行: docker compose up -d --build"
