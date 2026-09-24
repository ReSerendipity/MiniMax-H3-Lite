#!/usr/bin/env python3
"""分支保护漂移检测 / 幂等应用（单一来源 docs/ci/branch-protection.json）。

用法：
    python scripts/apply_branch_protection.py              # 只读漂移检测（CI 用）
    python scripts/apply_branch_protection.py --apply --yes  # 幂等写入远端（需二次确认）

退出码：
    0  无漂移，或 --apply 写入并复验无漂移
    1  检测到漂移（只读模式）或写入后仍有漂移
    2  API 读取/写入失败

设计要点：
- required_signatures 不是 PUT /protection 接受的字段，它是独立子资源，
  需要走 .../protection/required_signatures 的 PUT/DELETE。
- allow_auto_merge 是仓库级设置，走 PATCH /repos/{slug}。
- required_pull_request_reviews 为 null 表示“不要求 PR 评审”；
  PUT 时原样传 null（GitHub 据此移除该子保护），比对时按“有无该块”判定。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(os.path.dirname(HERE), "docs", "ci", "branch-protection.json")

# 进入 PUT /protection 请求体的字段（required_signatures / allow_auto_merge 除外）
_PUT_FIELDS = (
    "required_status_checks",
    "required_pull_request_reviews",
    "enforce_admins",
    "required_linear_history",
    "allow_force_pushes",
    "allow_deletions",
    "block_creations",
    "required_conversation_resolution",
    "lock_branch",
    "allow_fork_syncing",
    "restrictions",
)

_REVIEW_FIELDS = (
    "dismiss_stale_reviews",
    "require_code_owner_reviews",
    "required_approving_review_count",
    "require_last_push_approval",
)

# 其余布尔型开关在 GET 响应里都是 {"enabled": bool}
_ENABLED_FLAGS = (
    ("enforce_admins", "enforce_admins"),
    ("required_linear_history", "required_linear_history"),
    ("allow_force_pushes", "allow_force_pushes"),
    ("allow_deletions", "allow_deletions"),
    ("block_creations", "block_creations"),
    ("required_conversation_resolution", "required_conversation_resolution"),
    ("lock_branch", "lock_branch"),
    ("allow_fork_syncing", "allow_fork_syncing"),
)


def gh(args):  # type: (list[str]) -> tuple[int, str, str]
    """调用 gh api，返回 (returncode, stdout, stderr)。"""
    r = subprocess.run(  # nosec B404 B603 B607 - gh 走用户已认证的固定 CLI，参数为白名单化的 API 路径
        ["gh", "api", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def load_cfg(path=CFG):  # type: (str) -> dict
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def protection_paths(cfg):  # type: (dict) -> tuple[str, str]
    slug = f"{cfg['owner']}/{cfg['repo']}"
    base = f"repos/{slug}/branches/{cfg.get('branch', 'main')}/protection"
    return slug, base


def desired_put_body(cfg):  # type: (dict) -> dict
    """由单一来源组装 PUT /protection 请求体。"""
    missing = [k for k in _PUT_FIELDS if k not in cfg]
    if missing:
        raise ValueError(f"branch-protection.json 缺少字段: {', '.join(missing)})")
    reviews = cfg["required_pull_request_reviews"]
    if reviews is not None:
        bad = [k for k in _REVIEW_FIELDS if k not in reviews]
        if bad:
            raise ValueError(f"required_pull_request_reviews 缺少字段: {', '.join(bad)}")
    return {k: cfg[k] for k in _PUT_FIELDS}


def _restrictions_empty(cur):  # type: (dict | None) -> bool
    if not cur:
        return True
    return all(not cur.get(k) for k in ("users", "teams", "apps"))


def compute_drift(cur, cfg):  # type: (dict, dict) -> list[str]
    """比对线上保护与目标配置，返回漂移字段名列表（不含 allow_auto_merge）。"""
    d = []  # type: list[str]

    rsc = cur.get("required_status_checks") or {}
    want_rsc = cfg["required_status_checks"]
    if bool(rsc.get("strict")) != bool(want_rsc["strict"]):
        d.append("strict")
    if set(rsc.get("contexts") or []) != set(want_rsc["contexts"]):
        d.append("contexts")

    cur_reviews = cur.get("required_pull_request_reviews")
    want_reviews = cfg["required_pull_request_reviews"]
    if want_reviews is None:
        if cur_reviews is not None:
            d.append("required_pull_request_reviews")
    elif cur_reviews is None or any(
        cur_reviews.get(k) != want_reviews[k] for k in _REVIEW_FIELDS
    ):
        d.append("required_pull_request_reviews")

    if bool((cur.get("required_signatures") or {}).get("enabled")) != bool(
        cfg["required_signatures"]
    ):
        d.append("required_signatures")

    for cfg_key, cur_key in _ENABLED_FLAGS:
        if bool((cur.get(cur_key) or {}).get("enabled")) != bool(cfg[cfg_key]):
            d.append(cur_key)

    if cfg["restrictions"] is None and not _restrictions_empty(cur.get("restrictions")):
        d.append("restrictions")
    # 非空 restrictions（用户/团队白名单）当前配置不使用；如需支持再补比对。

    return d


def auto_merge_drift(slug, cfg):  # type: (str, dict) -> bool
    """仓库级 allow_auto_merge 是否漂移（拉取失败按漂移处理，促使人工介入）。"""
    code, out, err = gh([f"repos/{slug}", "--jq", ".allow_auto_merge"])
    if code != 0:
        print(f"[WARN] 读取 allow_auto_merge 失败，按漂移处理: {err[:200]}")
        return True
    return (out == "true") != bool(cfg["allow_auto_merge"])


def apply_protection(cfg, body):  # type: (dict, dict) -> tuple[bool, str]
    """写入保护（PUT 主体 + signatures 子端点 + 仓库级 auto-merge）。"""
    slug, base = protection_paths(cfg)
    fd, tmp_path = tempfile.mkstemp(
        suffix=".json", prefix="_branch-protection-", dir=HERE, text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
        code, _, err = gh(["-X", "PUT", base, "--input", tmp_path])
        if code != 0:
            return False, f"PUT {base} 失败: {err[:200]}"

        if cfg["required_signatures"]:
            # 启用签名要求是独立子端点，方法为 POST（非 PUT）。
            code, _, err = gh(["-X", "POST", f"{base}/required_signatures"])
        else:
            code, _, err = gh(["-X", "DELETE", f"{base}/required_signatures"])
        # 关闭一个本就未启用的子资源会返回 404，属幂等成功。
        if code != 0 and not (not cfg["required_signatures"] and "404" in err):
            return False, f"required_signatures 写入失败: {err[:200]}"

        if cfg["allow_auto_merge"]:
            code, _, err = gh(["-X", "PATCH", f"repos/{slug}", "-F", "allow_auto_merge=true"])
            if code != 0:
                return False, f"allow_auto_merge 写入失败: {err[:200]}"
        return True, ""
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def main(argv=None):  # type: (list[str] | None) -> int
    ap = argparse.ArgumentParser(description="分支保护漂移检测 / 幂等应用")
    ap.add_argument("--apply", action="store_true", help="写入远端（默认只读检测）")
    ap.add_argument("--yes", action="store_true", help="写入的二次确认（必须与 --apply 同给）")
    a = ap.parse_args(argv)

    cfg = load_cfg()
    slug, base = protection_paths(cfg)
    body = desired_put_body(cfg)

    code, out, err = gh([base])
    if code != 0:
        print(f"[FAIL] 读取保护失败: {err[:200]}")
        return 2
    cur = json.loads(out)

    drift = compute_drift(cur, cfg)
    if auto_merge_drift(slug, cfg):
        drift.append("allow_auto_merge")

    if not drift:
        print(f"[OK] 无漂移: {slug}@{cfg.get('branch', 'main')}")
        return 0

    print(f"[DRIFT] {slug}@{cfg.get('branch', 'main')} -> {', '.join(drift)}")
    if not a.apply:
        return 1
    if not a.yes:
        print("[ABORT] 写入需同时给 --apply --yes，本次未做任何改动。")
        return 2

    ok, msg = apply_protection(cfg, body)
    if not ok:
        print(f"[FAIL] {msg}")
        return 2

    code2, out2, err2 = gh([base])
    if code2 != 0:
        print(f"[FAIL] 写入后复验读取失败: {err2[:200]}")
        return 2
    remain = compute_drift(json.loads(out2), cfg)
    if auto_merge_drift(slug, cfg):
        remain.append("allow_auto_merge")
    if remain:
        print(f"[FAIL] 写入后仍有漂移: {', '.join(remain)}")
        return 1
    print(f"[OK] 已写入并复验无漂移: {slug}@{cfg.get('branch', 'main')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
