"""
MM·H3 工作台 — ComfyUI 可选执行器
基于框架无关任务规格层（backend/h3/spec.py）构建与官方三份模板一致的 API 格式 prompt，
处理参考素材上传与结果 /view 下载。
ComfyUI 仅为可选后端；默认 diffusers 后端不依赖本模块。
"""
import json
import time
import uuid
import tempfile
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

from config import settings
from settings_store import resolve as resolve_setting
from h3 import spec as h3


def build_prompt(task: dict) -> dict:
    """
    构建 ComfyUI API 格式 prompt（node id → {class_type, inputs}）。
    task 关键字段：task_type / unet_model / clip_model / vae_video_model / vae_audio_model /
    prompt / width / height / length / seed / first_frame / last_frame /
    ref_images / ref_videos / ref_audios / sampler_name / scheduler / steps / denoise /
    save_prefix / ref_image_size / load_video_node / load_audio_node。
    """
    n: dict = {}
    n["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": task["unet_model"], "weight_dtype": h3.UNET_WEIGHT_DTYPE}}
    n["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": task["clip_model"], "type": h3.CLIP_TYPE, "device": "default"}}
    n["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": task["vae_video_model"]}}
    n["4"] = {"class_type": "VAELoader", "inputs": {"vae_name": task["vae_audio_model"]}}
    n["5"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": task["sampler_name"]}}
    n["6"] = {"class_type": "BasicScheduler", "inputs": {"model": ["1", 0], "scheduler": task["scheduler"], "steps": task["steps"], "denoise": task["denoise"]}}
    n["7"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": task["seed"], "control_after_generate": "fixed"}}

    ttype = task["task_type"]
    if ttype in (h3.T2VA, h3.FL2VA):
        inputs = {
            "clip": ["2", 0],
            "vae": ["3", 0],
            "prompt": task["prompt"],
            "width": task["width"],
            "height": task["height"],
            "length": task["length"],
        }
        if task.get("first_frame"):
            n["30"] = {"class_type": "LoadImage", "inputs": {"image": task["first_frame"]}}
            inputs["first_frame"] = ["30", 0]
        if task.get("last_frame"):
            n["31"] = {"class_type": "LoadImage", "inputs": {"image": task["last_frame"]}}
            inputs["last_frame"] = ["31", 0]
        n["20"] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": inputs}
    else:  # ref2va
        ref_inputs = {}
        # 先建配对音轨映射：video_path -> audio_path（ComfyUI 文件名）
        pair_audio_by_video = {}
        for p in task.get("ref_video_audios", []):
            pair_audio_by_video[p["video"]] = p["audio"]
        for i, name in enumerate(task.get("ref_images", [])):
            nid = str(40 + i)
            n[nid] = {"class_type": "LoadImage", "inputs": {"image": name}}
            ref_inputs[f"ref_images.ref_image_{i}"] = [nid, 0]
        for i, name in enumerate(task.get("ref_videos", [])):
            nid = str(50 + i)
            n[nid] = {"class_type": task["load_video_node"], "inputs": {"video": name}}
            ref_inputs[f"ref_videos.ref_video_{i}"] = [nid, 0]
            # 按下标对齐补 ref_video_audios.ref_video_audio_{i}
            audio_name = pair_audio_by_video.get(name)
            if audio_name:
                anid = str(55 + i)
                n[anid] = {"class_type": task["load_audio_node"], "inputs": {"audio": audio_name}}
                ref_inputs[f"ref_video_audios.ref_video_audio_{i}"] = [anid, 0]
        for i, name in enumerate(task.get("ref_audios", [])):
            nid = str(60 + i)
            n[nid] = {"class_type": task["load_audio_node"], "inputs": {"audio": name}}
            ref_inputs[f"ref_audios.ref_audio_{i}"] = [nid, 0]
        inputs = {
            "clip": ["2", 0],
            "vae": ["3", 0],
            "audio_vae": ["4", 0],
            "prompt": task["prompt"],
            "width": task["width"],
            "height": task["height"],
            "length": task["length"],
            "ref_image_size": task["ref_image_size"],
            **ref_inputs,
        }
        n["20"] = {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": inputs}

    n["8"] = {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["20", 0]}}
    n["9"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["7", 0], "guider": ["8", 0], "sampler": ["5", 0], "sigmas": ["6", 0], "latent_image": ["20", 1]}}
    n["10"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}}
    n["11"] = {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["9", 0], "vae": ["4", 0]}}
    n["12"] = {"class_type": "CreateVideo", "inputs": {"images": ["10", 0], "audio": ["11", 0], "fps": h3.FPS, "bit_depth": 8}}
    n["13"] = {"class_type": "SaveVideo", "inputs": {"video": ["12", 0], "filename_prefix": task["save_prefix"], "format": "auto", "codec": "auto"}}
    return n


def _multipart_body(fields: list[tuple[str, str]], filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = "----MMH3" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for k, v in fields:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    chunks.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        'Content-Type: application/octet-stream\r\n\r\n'.encode()
    )
    chunks.append(data)
    chunks.append(f'\r\n--{boundary}--\r\n'.encode())
    return b"".join(chunks), boundary


