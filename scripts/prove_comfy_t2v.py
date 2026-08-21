#!/usr/bin/env python3
"""一次性验证：把 aki 自带官方 H3 t2v 工作流通过 ComfyUI HTTP API 跑通，出 mp4。

用途：证明「MiniMax-H3-lite 用 comfy 后端 + ComfyUI」这条路能真正生成视频。
"""
import json
import sys
import time
import urllib.request
import urllib.error

CN = "http://127.0.0.1:8188"


def submit(prompt_graph):
    body = json.dumps({"prompt": prompt_graph}).encode()
    req = urllib.request.Request(CN + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()}


def wait(prompt_id, timeout=900):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{CN}/history/{prompt_id}", timeout=10) as r:
                h = json.loads(r.read().decode())
            if prompt_id in h:
                entry = h[prompt_id]
                st = entry.get("status", {})
                if st.get("completed"):
                    return True, entry.get("outputs", {})
                if st.get("status_str") == "error":
                    return False, st
        except Exception:
            pass
        time.sleep(2)
    return False, "timeout"


def main():
    # 用 aki 自带转换工具把 editor 工作流转成 API
    sys.path.insert(0, r"C:\Users\Doro\APP\ComfyUI-aki-v3\tool")
    from batch_workflow_generator import load_workflow_json, extract_api_prompt

    d = load_workflow_json(
        r"C:\Users\Doro\APP\ComfyUI-aki-v3\ComfyUI\user\default\workflows\video_minimax_h3_t2v.json")
    api = extract_api_prompt(d)
    # 剔除前端假节点（MarkdownNote），它们不是可执行算子
    api = {nid: n for nid, n in api.items()
           if n.get("class_type") not in ("MarkdownNote", "Note", "Reroute")}
    print(f"[1] API nodes (after strip): {len(api)}")

    # 覆盖 prompt/seed，用官方默认图
    for nid, n in api.items():
        if n.get("class_type") == "MiniMaxH3ImageToVideo":
            n["inputs"]["prompt"] = "integrated_multimodal_description: [Shot 1] A small cat walking on a beach at dusk, cinematic.\n\noverall_soundscape: Gentle waves and soft breeze."
        if n.get("class_type") == "RandomNoise":
            n["inputs"]["noise_seed"] = 42
        if n.get("class_type") == "ResolutionSelector":
            n["inputs"]["megapixels"] = 0.4  # 最小档，控显存/时长

    print("[2] submitting...")
    r = submit(api)
    if "prompt_id" not in r:
        print("[FAIL] submit error:", r)
        return 1
    pid = r["prompt_id"]
    print("[3] prompt_id:", pid)
    ok, outputs = wait(pid)
    if ok:
        print("[OK] completed. outputs:")
        print(json.dumps(outputs, ensure_ascii=False, default=str)[:2000])
        return 0
    print("[FAIL] not completed:", outputs)
    return 1


if __name__ == "__main__":
    sys.exit(main())