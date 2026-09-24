"""scripts/apply_branch_protection.py 的单测（不触网，gh() 全部打桩）。

回归保护的历史缺陷：
- sys.exit(1) 未缩进在 if 内 -> 读取后无条件退出，漂移检测/写入永不达；
- 裸 return 让 [DRIFT] 与 --apply 块成为死代码；
- apply 成功也返回 1；
- docs/ci/branch-protection.json 的 contexts 为空却无人校验，
  与线上 8 条必需检查长期漂移。
"""
import importlib.util
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CFG_PATH = PROJECT_ROOT / "docs" / "ci" / "branch-protection.json"


@pytest.fixture(scope="module")
def mod():
    path = PROJECT_ROOT / "scripts" / "apply_branch_protection.py"
    spec = importlib.util.spec_from_file_location("apply_branch_protection", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def cfg(mod):
    return mod.load_cfg(str(CFG_PATH))


def live_protection_from_cfg(cfg):
    """按 cfg 构造一份与 GET /protection 同形的“线上无漂移”响应。"""
    reviews = cfg["required_pull_request_reviews"]
    cur = {
        "required_status_checks": {
            "strict": cfg["required_status_checks"]["strict"],
            "contexts": list(cfg["required_status_checks"]["contexts"]),
        },
        "required_pull_request_reviews": reviews,
        "required_signatures": {"enabled": cfg["required_signatures"]},
        "enforce_admins": {"enabled": cfg["enforce_admins"]},
        "required_linear_history": {"enabled": cfg["required_linear_history"]},
        "allow_force_pushes": {"enabled": cfg["allow_force_pushes"]},
        "allow_deletions": {"enabled": cfg["allow_deletions"]},
        "block_creations": {"enabled": cfg["block_creations"]},
        "required_conversation_resolution": {
            "enabled": cfg["required_conversation_resolution"]
        },
        "lock_branch": {"enabled": cfg["lock_branch"]},
        "allow_fork_syncing": {"enabled": cfg["allow_fork_syncing"]},
        "restrictions": None,
    }
    return cur


# ---------- 配置单一来源自身的完整性 ----------

def test_shipped_json_matches_live_eight_contexts(cfg):
    """JSON 必须显式登记线上 8 条必需检查，不允许再为空。"""
    contexts = cfg["required_status_checks"]["contexts"]
    assert len(contexts) == 8
    assert "lint" in contexts and "security-scan" in contexts
    assert cfg["required_status_checks"]["strict"] is False


def test_shipped_json_reviews_null_reflects_live(cfg):
    """线上没有 required_pull_request_reviews 子块，单一来源必须如实写 null。"""
    assert cfg["required_pull_request_reviews"] is None
    assert cfg["enforce_admins"] is True


# ---------- desired_put_body ----------

def test_put_body_excludes_subresources(cfg, mod):
    body = mod.desired_put_body(cfg)
    assert "required_signatures" not in body  # 独立 POST/DELETE 子端点
    assert "allow_auto_merge" not in body  # 仓库级 PATCH 设置
    assert body["required_pull_request_reviews"] is None
    assert body["enforce_admins"] is True
    assert body["required_status_checks"]["contexts"] == cfg["required_status_checks"][
        "contexts"
    ]


def test_put_body_raises_on_missing_field(mod):
    bad = {"required_status_checks": {"strict": False, "contexts": []}}
    with pytest.raises(ValueError):
        mod.desired_put_body(bad)


def test_put_body_raises_on_incomplete_reviews(cfg, mod):
    cfg["required_pull_request_reviews"] = {"dismiss_stale_reviews": True}
    with pytest.raises(ValueError):
        mod.desired_put_body(cfg)


# ---------- compute_drift ----------

def test_no_drift_when_live_equals_cfg(cfg, mod):
    assert mod.compute_drift(live_protection_from_cfg(cfg), cfg) == []


def test_contexts_drift_detected(cfg, mod):
    cur = live_protection_from_cfg(cfg)
    cur["required_status_checks"]["contexts"].pop()
    assert "contexts" in mod.compute_drift(cur, cfg)


def test_strict_drift_detected(cfg, mod):
    cur = live_protection_from_cfg(cfg)
    cur["required_status_checks"]["strict"] = True
    assert "strict" in mod.compute_drift(cur, cfg)


def test_reviews_presence_drift_both_directions(cfg, mod):
    # 线上有评审块、配置要求 null -> 漂移
    cur = live_protection_from_cfg(cfg)
    cur["required_pull_request_reviews"] = {
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
        "required_approving_review_count": 1,
        "require_last_push_approval": False,
    }
    assert "required_pull_request_reviews" in mod.compute_drift(cur, cfg)

    # 配置要求评审块、线上缺失 -> 漂移
    cfg["required_pull_request_reviews"] = {
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
        "required_approving_review_count": 1,
        "require_last_push_approval": False,
    }
    cur2 = live_protection_from_cfg(cfg)
    cur2["required_pull_request_reviews"] = None
    assert "required_pull_request_reviews" in mod.compute_drift(cur2, cfg)


def test_signatures_and_flags_drift(cfg, mod):
    cur = live_protection_from_cfg(cfg)
    cur["required_signatures"] = {"enabled": True}
    cur["enforce_admins"] = {"enabled": False}
    d = mod.compute_drift(cur, cfg)
    assert "required_signatures" in d
    assert "enforce_admins" in d


def test_nonempty_restrictions_is_drift(cfg, mod):
    cur = live_protection_from_cfg(cfg)
    cur["restrictions"] = {"users": [{"login": "x"}], "teams": [], "apps": []}
    assert "restrictions" in mod.compute_drift(cur, cfg)


def test_auto_merge_drift(monkeypatch, cfg, mod):
    calls = []

    def fake_gh(args):
        calls.append(args)
        if args[-1] == ".allow_auto_merge":
            return (0, "true", "")
        return (1, "", "boom")

    monkeypatch.setattr(mod, "gh", fake_gh)
    assert mod.auto_merge_drift("o/r", cfg) is False
    cfg["allow_auto_merge"] = False
    assert mod.auto_merge_drift("o/r", cfg) is True

    # 读取失败按漂移处理（促人工介入），不允许静默“无漂移”
    def broken(_args):
        return (1, "", "rate limit")

    monkeypatch.setattr(mod, "gh", broken)
    assert mod.auto_merge_drift("o/r", cfg) is True


# ---------- apply_protection 调用顺序 ----------

def test_apply_sequence_disabled_signatures(monkeypatch, cfg, mod):
    calls = []

    def fake_gh(args):
        calls.append(args)
        if args[:2] == ["-X", "DELETE"] and args[2].endswith("/required_signatures"):
            return 1, "", "404 Not Found"  # 本就未启用，幂等成功
        return 0, "", ""

    monkeypatch.setattr(mod, "gh", fake_gh)
    ok, msg = mod.apply_protection(cfg, mod.desired_put_body(cfg))
    assert ok, msg
    methods = [(a[1], a[2].split("/")[-1]) for a in calls if a and a[0] == "-X"]
    assert ("PUT", "protection") in methods
    assert ("DELETE", "required_signatures") in methods
    assert ("PATCH", "MiniMax-H3-lite") in methods
    # 不能把签名要求塞进 PUT 主体之外的误调用
    assert all("required_signatures" not in a[2] or a[1] == "DELETE" for a in calls)
    # 临时 body 文件必须清掉
    assert not list(Path(mod.HERE).glob("_branch-protection-*.json"))


def test_apply_sequence_enabled_signatures(monkeypatch, cfg, mod):
    cfg["required_signatures"] = True
    calls = []

    def fake_gh(args):
        calls.append(args)
        return 0, "", ""

    monkeypatch.setattr(mod, "gh", fake_gh)
    ok, _ = mod.apply_protection(cfg, mod.desired_put_body(cfg))
    assert ok
    assert ["-X", "POST", "repos/ReSerendipity/MiniMax-H3-lite/branches/main/protection/required_signatures"] in calls


# ---------- main 端到端（打桩） ----------

def _install_fake(monkeypatch, mod, cfg, cur=None, auto_merge="true",
                  protection_read_fail=False, record=None):
    cur = cur if cur is not None else live_protection_from_cfg(cfg)

    def fake_gh(args):
        if record is not None:
            record.append(args)
        if args == ["repos/ReSerendipity/MiniMax-H3-lite/branches/main/protection"]:
            if protection_read_fail:
                return 1, "", "404 no protection"
            return 0, json.dumps(cur), ""
        if len(args) == 3 and args[1] == "--jq" and args[2] == ".allow_auto_merge":
            return 0, auto_merge, ""
        if args and args[0] == "-X":
            if args[1] == "DELETE" and args[2].endswith("/required_signatures"):
                return 1, "", "404 Not Found"
            return 0, "", ""
        return 1, "", "unexpected call: " + " ".join(args)

    monkeypatch.setattr(mod, "gh", fake_gh)


def test_main_ok_no_drift(monkeypatch, mod, cfg, capsys):
    _install_fake(monkeypatch, mod, cfg)
    assert mod.main([]) == 0
    assert "[OK]" in capsys.readouterr().out


def test_main_drift_readonly_returns_1(monkeypatch, mod, cfg):
    cur = live_protection_from_cfg(cfg)
    cur["required_status_checks"]["contexts"] = ["only-one"]
    _install_fake(monkeypatch, mod, cfg, cur=cur)
    assert mod.main([]) == 1


def test_main_read_failure_returns_2(monkeypatch, mod, cfg):
    _install_fake(monkeypatch, mod, cfg, protection_read_fail=True)
    assert mod.main([]) == 2


def _install_drift_then_converge(monkeypatch, mod, cfg, record):
    """首检漂移（缺一条 context），写入后的复验与 cfg 一致。"""
    drifted = live_protection_from_cfg(cfg)
    drifted["required_status_checks"]["contexts"] = ["lint"]
    aligned = live_protection_from_cfg(cfg)
    state = {"protection_gets": 0}

    def fake_gh(args):
        if record is not None:
            record.append(args)
        if args == ["repos/ReSerendipity/MiniMax-H3-lite/branches/main/protection"]:
            state["protection_gets"] += 1
            cur = drifted if state["protection_gets"] == 1 else aligned
            return 0, json.dumps(cur), ""
        if len(args) == 3 and args[1] == "--jq" and args[2] == ".allow_auto_merge":
            return 0, "true", ""
        if args and args[0] == "-X":
            if args[1] == "DELETE" and args[2].endswith("/required_signatures"):
                return 1, "", "404 Not Found"
            return 0, "", ""
        return 1, "", "unexpected call: " + " ".join(args)

    monkeypatch.setattr(mod, "gh", fake_gh)


def test_main_apply_without_yes_aborts(monkeypatch, mod, cfg):
    record = []
    _install_drift_then_converge(monkeypatch, mod, cfg, record)
    assert mod.main(["--apply"]) == 2
    assert not any(a and a[0] == "-X" for a in record)


def test_main_apply_happy_path_rechecks(monkeypatch, mod, cfg):
    record = []
    _install_drift_then_converge(monkeypatch, mod, cfg, record)
    assert mod.main(["--apply", "--yes"]) == 0
    writes = [a for a in record if a and a[0] == "-X"]
    assert any(a[1] == "PUT" for a in writes)
    # 保护 GET 发生两次（写前 + 写后复验）
    gets = [a for a in record if a and a[0].startswith("repos/") and a[0].endswith("/protection")]
    assert len(gets) == 2
