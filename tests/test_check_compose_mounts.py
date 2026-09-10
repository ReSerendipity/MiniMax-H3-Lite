"""scripts/check_compose_mounts.py 的三态判定单测。

背景：bind-mount 源里有 5 个目录全部被 .gitignore 排除（vendored 内核与运行时目录），
GitHub 托管 runner 的干净 checkout 里它们必然不存在。旧实现一律判 FAIL，
导致 trivy job 在构建镜像之前就红；而本机（目录真实存在）却常年全绿。
这里把"缺失"拆成 OK / SKIP / FAIL 三态，且不依赖环境探测的隐式约定。
"""
import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def mod():
    path = PROJECT_ROOT / "scripts" / "check_compose_mounts.py"
    spec = importlib.util.spec_from_file_location("check_compose_mounts", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_existing_source_is_ok(mod, tmp_path):
    d = tmp_path / "model"
    d.mkdir()
    assert mod.classify_mount(exists=True, ignored=True, in_ci=True) == "OK"
    assert mod.classify_mount(exists=True, ignored=False, in_ci=False) == "OK"


def test_missing_gitignored_source_in_ci_is_skip(mod):
    assert mod.classify_mount(exists=False, ignored=True, in_ci=True) == "SKIP"


def test_missing_gitignored_source_locally_is_fail(mod):
    # 本地缺 comfy_kernel/ 意味着 native 引擎根本跑不起来，必须报红
    assert mod.classify_mount(exists=False, ignored=True, in_ci=False) == "FAIL"


def test_missing_tracked_source_always_fail(mod):
    # GOTCHAS #21 的原始事故：./config.yaml 既不存在也没被忽略 → 任何环境都要红
    assert mod.classify_mount(exists=False, ignored=False, in_ci=True) == "FAIL"
    assert mod.classify_mount(exists=False, ignored=False, in_ci=False) == "FAIL"


def test_is_ignored_returns_false_for_path_outside_repo(mod, tmp_path):
    assert mod.is_ignored(tmp_path.parent / "elsewhere", tmp_path) is False


def test_is_ignored_detects_gitignored_dir(mod, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("comfy_kernel/\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    target = repo / "comfy_kernel"
    assert mod.is_ignored(target, repo) is True
    assert mod.is_ignored(repo / "backend", repo) is False


def test_skip_does_not_short_circuit_image_subcheck(tmp_path):
    """D8 回归：全部 bind-mount 被 SKIP 时，image-ref 副检查仍须执行。

    旧 main() 的 [SKIP] 分支写成 `return 0` 提前返回，导致只要有任何挂载被
    SKIP（CI 里 5/5 全 SKIP 正是这种情形），后面的 services.<svc>.image: 钉版
    副检查就被彻底短路，镜像 :latest 告警丢声。这里构造"所有源缺失且被
    gitignore + CI=true"（→ 全部 SKIP、无 FAIL）的场景，断言输出里仍出现
    副检查段落；修复前此断言必红。用真实 CLI 子进程跑，锁死控制流而非纯函数。
    """
    import os
    import shutil
    import subprocess
    import sys

    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(
        PROJECT_ROOT / "scripts" / "check_compose_mounts.py",
        repo / "scripts" / "check_compose_mounts.py",
    )
    # 以 LF 写出，避免依赖 git autocrlf：两条目录专属模式，磁盘上都不存在
    with open(repo / ".gitignore", "w", newline="\n", encoding="utf-8") as fh:
        fh.write("comfy_kernel/\nmodel/\n")
    (repo / "docker-compose.yml").write_text(
        "services:\n"
        "  app:\n"
        "    image: minimax-demo\n"
        "    volumes:\n"
        "      - ./comfy_kernel:/app/comfy_kernel:ro\n"
        "      - ./model:/app/model\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    env = dict(os.environ)
    env["CI"] = "true"
    r = subprocess.run(
        [sys.executable, "scripts/check_compose_mounts.py", "--file", "docker-compose.yml"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        # 子进程内脚本执行 sys.stdout.reconfigure(encoding="utf-8")，输出为 UTF-8 字节；
        # text=True 的默认解码按父进程 locale（Windows CI runner 为 cp1252），
        # 解码中文会抛 UnicodeDecodeError → stdout=None。必须显式指定同构解码。
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )
    out = r.stdout
    # 前提：确为 SKIP（而非 FAIL），否则测不到短路分支
    assert "[SKIP]" in out, out
    assert "[FAIL]" not in out, out
    assert r.returncode == 0, out + r.stderr
    # 关键：SKIP 之后 image-ref 副检查没有被短路，仍照常打印
    assert "副检查" in out, out
    assert "services.app.image:" in out, out
    assert "WARN" in out, out
