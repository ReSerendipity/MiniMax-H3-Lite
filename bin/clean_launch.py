"""
clean_launch.py — 启动加固（对齐兄弟项目 Image_MultiModel / TTS_MultiModel 风格）

安全启动 MM·H3 工作台：
- 自动检测并使用 WinPython / 系统 CUDA Python（家族共享约定）
- 检查 Python 版本与依赖
- 设置环境变量（离线模型读取、PyTorch 显存分配）
- 启动后端 FastAPI（默认 18080）+ 前端静态服务器（默认 8080）
- 服务就绪后自动打开浏览器
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# ── 项目根目录 ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = Path(__file__).resolve().parent


# ── WinPython 自动检测（对齐家族约定）────────────────────────
# 优先项目内 WPy64，其次兄弟项目共享 WinPython，再系统级 CUDA Python，
# 最后回退到当前 Python。
def find_winpython():
    """查找带 CUDA 的 python.exe 路径"""
    # 1. 项目内 WinPython
    for wpy_dir in PROJECT_ROOT.glob("WPy64-*"):
        py = wpy_dir / "python" / "python.exe"
        if py.exists():
            return str(py)
    # 2. 兄弟项目共享 WinPython（Seedvr2 / TTS_MultiModel / Image_MultiModel）
    for ref in (
        Path(r"C:\Users\Doro\Seedvr2\WPy64-312101\python\python.exe"),
        Path(r"C:\Users\Doro\TTS_MultiModel\WPy64-312101\python\python.exe"),
        Path(r"C:\Users\Doro\Image_MultiModel\WPy64-312101\python\python.exe"),
    ):
        if ref.exists():
            return str(ref)
    # 3. 系统级 CUDA Python（含 cu13x PyTorch，推理可用）
    for sys_py in (
        Path(r"C:\Python312\python.exe"),
        Path(r"C:\Users\Doro\APP\ComfyUI-aki-v3\python\python.exe"),
    ):
        if sys_py.exists():
            try:
                code = subprocess.run(
                    [str(sys_py), "-c", "import torch; assert torch.cuda.is_available()"],
                    capture_output=True, timeout=30,
                )
                if code.returncode == 0:
                    return str(sys_py)
            except Exception:
                pass
    # 4. 回退到当前 Python
    return sys.executable


# ── 环境变量（对齐家族约定）──────────────────────────────────
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("MODELSCOPE_OFFLINE", "1")
os.environ.setdefault("COMFYUI_DISABLE_UPDATE_CHECK", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
# 工作目录
os.chdir(str(PROJECT_ROOT))


def check_python_version():
    """检查 Python 版本 ≥ 3.10"""
    if sys.version_info < (3, 10):
        print(f"[ERROR] Python 3.10+ required, got {sys.version}")
        sys.exit(1)
    print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"[OK] Python executable: {sys.executable}")


def check_dependencies():
    """检查后端依赖（缺失则按 requirements.txt 安装）"""
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic": "pydantic",
        "multipart": "python-multipart",
    }
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"[WARN] Missing packages: {', '.join(missing)}")
        print("Installing from requirements.txt ...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")]
        )
        print("[OK] Dependencies installed")
    else:
        print("[OK] All dependencies present")


def wait_port(port: int, timeout: int = 120) -> bool:
    """等待端口就绪"""
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(1)
    return False


def launch():
    """启动前端 + 后端"""
    print("\n" + "=" * 60)
    print("  MM·H3 工作台 — Launching...")
    print("=" * 60)

    check_python_version()
    check_dependencies()

    # 确保数据目录存在（config.py 已兜底，这里再次确认）
    for d in ["data", "uploads", "assets"]:
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(PROJECT_ROOT))

    # 端口（环境变量可覆盖，与 config.py 约定一致）
    backend_port = int(os.environ.get("MMH3_PORT", "18080"))
    frontend_port = 8080

    # ── 启动后端 FastAPI ───────────────────────────────────
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", str(backend_port)],
        cwd=str(PROJECT_ROOT),
    )
    print(f"[INFO] 后端启动中: http://127.0.0.1:{backend_port} (PID {backend_proc.pid})")

    # ── 启动前端静态服务器（node server.js，无 Node 时用 Python http.server 兜底）──
    frontend_proc = None
    server_js = PROJECT_ROOT / "server.js"
    node = shutil.which("node")
    if node and server_js.exists():
        frontend_proc = subprocess.Popen([node, "server.js"], cwd=str(PROJECT_ROOT))
        print(f"[INFO] 前端启动中(Node): http://localhost:{frontend_port} (PID {frontend_proc.pid})")
    else:
        # 兜底：Python 内置静态服务器（零依赖）
        frontend_proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(frontend_port), "--bind", "127.0.0.1"],
            cwd=str(PROJECT_ROOT),
        )
        print(f"[INFO] 前端启动中(Python http.server): http://localhost:{frontend_port} (PID {frontend_proc.pid})")

    # ── 等待后端就绪后自动打开浏览器 ──────────────────────
    if wait_port(backend_port, timeout=120):
        time.sleep(2)
        webbrowser.open(f"http://localhost:{frontend_port}")
        print(f"[INFO] 服务就绪，已打开 http://localhost:{frontend_port}")
    else:
        print("[WARN] 等待后端就绪超时，请手动打开 http://localhost:" + str(frontend_port))

    # 保持前台运行，等待后端退出
    try:
        if backend_proc:
            backend_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in (backend_proc, frontend_proc):
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass


if __name__ == "__main__":
    # 若找到的 CUDA Python 与当前运行的不同，则重启为它（对齐家族约定）
    wpy = find_winpython()
    if os.path.abspath(wpy) != os.path.abspath(sys.executable):
        print(f"[INFO] Relaunching with CUDA Python: {wpy}")
        os.execv(wpy, [wpy, __file__])
    else:
        launch()
