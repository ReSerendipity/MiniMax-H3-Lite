"""从《琵琶曲_视频提示词库.md》导出 18 个可直接上传的 TXT 提示词。

每个 TXT = 一个镜头的完整 prompt（含 Negative Prompt），字符数校验 6000~7000。
用法: python scripts/export_shot_txts.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MD = ROOT / "prompt" / "琵琶曲_视频提示词库.md"
OUT_DIR = ROOT / "prompt" / "txt"

MIN_CHARS, MAX_CHARS = 6000, 7000

NEGATIVE = (
    "different face, different person, wrong identity, face changing, age change, "
    "facial drifting, identity shift, morphing face, asymmetric features, "
    "warping, jitter, motion blur on face, double exposure, ghosting, temporal flicker, "
    "cartoon, anime, illustration, anime style, bad anatomy, extra fingers, "
    "deformed hands, mutated hands, plastic skin, porcelain skin, glossy skin, "
    "modern clothes, modern buildings, modern objects, cars, electric lights, "
    "neon signs, jeans, sneakers, watermark, text artifacts, blurry, low quality, "
    "Qing dynasty, Qing dynasty clothing, Manchu hairstyle, queue hairstyle, "
    "qipao, cheongsam, mandarin collar"
)


def parse_shots(text: str) -> list[tuple[str, str, str]]:
    """返回 [(shot_no, short_name, prompt_text), ...]，按库内顺序。"""
    shots: list[tuple[str, str, str]] = []
    pattern = re.compile(r"^## (Shot \d+)（(.*?)）.*?^```\n(.*?)\n```", re.M | re.S)
    for m in pattern.finditer(text):
        shot_no, header_info, prompt = m.group(1), m.group(2), m.group(3)
        parts = header_info.split(" · ")
        short_name = parts[1] if len(parts) > 1 else shot_no
        shots.append((shot_no, short_name, prompt.strip()))
    return shots


def validate(prompt: str, shot_no: str) -> list[str]:
    problems: list[str] = []
    length = len(prompt)
    if not (MIN_CHARS <= length <= MAX_CHARS):
        problems.append(f"字符数 {length} 超出 {MIN_CHARS}~{MAX_CHARS}")
    if not prompt.startswith("integrated_multimodal_description:"):
        problems.append("缺少 integrated_multimodal_description 字段")
    if "overall_soundscape:" not in prompt:
        problems.append("缺少 overall_soundscape 字段")
    if "non_diegetic_music:" not in prompt:
        problems.append("缺少 non_diegetic_music 字段")
    if "Negative Prompt:" not in prompt:
        problems.append("缺少 Negative Prompt")
    elif NEGATIVE not in prompt:
        problems.append("Negative Prompt 与统一负面词不一致")
    if not re.search(r"Shot \d+ of 18", prompt):
        problems.append("缺少 story_context（Shot N of 18）")
    stripped = prompt.replace("never sings", "").replace("not singing", "")
    if re.search(r"\bsings?\b|\bsinging\b|vocal layer|vocal harmony", stripped):
        problems.append("疑似唱歌指令残留")
    if "<d>[Chinese]" in prompt:
        problems.append("禁止出现台词标签 <d>[Chinese]（全片零台词）")
    if re.search(r"\b(speech|dialogue|spoken line|speaks a line|says|whispers a line)\b", prompt, re.I):
        problems.append("疑似台词指令残留（全片零台词）")
    if shot_no in {"03", "05", "07", "09", "10", "15"} and not re.search(
        r"no facial detail|face not visible|no individual facial detail|not clearly visible|her face turned away|face not in frame",
        prompt,
    ):
        problems.append("远景/背影镜头缺少无人脸声明")
    return problems


def main() -> int:
    if not MD.exists():
        print(f"[ERROR] 未找到母版文件: {MD}")
        return 1
    shots = parse_shots(MD.read_text(encoding="utf-8"))
    if len(shots) != 18:
        print(f"[ERROR] 解析到 {len(shots)} 个镜头（应为 18）")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    for shot_no, short_name, prompt in shots:
        fname = f"{shot_no.replace(' ', '_')}_{short_name}.txt"
        (OUT_DIR / fname).write_text(prompt + "\n", encoding="utf-8")
        problems = validate(prompt, shot_no)
        status = "OK " if not problems else "FAIL"
        if problems:
            failed += 1
        print(f"[{status}] {fname}  {len(prompt)} 字符")
        for p in problems:
            print(f"         - {p}")
    print(f"\n导出完成: {len(shots) - failed}/{len(shots)} 通过校验 -> {OUT_DIR}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())