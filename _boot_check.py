import os, subprocess

# 各项目「启动时必然会 import」的核心模块（从注册表/入口推断）
checks = {
    r"C:\Users\Doro\Image_MultiModel": [
        ("clip_anytorch", "CLIP 安全检测（requirements 明确要求）")
    ],
    r"C:\Users\Doro\TTS_MultiModel": None,  # 无强需项，用整体启动验证
    r"C:\Users\Doro\SeedVR2-lite": None,
}

for proj, extra in checks.items():
    py = os.path.join(proj, ".venv", "Scripts", "python.exe")
    name = os.path.basename(proj)
    print("=====", name, "====")
    if extra:
        for m, desc in extra:
            cmd = "import importlib.util;print('PRESENT' if importlib.util.find_spec('%s') else 'MISSING')" % m
            r = subprocess.run([py, "-c", cmd], capture_output=True, text=True)
            print("  ", m, "->", r.stdout.strip(), "|", desc)

# 整体启动 smoke：尝试 import 各自 app 入口，捕获首个 ImportError
boots = {
    r"C:\Users\Doro\Image_MultiModel": "app.integrated_app.app_server",
    r"C:\Users\Doro\TTS_MultiModel": "app.integrated_app.app_server",
    r"C:\Users\Doro\SeedVR2-lite": "app.clean_launch",
}
for proj, mod in boots.items():
    py = os.path.join(proj, ".venv", "Scripts", "python.exe")
    r = subprocess.run([py, "-c", "import %s; print('BOOT_OK')" % mod],
                       capture_output=True, text=True, cwd=proj)
    line = "BOOT_OK" if r.returncode == 0 else ("FAIL: " + (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else r.stdout.strip().splitlines()[-1]))
    print(" ", os.path.basename(proj), "import", mod, "->", line)