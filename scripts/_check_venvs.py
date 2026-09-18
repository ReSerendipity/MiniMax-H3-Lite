import os
import subprocess  # nosec B404

# DEV-ONLY 运维工具：默认检查本机开发目录（C:\Users\Doro）下的兄弟项目。
# 克隆到其他机器时请设置 DEV_REPO_ROOT 指向项目根目录，否则请勿直接运行。
_DEV_ROOT = os.environ.get("DEV_REPO_ROOT", r"C:\Users\Doro")

projects = {
    os.path.join(_DEV_ROOT, "SeedVR2-lite"): [
        "diffusers", "safetensors", "omegaconf", "mediapy",
        "huggingface_hub", "onnx", "cv2", "rotary_embedding_torch",
    ],
    os.path.join(_DEV_ROOT, "TTS_MultiModel"): [
        "funasr", "modelscope", "jieba", "librosa", "numba",
        "umap_learn", "soxr", "soundfile", "torch_complex",
        "protobuf", "omegaconf", "hydra",
    ],
    os.path.join(_DEV_ROOT, "Image_MultiModel"): [
        "diffusers", "clip_anytorch", "numpy", "huggingface_hub",
        "safetensors", "PIL", "cv2",
    ],
}


for proj, mods in projects.items():
    py = os.path.join(proj, ".venv", "Scripts", "python.exe")
    name = os.path.basename(proj)
    print("=====", name, "====")
    if not os.path.exists(py):
        print("  NO VENV")
        continue
    cmd = ("import importlib.util;"
           "mods=%r;"
           "[print(('OK  ' if importlib.util.find_spec(m) else 'MISS'), m) for m in mods]" % mods)
    r = subprocess.run([py, "-c", cmd], capture_output=True, text=True)  # nosec B603
    print(r.stdout, end="")
    if r.stderr.strip():
        print("  stderr:", r.stderr.strip().splitlines()[-1])
