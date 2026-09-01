#!/usr/bin/env python3
"""
scripts/check_config_refs.py — 配置-实现一致性门禁（MiniMax-H3-lite 适配版）

根因：安全评估 M1 指出「配置幻觉（Phantom Control）」——``config.py`` 的
``@dataclass Settings`` 字段若由环境变量（``MMH3_*``）覆盖却从未被代码真实应用，
即「声明了但没人读」的假控制（如 ``MMH3_HOST`` 写入 ``settings.HOST``，但 uvicorn
启动硬编码 ``127.0.0.1``，``settings.HOST`` 从未被读取）。

本仓库无 ``config.yaml`` / pydantic，配置为 ``@dataclass Settings``，故门禁做轻量
MiniMax 适配：

1. 解析 ``backend/config.py`` 的 ``Settings`` 字段与 ``from_env()`` 的
   环境变量→字段映射；
2. 对每个可由环境变量覆盖的字段，断言其在 ``backend/`` 或 ``scripts/`` 中
   「被真实应用」：
   - ``backend/`` 中出现 ``settings.<field>`` 的读取（Load）；或
   - ``scripts/`` 中出现对应 ``MMH3_*`` 环境变量的读取（启动层落地，如
     ``uvicorn --host``）。
3. 未被应用的字段判 ``[FAIL]``（保留字段进 allowlist）。

任一缺失以非零退出码终止，作为 CI 门禁。

用法：
    python scripts/check_config_refs.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PY = ROOT / "backend" / "config.py"
BACKEND_DIR = ROOT / "backend"
SCRIPTS_DIR = ROOT / "scripts"

# 保留字段：由环境变量覆盖但目前仅作预留 / 透传，尚未在代码中消费。
# 这些字段若日后变为安全相关，须从 allowlist 移除并补消费点 + 门禁覆盖。
_ALLOWLIST: set[str] = {
    # 保留：Comfy 内核源码目录，暂无自动拉起实现
    "COMFY_SOURCE_DIR",
    # 保留：H3 模型各组件文件名默认值（fl2va/ref2va/clip/vae_video/vae_audio）。
    # 当前推理实际只用 settings.MODEL_PATH/MODEL_NAME，这些组件名仅作 h3.spec 默认值，
    # 暂未接线到推理调用；覆盖 MMH3_MODEL_* 当前无效果（已知功能限制，非安全控制）。
    "MODEL_FL2VA",
    "MODEL_REF2VA",
    "MODEL_CLIP",
    "MODEL_VAE_VIDEO",
    "MODEL_VAE_AUDIO",
}

errors: list[str] = []


def _py_files(base: Path) -> list[Path]:
    files: list[Path] = []
    if not base.exists():
        return files
    for path in base.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path.name.startswith("_"):
            continue
        files.append(path)
    return sorted(files)


def collect_settings_fields() -> set[str]:
    """返回 Settings 数据类的字段名集合。"""
    if not CONFIG_PY.exists():
        return set()
    tree = ast.parse(CONFIG_PY.read_text(encoding="utf-8"))
    fields: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields.add(stmt.target.id)
                elif isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            fields.add(t.id)
    return fields


def collect_env_map() -> dict[str, str]:
    """返回 {MMH3_ENV_VAR: settings_attr}，从 from_env() 提取。

    覆盖两种写法：
      - ``if env.get("MMH3_HOST"): s.HOST = env["MMH3_HOST"]``
      - ``for env_key, attr in (("MMH3_MODEL_FL2VA", "MODEL_FL2VA"), ...):
             if env.get(env_key): setattr(s, attr, env[env_key])``
    """
    if not CONFIG_PY.exists():
        return {}
    tree = ast.parse(CONFIG_PY.read_text(encoding="utf-8"))
    env_map: dict[str, str] = {}

    # 1) 直接赋值：s.ATTR = env[...] / int(env[...])
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            # 目标形如 s.HOST（Attribute + Store）
            tgt = node.targets[0] if node.targets else None
            if (
                isinstance(tgt, ast.Attribute)
                and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "s"
            ):
                attr = tgt.attr
                # 右值来自 env.get("MMH3_X") 或 env["MMH3_X"]
                rhs = node.value
                key = _env_key_from(rhs)
                if key:
                    env_map[key] = attr

    # 2) 元组循环：for env_key, attr in (("MMH3_X", "ATTR"), ...): setattr(s, attr, ...)
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        # 迭代对象必须是元组字面量
        iter_node = node.iter
        if not isinstance(iter_node, (ast.Tuple, ast.List)):
            continue
        for elt in iter_node.elts:
            if not isinstance(elt, (ast.Tuple, ast.List)) or len(elt.elts) != 2:
                continue
            k, a = elt.elts
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and isinstance(a, ast.Constant) and isinstance(a.value, str):
                if k.value.startswith("MMH3_"):
                    env_map[k.value] = a.value

    return env_map


def _env_key_from(node: ast.AST) -> str | None:
    """从 env.get("MMH3_X") / env["MMH3_X"] 提取环境变量名。"""
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "get" and len(node.args) >= 1:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                return a0.value
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Index):
            sl = sl.value
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return sl.value
    return None


def is_read_as_settings_attr(attr: str, files: list[Path]) -> bool:
    """backend/ 中是否出现 settings.<attr> 的读取（Load 上下文）。"""
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            if node.attr != attr:
                continue
            if not isinstance(node.ctx, ast.Load):
                continue
            base = node.value
            # base 为 settings（Name）或 xx.settings（Attribute）
            if isinstance(base, ast.Name) and base.id == "settings":
                return True
            if isinstance(base, ast.Attribute) and base.attr == "settings":
                return True
    return False


def is_env_read_in_scripts(env_key: str, files: list[Path]) -> bool:
    """scripts/ 中是否读取对应 MMH3_* 环境变量（启动层落地）。"""
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            # os.environ.get("X") / os.getenv("X") / getenv("X")
            fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if fname in ("get", "getenv") and len(node.args) >= 1:
                a0 = node.args[0]
                if isinstance(a0, ast.Constant) and a0.value == env_key:
                    # .get 必须作用在 os.environ / env 上
                    if fname == "get":
                        if isinstance(f.value, ast.Attribute) and f.value.attr == "environ":
                            return True
                        if isinstance(f.value, ast.Name) and f.value.id in ("env", "os"):
                            return True
                    else:  # getenv
                        return True
            # 下标：os.environ["X"]
            if isinstance(node, ast.Subscript):
                pass
        # 也扫描 os.environ["X"] 下标
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                sl = node.slice
                if isinstance(sl, ast.Index):
                    sl = sl.value
                if isinstance(sl, ast.Constant) and sl.value == env_key:
                    v = node.value
                    if isinstance(v, ast.Attribute) and v.attr == "environ":
                        return True
    return False


def main() -> int:
    if not CONFIG_PY.exists():
        print(f"[FAIL] 找不到 {CONFIG_PY}")
        return 1
    fields = collect_settings_fields()
    env_map = collect_env_map()
    print(f"[INFO] Settings 字段 {len(fields)} 个；可由环境变量覆盖的字段 {len(env_map)} 个")
    if not env_map:
        print("[WARN] 未从 from_env() 解析到任何 MMH3_* 环境变量映射，请检查脚本逻辑")

    backend_files = _py_files(BACKEND_DIR)
    script_files = _py_files(SCRIPTS_DIR)

    unconsumed: list[str] = []
    for env_key, attr in sorted(env_map.items()):
        applied_backend = is_read_as_settings_attr(attr, backend_files)
        applied_launch = is_env_read_in_scripts(env_key, script_files)
        if applied_backend or applied_launch:
            where = "backend" if applied_backend else "scripts(启动层)"
            print(f"[INFO] {env_key} -> settings.{attr} 已应用（{where}）")
        elif attr in _ALLOWLIST:
            print(f"[WARN] {env_key} -> settings.{attr} 未应用，但属保留字段（allowlist），跳过")
        else:
            unconsumed.append(f"{env_key} -> settings.{attr}")

    for item in unconsumed:
        errors.append(
            f"环境变量 {item} 声明了覆盖，但 settings.{item.split(' -> ')[1]} "
            f"从未在 backend/ 被读取、也未在 scripts/ 启动层落地（幽灵控制 / 假安全感）"
        )

    if errors:
        print("\n[FAIL] 配置-实现一致性门禁未通过：")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("[PASS] 所有可由环境变量覆盖的 Settings 字段均被真实应用（无幽灵控制）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