def upload_file(base: str, local_path: str, filename: str) -> str:
    """上传素材到 ComfyUI（POST /upload/image，input 型），返回 ComfyUI 文件名（含 subfolder）。"""
    data = Path(local_path).read_bytes()
    body, boundary = _multipart_body([("type", "input"), ("overwrite", "true")], filename, data)
    req = urllib.request.Request(
        f"{base}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
    name = resp.get("name")
    subfolder = (resp.get("subfolder") or "").strip("/")
    if not name:
        raise RuntimeError(f"ComfyUI 上传失败: {resp}")
    return f"{subfolder}/{name}" if subfolder else name


def _download_view(base: str, filename: str, subfolder: str, ftype: str) -> str:
    """经 /view 下载结果视频到本地临时文件（兼容远程 ComfyUI）。"""
    qs = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": ftype})
    req = urllib.request.Request(f"{base}/view?{qs}")
    data = urllib.request.urlopen(req, timeout=60).read()
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name


def run_comfyui(task: dict) -> str:
    """
    执行 ComfyUI 生成并返回本地临时视频文件路径。
    流程：上传参考素材 → 构建 prompt → POST /prompt → 轮询 /history → /view 下载。
    任一环节失败即抛错（任务 failed），绝不假成功。
    """
    base = resolve_setting("inference_url", settings.INFERENCE_URL).rstrip("/")

    first_frame = upload_file(base, task["first_frame_path"], Path(task["first_frame_path"]).name) if task.get("first_frame_path") else None
    last_frame = upload_file(base, task["last_frame_path"], Path(task["last_frame_path"]).name) if task.get("last_frame_path") else None
    ref_images = [upload_file(base, p, Path(p).name) for p in task.get("ref_image_paths", [])]
    ref_videos = [upload_file(base, p, Path(p).name) for p in task.get("ref_video_paths", [])]
    ref_audios = [upload_file(base, p, Path(p).name) for p in task.get("ref_audio_paths", [])]

    # 配对音轨：上传配对音轨文件并建立 video_path(本地) -> audio_name(ComfyUI) 映射
    pair_audio_by_video_cfy = {}
    for p in task.get("ref_video_audios", []):
        cfy_name = upload_file(base, p["audio"], Path(p["audio"]).name)
        pair_audio_by_video_cfy[p["video"]] = cfy_name
    # 将配对映射中的本地路径替换为 ComfyUI 路径
    ref_video_audios_cfy = []
    for p in task.get("ref_video_audios", []):
        cfy_video = None
        for i, vp in enumerate(task.get("ref_video_paths", [])):
            if vp == p["video"]:
                cfy_video = ref_videos[i]
                break
        cfy_audio = pair_audio_by_video_cfy.get(p["video"])
        if cfy_video and cfy_audio:
            ref_video_audios_cfy.append({"video": cfy_video, "audio": cfy_audio})

    prompt = build_prompt({
        "task_type": task["task_type"],
        "unet_model": task["unet_model"],
        "clip_model": task["clip_model"],
        "vae_video_model": task["vae_video_model"],
        "vae_audio_model": task["vae_audio_model"],
        "prompt": task["prompt"],
        "width": task["width"],
        "height": task["height"],
        "length": task["num_frames"],
        "seed": task["seed"],
        "first_frame": first_frame,
        "last_frame": last_frame,
        "ref_images": ref_images,
        "ref_videos": ref_videos,
        "ref_audios": ref_audios,
        "ref_video_audios": ref_video_audios_cfy,
        "sampler_name": task.get("sampler_name") or resolve_setting("sampler", settings.SAMPLER_NAME),
        "scheduler": task.get("scheduler", h3.SCHEDULER),
        "steps": int(task.get("steps") or resolve_setting("steps", settings.STEPS)),
        "denoise": float(task.get("denoise") or resolve_setting("denoise", settings.DENOISE)),
        "save_prefix": resolve_setting("save_prefix", settings.SAVE_PREFIX),
        "ref_image_size": task.get("ref_image_size") or resolve_setting("ref_image_size", settings.REF_IMAGE_SIZE),
        "load_video_node": resolve_setting("load_video_node", settings.LOAD_VIDEO_NODE),
        "load_audio_node": resolve_setting("load_audio_node", settings.LOAD_AUDIO_NODE),
    })

    try:
        req = urllib.request.Request(
            f"{base}/prompt",
            data=json.dumps({"prompt": prompt}).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        prompt_id = resp.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI 未返回 prompt_id: {resp}")
    except Exception as e:
        raise RuntimeError(f"ComfyUI 提交失败: {type(e).__name__}: {e}") from e

    deadline = time.time() + settings.INFERENCE_TIMEOUT
    while time.time() < deadline:
        time.sleep(1.5)
        try:
            hist_req = urllib.request.Request(f"{base}/history/{prompt_id}")
            hist = json.loads(urllib.request.urlopen(hist_req, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise RuntimeError(f"ComfyUI 历史查询失败: {e}") from e
        except Exception as e:
            raise RuntimeError(f"ComfyUI 历史查询失败: {type(e).__name__}: {e}") from e

        entry = hist.get(prompt_id)
        if not entry:
            continue
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(f"ComfyUI 执行失败: {status.get('messages', [])}")
        if status.get("completed"):
            for node_out in entry.get("outputs", {}).values():
                for key in ("videos", "gifs"):
                    for item in node_out.get(key, []):
                        fname = item.get("filename")
                        if fname:
                            return _download_view(base, fname, item.get("subfolder") or "", item.get("type") or "output")
            raise RuntimeError("ComfyUI 执行完成但未找到输出视频文件")

    raise RuntimeError(f"ComfyUI 推理超时（{settings.INFERENCE_TIMEOUT}s）")
