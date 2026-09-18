#!/usr/bin/env python3
"""Dump 官方 H3 三工作流的 API 结构（去假节点），供注入参数用。开发辅助。

DEV-ONLY：依赖外部 ComfyUI 安装目录（batch_workflow_generator 工具与官方工作流）。
默认读取本机 aki-v3 安装；其他机器请用环境变量 COMFYUI_ROOT 指向你的 ComfyUI 根目录。
"""
import json
import os
import sys

_COMFY_ROOT = os.environ.get("COMFYUI_ROOT", r"C:\Users\Doro\APP\ComfyUI-aki-v3")
sys.path.insert(0, os.path.join(_COMFY_ROOT, "tool"))
from batch_workflow_generator import load_workflow_json, extract_api_prompt


def dump(t):
    d = load_workflow_json(
        os.path.join(_COMFY_ROOT, "ComfyUI", "user", "default", "workflows",
                     f"video_minimax_h3_{t}.json"))
    api = extract_api_prompt(d)
    api = {nid: n for nid, n in api.items()
           if n.get("class_type") not in ("MarkdownNote", "Note", "Reroute")}
    print("=" * 20, t, "=", len(api), "nodes")
    for nid, n in api.items():
        inp = n.get("inputs", {})
        conn = {k: v for k, v in inp.items() if isinstance(v, list) and len(v) >= 2}
        own = {k: v for k, v in inp.items() if k not in conn}
        print(f"  #{nid} {n.get('class_type')}")
        if own:
            print(f"      own: {json.dumps(own, ensure_ascii=False)[:260]}")
        if conn:
            print(f"      conn: {json.dumps(conn, ensure_ascii=False)[:200]}")


if __name__ == "__main__":
    for task in (sys.argv[1:] or ["t2v", "i2v", "r2v"]):
        dump(task)
