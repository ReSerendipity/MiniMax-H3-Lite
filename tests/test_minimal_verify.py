"""
tests/test_minimal_verify.py — 最小验证脚本的映射逻辑测试（2026-09-28）

验证 scripts/minimal_verify.py 的源文件 → 测试文件映射规则是否正确。
不实际执行 pytest 命令，只测试命令构建逻辑。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# 导入被测模块（scripts/ 不在默认 Python 路径上，用 importlib 加载）
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "minimal_verify",
    SCRIPTS_DIR / "minimal_verify.py",
)
mv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mv)


class TestBackendModuleMapping:
    """backend/<module>.py → tests/test_<module>.py 映射"""

    def test_direct_module_match(self):
        """backend/watermark.py → tests/test_watermark.py"""
        changed = [PROJECT_ROOT / "backend" / "watermark.py"]
        tests = mv._backend_module_tests(changed)
        assert any("test_watermark.py" in t for t in tests)

    def test_router_maps_to_api_tests(self):
        """backend/routers/inference.py → tests/test_api_*.py"""
        changed = [PROJECT_ROOT / "backend" / "routers" / "inference.py"]
        tests = mv._backend_module_tests(changed)
        assert any("test_api_" in t for t in tests)

    def test_h3_maps_to_h3_tests(self):
        """backend/h3/spec.py → tests/test_h3_*.py"""
        changed = [PROJECT_ROOT / "backend" / "h3" / "spec.py"]
        tests = mv._backend_module_tests(changed)
        # 应该有 H3 或 comfy 相关测试
        assert any("test_h3_" in t or "test_comfy_" in t for t in tests)

    def test_nonexistent_test_not_mapped(self):
        """backend/main.py 没有 test_main.py → 不返回精确匹配"""
        changed = [PROJECT_ROOT / "backend" / "main.py"]
        tests = mv._backend_module_tests(changed)
        # main.py 没有对应的 test_main.py
        assert not any("test_main.py" in t for t in tests)

    def test_init_not_mapped(self):
        """backend/__init__.py 不应映射到 test___init__.py"""
        changed = [PROJECT_ROOT / "backend" / "__init__.py"]
        tests = mv._backend_module_tests(changed)
        assert not tests


class TestScriptMapping:
    """scripts/<name>.py → tests/test_<name>.py 映射"""

    def test_script_with_test(self):
        """scripts/check_compose_mounts.py → tests/test_check_compose_mounts.py"""
        changed = [PROJECT_ROOT / "scripts" / "check_compose_mounts.py"]
        tests = mv._script_tests(changed)
        assert any("test_check_compose_mounts.py" in t for t in tests)

    def test_script_without_test(self):
        """scripts/cleanup_garbage.py 没有对应测试 → 空列表"""
        changed = [PROJECT_ROOT / "scripts" / "cleanup_garbage.py"]
        tests = mv._script_tests(changed)
        assert not tests


class TestFrontendDetection:
    """前端变更检测"""

    def test_assets_js_detected(self):
        """assets/js/*.js 变更应被检测为前端变更"""
        changed = [PROJECT_ROOT / "assets" / "js" / "app.js"]
        assert mv._has_frontend_changes(changed)

    def test_package_json_detected(self):
        """根 package.json 变更应被检测为前端变更"""
        changed = [PROJECT_ROOT / "package.json"]
        assert mv._has_frontend_changes(changed)

    def test_backend_not_frontend(self):
        """backend/watermark.py 不应被检测为前端变更"""
        changed = [PROJECT_ROOT / "backend" / "watermark.py"]
        assert not mv._has_frontend_changes(changed)


class TestConfigDetection:
    """配置/版本变更检测"""

    def test_package_json_is_config(self):
        """package.json 是配置文件"""
        changed = [PROJECT_ROOT / "package.json"]
        assert mv._has_config_changes(changed)

    def test_version_py_is_config(self):
        """backend/version.py 是配置文件"""
        changed = [PROJECT_ROOT / "backend" / "version.py"]
        assert mv._has_config_changes(changed)

    def test_random_backend_not_config(self):
        """backend/watermark.py 不是配置文件"""
        changed = [PROJECT_ROOT / "backend" / "watermark.py"]
        assert not mv._has_config_changes(changed)


class TestBuildVerifyCommands:
    """命令构建集成测试"""

    def test_empty_changes_returns_empty(self):
        """空变更列表 → 空命令列表"""
        assert mv.build_verify_commands([]) == []

    def test_backend_change_produces_pytest(self):
        """backend 变更 → 产生 pytest 命令"""
        changed = [PROJECT_ROOT / "backend" / "watermark.py"]
        steps = mv.build_verify_commands(changed)
        assert len(steps) >= 1
        desc, cmd = steps[0]
        assert "pytest" in " ".join(cmd)

    def test_test_file_produces_direct_pytest(self):
        """测试文件变更 → 直接执行该测试"""
        changed = [PROJECT_ROOT / "tests" / "test_watermark.py"]
        steps = mv.build_verify_commands(changed)
        assert len(steps) >= 1
        desc, cmd = steps[0]
        assert "test_watermark.py" in " ".join(cmd)

    def test_comfy_kernel_excluded_externally(self):
        """comfy_kernel 变更应在调用方过滤，不在脚本内处理"""
        # 脚本本身不过滤 comfy_kernel（由 main() 过滤），这里测试底层函数
        # 传入 comfy_kernel 路径不会产生映射（不在 backend/ 下）
        changed = [PROJECT_ROOT / "comfy_kernel" / "nodes.py"]
        steps = mv.build_verify_commands(changed)
        assert not steps


class TestNoCoverageOverhead:
    """确认命令中包含 --no-cov 以加速反馈"""

    def test_pytest_commands_have_no_cov(self):
        """所有 pytest 命令都应包含 --no-cov"""
        changed = [
            PROJECT_ROOT / "backend" / "watermark.py",
            PROJECT_ROOT / "tests" / "test_database.py",
        ]
        steps = mv.build_verify_commands(changed)
        for desc, cmd in steps:
            if "pytest" in cmd[1]:  # 跳过非 pytest 命令
                assert "--no-cov" in cmd, f"命令缺少 --no-cov：{cmd}"
