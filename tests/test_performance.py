"""MM·H3 工作台 - 基础性能测试

使用 pytest-benchmark 测量关键 API 的响应时间。
注意：这些测试需要真实的数据库和一定的系统负载，
在 CI 环境中可能被跳过（通过标记）。

运行方式:
    pytest tests/test_performance.py -v --benchmark-only
    pytest tests/test_performance.py -v -m "not slow"  # 跳过性能测试

由于环境差异，这些测试仅记录性能数据，不设硬性门槛。
"""
import sys
import time
from pathlib import Path

import pytest

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app


# 标记所有性能测试为 slow，默认跳过
pytestmark = pytest.mark.slow


class TestAPIPerformance:
    """API 响应时间基准测试"""
    
    @pytest.fixture(scope="class")
    def client(self):
        """每个测试类共享一个 client"""
        with TestClient(app) as c:
            yield c
    
    @pytest.fixture(scope="class")
    def test_project(self, client):
        """创建测试项目供性能测试使用"""
        r = client.post("/api/projects", json={"name": "性能测试项目"})
        pid = r.json()["id"]
        yield pid
        client.delete(f"/api/projects/{pid}")
    
    def test_health_endpoint_latency(self, client, benchmark):
        """健康检查端点响应时间基准"""
        def _call():
            return client.get("/api/health")
        
        result = benchmark(_call)
        assert result.status_code == 200
    
    def test_list_projects_latency(self, client, benchmark):
        """项目列表端点响应时间基准"""
        def _call():
            return client.get("/api/projects")
        
        result = benchmark(_call)
        assert result.status_code == 200
    
    def test_create_project_latency(self, client, benchmark):
        """创建项目端点响应时间基准"""
        def _call():
            return client.post("/api/projects", json={"name": f"性能测试_{time.time()}"})
        
        result = benchmark(_call)
        assert result.status_code == 200
        # 清理创建的项目
        pid = result.json()["id"]
        client.delete(f"/api/projects/{pid}")
    
    def test_list_shots_latency(self, client, test_project, benchmark):
        """镜头列表端点响应时间基准"""
        def _call():
            return client.get(f"/api/projects/{test_project}/shots")
        
        result = benchmark(_call)
        assert result.status_code == 200


class TestDatabasePerformance:
    """数据库操作性能测试"""
    
    def test_new_id_generation(self, benchmark):
        """ID 生成响应时间基准"""
        from backend.database import new_id
        
        def _call():
            return new_id("test_")
        
        result = benchmark(_call)
        assert result.startswith("test_")
    
    def test_row_to_dict_conversion(self, benchmark):
        """行转字典响应时间基准"""
        from backend.database import row_to_dict
        import sqlite3
        
        # 创建模拟 row
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE test (id TEXT, name TEXT, data TEXT)")
        conn.execute("INSERT INTO test VALUES ('1', 'test', '{\"key\": \"value\"}')")
        row = conn.execute("SELECT * FROM test").fetchone()
        
        def _call():
            return row_to_dict(row)
        
        result = benchmark(_call)
        assert result["id"] == "1"
        assert result["name"] == "test"
        
        conn.close()


class TestSpecPerformance:
    """规格层计算性能测试"""
    
    def test_frames_for_duration(self, benchmark):
        """帧数计算响应时间基准"""
        from h3 import spec as h3
        
        def _call():
            return h3.frames_for_duration(8)
        
        result = benchmark(_call)
        assert result == 192
    
    def test_resolution_for(self, benchmark):
        """分辨率计算响应时间基准"""
        from h3 import spec as h3
        
        def _call():
            return h3.resolution_for("16:9", multiple=2)
        
        result = benchmark(_call)
        assert result[0] == 1344 and result[1] == 768
