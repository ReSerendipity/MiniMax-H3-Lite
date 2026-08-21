import os, subprocess

projects = {
    r"C:\Users\Doro\SeedVR2-lite": ["diffusers", "safetensors", "omegaconf", "mediapy",
                                     "huggingface_hub", "onnx", "cv2", "rotary_embedding_torch"],
    r"C:\Users\Doro\TTS_MultiModel": ["funasr", "modelscope", "jieba", "librosa", "numba",
                                       "umap_learn", "soxr", "soundfile", "torch_complex",
                                       "protobuf", "omegaconf", "hydra"],
    r"C:\Users\Doro\Image_MultiModel": ["diffusers", "clip_anytorch", "numpy", "huggingface_hub",
                                          "safetensors", "PIL", "cv2"],
}

for proj, mods in projects.items():
    py = os.path.join(proj, ".venv", "Scripts", "python.exe")
    name = os.path.basename(proj)
    print("=====", name, "====")
    if not os.path.exists(py):
        print("  NO VENV"); continue
    cmd = ("import importlib.util;"
           "mods=%r;"
           "[print(('OK  ' if importlib.util.find_spec(m) else 'MISS'), m) for m in mods]" % mods)
    r = subprocess.run([py, "-c", cmd], capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr.strip():
        print("  stderr:", r.stderr.strip().splitlines()[-1])