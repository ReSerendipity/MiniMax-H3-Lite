"""业务服务层（后端服务设计评估 P1-1 落地）。

写路径业务逻辑自 routers 收口至此：路由只留 FastAPI 参数绑定与响应包装，
校验/幂等/落库/状态机在 service 实现。导入风格与 routers/*.py 一致：把 backend
目录放入 sys.path 后扁平导入，保证运行态与 pytest 命中同一模块实例（双形态
教训：切勿混用 backend.services.* 与 services.* 两种导入路径，否则 monkeypatch
会打在被测代码不引用的副本上）。
"""
