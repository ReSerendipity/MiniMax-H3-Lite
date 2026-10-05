"""desktop_launch.py — 桌面壳专用启动入口（由 Tauri 壳拉起，勿手动运行）

启动契约（与 desktop/src-tauri/src/python_process.rs 双向约定，对齐 TTS_MultiModel）：
- ``--host/--port`` 必填：端口由壳经 find_free_port 预先抓取后传入，本脚本不再探测；
- 不调用 ``webbrowser.open``（壳的 WebView 即浏览器）；
- stdout/stderr 归壳接管（重定向到 logs/desktop_python_*.log）；
- 开头打印「监听端口: N」行，供装后从安装日志读取动态端口（发版周期阶段 3 断言用）；
- 依赖缺失时按 requirements.txt 自动安装（复用 clean_launch.check_dependencies）；
- 不做 uvicorn reload；进程内 uvicorn.run，壳 taskkill 进程树即可整体回收。

解释器选择不在此处：壳侧解析链（runtime → MMH3_DESKTOP_PYTHON → .venv →
WinPython → 兄弟项目 → 系统 CUDA Python → MMH3_EXTRA_PYTHON → PATH）见
desktop/src-tauri/src/python_process.rs。
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# backend 包与 clean_launch 启动器工具可导入（clean_launch 复用其版本/依赖/回环校验）
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# 环境变量先于 backend 导入设置（对齐 clean_launch 模块级约定）
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("MODELSCOPE_OFFLINE", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.chdir(str(PROJECT_ROOT))

from clean_launch import _require_loopback, check_dependencies, check_python_version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MM·H3 工作台桌面壳启动入口")
    parser.add_argument("--host", required=True, help="绑定主机（由壳传入，必须回环地址）")
    parser.add_argument("--port", required=True, type=int, help="绑定端口（由壳传入的空闲端口）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    host = _require_loopback(args.host)

    check_python_version()
    check_dependencies()

    for d in ("data", "uploads", "logs"):
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)

    print("-" * 60)
    print("  模型许可: MiniMax H3 Community License（详见 NOTICE / MODEL_SETUP_GUIDE.md）")
    print("-" * 60)
    print(f"监听端口: {args.port}")

    import uvicorn

    uvicorn.run("backend.main:app", host=host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
