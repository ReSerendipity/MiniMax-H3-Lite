#!/bin/sh
# 启用本仓库的 .githooks（克隆后执行一次即可）
# 之后钩子源码统一由 .githooks/ 提供，改动即时生效，无需再复制文件。
#
# 只读自检模式（不写任何配置）：
#   sh .githooks/install.sh --check
# core.hooksPath 属本地配置、不随克隆传播，故新克隆/换机后钩子默认全部失效；
# 本模式让「钩子没装上」成为一条可检测、可判定退出码的显式状态，而非无声失败。
if [ "${1:-}" = "--check" ]; then
    CURRENT="$(git config core.hooksPath 2>/dev/null)"
    if [ "$CURRENT" = ".githooks" ]; then
        echo "[hooks] 已启用：core.hooksPath=$CURRENT"
        exit 0
    fi
    echo "[hooks] 未启用：core.hooksPath=${CURRENT:-<未设置>}" >&2
    echo "[hooks] 该配置不随克隆传播。启用：sh .githooks/install.sh" >&2
    echo "[hooks] 影响：pre-commit（密钥/大文件/完整性清单）、commit-msg 与 prepare-commit-msg（DCO 签名）、" >&2
    echo "        pre-push（gitleaks + 本地预检）在当前仓库不会执行。" >&2
    exit 1
fi
git config core.hooksPath .githooks
echo "已启用 .githooks：core.hooksPath=$(git config core.hooksPath)"
echo ""
echo "已生效钩子："
echo "  pre-commit          框架可用则走 pre-commit，否则走轻量检查+根目录守卫"
echo "  pre-push            执行 precheck.ps1（无则退回根目录守卫）"
echo "  prepare-commit-msg  自动补 DCO 签名（幂等）"
echo "  commit-msg          DCO 硬校验 + 规范软提示"
echo "  post-merge/-checkout 依赖清单变更提醒"
