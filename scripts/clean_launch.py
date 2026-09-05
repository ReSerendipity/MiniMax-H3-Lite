"""
clean_launch.py — 启动加固（对齐兄弟项目 Image_MultiModel / TTS_MultiModel 风格）

安全启动 MM·H3 工作台：
- 自动检测并使用 WinPython / 系统 CUDA Python（家族共享约定）
- 检查 Python 版本与依赖
- 设置环境变量（离线模型读取、PyTorch 显存分配）
- 启动后端 FastAPI（单端口 18080：Jinja2 页面 + API + 静态资源）
- 服务就绪后自动打开浏览器
"""

import os
import socket
import subprocess  # nosec B404: 仅用于 venv torch 探测 / pip 安装 / uvicorn 拉起（固定参数，无 shell）
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
    """查找带 CUDA 的 python.exe 路径。

    优先级：项目 venv（.venv，隔离环境，torch 2.9.1+cu130 已验证）→ 项目内 WinPython
    → 兄弟项目共享 WinPython → 系统 CUDA Python → 当前 Python。
    """
    # 0. 项目 venv（推荐）：脱离 ComfyUI / 全局环境的隔离推理环境
    venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        try:
            code = subprocess.run(  # nosec B603: 固定 venv 解释器 + 固定探针参数，无不可信输入
                [str(venv_py), "-c", "import torch; assert torch.cuda.is_available()"],
                capture_output=True, timeout=30,
            )
            if code.returncode == 0:
                return str(venv_py)
        except Exception:  # nosec B110: 探测尽力而为，失败继续下一层回退
            pass
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
                code = subprocess.run(  # nosec B603: 固定解释器 + 固定探针参数，无不可信输入
                    [str(sys_py), "-c", "import torch; assert torch.cuda.is_available()"],
                    capture_output=True, timeout=30,
                )
                if code.returncode == 0:
                    return str(sys_py)
            except Exception:  # nosec B110: 探测尽力而为，失败继续下一层回退
                pass
    # 4. 回退到当前 Python
    return sys.executable


# ── 环境变量（对齐家族约定）──────────────────────────────────
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("MODELSCOPE_OFFLINE", "1")
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
        subprocess.check_call(  # nosec B603: 当前解释器 + 锁定清单安装，无不可信输入
            [sys.executable, "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")]
        )
        print("[OK] Dependencies installed")
    else:
        print("[OK] All dependencies present")


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _require_loopback(host: str) -> str:
    """强制 host 为回环地址；非回环直接失败（防止 0.0.0.0 公网暴露）。

    对齐兄弟项目 Image_MultiModel 的 ``ServerConfig.host_must_be_loopback`` 校验器：
    MMH3_HOST 若为回环则原样返回，否则启动即失败（fail-fast），不让错误配置静默生效。
    """
    h = (host or "").strip()
    if h not in _LOOPBACK_HOSTS:
        raise SystemExit(
            f"[ERROR] MMH3_HOST 必须为回环地址（127.0.0.1 / localhost / ::1），得到: {h!r}。"
            " 禁止绑定 0.0.0.0 以免服务暴露到公网。"
        )
    return h


def find_available_port(start_port: int, host: str = "127.0.0.1", max_attempts: int = 200) -> int:
    """从 start_port 向上查找第一个可用的端口（bind 探测）。

    对齐家族项目（TTS_MultiModel / Seedvr2 / Image_MultiModel）的自动换端口策略：
    默认端口被占用时向上顺延，避免启动直接报错退出。

    Args:
        start_port: 起始端口号（含）。
        host: 绑定主机，默认 127.0.0.1。
        max_attempts: 最大尝试次数，默认 200（最多尝试到 start_port+199）。

    Returns:
        int: 找到的第一个可用端口。

    Raises:
        OSError: 指定范围内未找到可用端口。
    """
    for offset in range(max_attempts):
        candidate = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, candidate))
                return candidate
            except OSError:
                continue
    raise OSError(f"在 {start_port}~{start_port + max_attempts} 范围内未找到可用端口")


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
    """启动后端（单端口：FastAPI 直出页面 + API + 静态资源）"""
    print("\n" + "=" * 60)
    print("  MM·H3 工作台 — Launching...")
    print("=" * 60)

    check_python_version()
    check_dependencies()

    # 确保数据目录存在（config.py 已兜底，这里再次确认）
    for d in ["data", "uploads", "assets"]:
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(PROJECT_ROOT))

    # 主机（MMH3_HOST 可覆盖；强制回环，禁止 0.0.0.0 公网暴露——对齐家族安全红线）
    # 修复安全评估 M1：此前硬编码 127.0.0.1 且 settings.HOST 从未被消费，
    # 导致 MMH3_HOST 是「声明了但没人读」的假控制。现改为读取并强制回环校验。
    host = _require_loopback(os.environ.get("MMH3_HOST", "127.0.0.1"))

    # 端口（环境变量 MMH3_PORT 可覆盖起始端口；被占用时自动向上顺延）。
    # 默认值 18080 与 backend/config.py 的 Settings.PORT 同源同值（单端口工作台），
    # 改动端口须两处同步，避免启动链路与 Settings 口径分裂。
    backend_start = int(os.environ.get("MMH3_PORT", "18080"))
    backend_port = find_available_port(backend_start, host=host)
    if backend_port != backend_start:
        print(f"[INFO] 后端端口 {backend_start} 已被占用，自动切换到 {backend_port}")

    # ── 启动后端 FastAPI（单端口：页面模板 + /assets + /api） ──────────
    backend_proc = subprocess.Popen(  # nosec B603: 当前解释器 + 固定 uvicorn 参数，无不可信输入
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", host, "--port", str(backend_port)],
        cwd=str(PROJECT_ROOT),
    )
    print(f"[INFO] 后端启动中: http://127.0.0.1:{backend_port} (PID {backend_proc.pid})")

    # ── 等待后端就绪后自动打开浏览器 ──────────────────────
    if wait_port(backend_port, timeout=120):
        time.sleep(2)
        webbrowser.open(f"http://localhost:{backend_port}")
        print(f"[INFO] 服务就绪，已打开 http://localhost:{backend_port}")
    else:
        print("[WARN] 等待后端就绪超时，请手动打开 http://localhost:" + str(backend_port))

    # 保持前台运行，等待后端退出
    try:
        if backend_proc:
            backend_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if backend_proc:
            try:
                backend_proc.terminate()
            except Exception:  # nosec B110: 退出清理尽力而为，失败不影响主流程
                pass


if __name__ == "__main__":
    # 若找到的 CUDA Python 与当前运行的不同，则重启为它（对齐家族约定）
    wpy = find_winpython()
    if os.path.abspath(wpy) != os.path.abspath(sys.executable):
        print(f"[INFO] Relaunching with CUDA Python: {wpy}")
        os.execv(wpy, [wpy, __file__])  # nosec B606: 重启到探测到的 CUDA 解释器，路径来自本地探测而非用户输入
    else:
        launch()
