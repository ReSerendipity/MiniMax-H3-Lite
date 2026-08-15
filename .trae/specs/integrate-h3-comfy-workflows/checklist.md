# Checklist

- [x] 框架无关任务规格层提供 t2va / fl2va / ref2va 类型、`mode → task_type` 映射、模型文件名常量与 ref 分组规范
- [x] 帧长公式与官方 Math Expression 一致（4s→107、8s→192、10s→243、15s→362 帧）
- [x] 分辨率规范：768 短边；diffusers 取偶、ComfyUI 32 倍数；均上限 768×1344
- [x] 默认 diffusers 后端（无需 ComfyUI）正确构造 t2va / fl2va / ref2va 输入（image / last_image / ref_images / ref_videos / ref_audios，num_frames 走网格公式）
- [x] ComfyUI 可选执行器按任务类型构建与官方模板一致的 API prompt，参考素材上传并注入，结果经 `/view` 下载（兼容远程）
- [x] 旧式 CheckpointLoaderSimple / EmptyH3LatentVideo / KSampler(euler) 硬编码工作流已移除
- [x] 后端引擎注册表列出可用引擎（diffusers 本地 / comfyui 外部 / sglang 未实现），含元数据与激活态
- [x] 运行时配置持久化：`POST /api/engine/switch` 切换并持久化，`run_inference` 即时生效（env 为最高优先级）
- [x] `GET /api/engines`、`GET/POST /api/system/settings` 端点可用
- [x] `/api/health` 增加 `backend` 与 `backend_requires_external` 字段
- [x] 前端状态栏 `ENGINE` 改为可点击切换器（下拉列表 + 激活态 + 外部服务标注），切换即时更新
- [x] 任务队列、资产落盘/缩略帧、队列状态机、对外 API 契约不变（diffusers 默认后端不回归）
- [x] generations.py 对 first_frame/last_frame/first_last/ref 模式做参考素材校验并返回明确错误
- [x] 一致性测试通过（规格层与三份官方 JSON 对齐）
- [x] 引擎切换冒烟测试通过（列表、切换持久化、健康检查字段）
- [x] tests/test_api_smoke.py 全部通过（无回归）