import os
import subprocess  # nosec B404

# DEV-ONLY 运维工具：默认检查本机开发目录（C:\Users\Doro）下的兄弟项目。
# 克隆到其他机器时请设置 DEV_REPO_ROOT 指向项目根目录，否则请勿直接运行。
_DEV_ROOT = os.environ.get("DEV_REPO_ROOT", r"C:\Users\Doro")

# 各项目「启动时必然会 import」的核心模块（从注册表/入口推断）
checks = {
    os.path.join(_DEV_ROOT, "Image_MultiModel"): [
        ("clip_anytorch", "CLIP 安全检测（requirements 明确要求）")
    ],
    os.path.join(_DEV_ROOT, "TTS_MultiModel"): None,  # 无强需项，用整体启动验证
    os.path.join(_DEV_ROOT, "SeedVR2-lite"): None,
}

for proj, extra in checks.items():
    py = os.path.join(proj, ".venv", "Scripts", "python.exe")
    name = os.path.basename(proj)
    print("=====", name, "====")
    if extra:
        for m, desc in extra:
            cmd = "import importlib.util;print('PRESENT' if importlib.util.find_spec('%s') else 'MISSING')" % m
            r = subprocess.run([py, "-c", cmd], capture_output=True, text=True,
                               encoding="utf-8", errors="replace",  # nosec B603
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})  # 子进程输出强制 UTF-8，与父解码同口径
            print("  ", m, "->", r.stdout.strip(), "|", desc)

# 整体启动 smoke：尝试 import 各自 app 入口，捕获首个 ImportError
boots = {
    os.path.join(_DEV_ROOT, "Image_MultiModel"): "app.integrated_app.app_server",
    os.path.join(_DEV_ROOT, "TTS_MultiModel"): "app.integrated_app.app_server",
    os.path.join(_DEV_ROOT, "SeedVR2-lite"): "app.clean_launch",
}
for proj, mod in boots.items():
    py = os.path.join(proj, ".venv", "Scripts", "python.exe")
    r = subprocess.run([py, "-c", "import %s; print('BOOT_OK')" % mod],  # nosec B603
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=proj,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})  # 子进程输出强制 UTF-8，与父解码同口径
    line = "BOOT_OK" if r.returncode == 0 else ("FAIL: " + (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else r.stdout.strip().splitlines()[-1]))
    print(" ", os.path.basename(proj), "import", mod, "->", line)
