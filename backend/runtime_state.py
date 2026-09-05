"""进程内轻量运行时状态（无 DB 依赖），供 /api/health 暴露真实就绪度。

运维稳定性评估发现：原 ``GET /api/health`` 仅回显静态配置（engine/model/quantization），
不含「模型是否已实际加载完成」「队列深度」等就绪信号 → healthy ≠ 可推理。
本模块保存首次成功推理后的 ``model_loaded`` 标志，由 queue_manager 在任务成功后置位。
"""
MODEL_LOADED = False


def mark_model_loaded() -> None:
    """标记模型已就绪（首次成功推理后调用）。"""
    global MODEL_LOADED
    MODEL_LOADED = True


def is_model_loaded() -> bool:
    """模型是否已完成过一次成功推理（粗粒度就绪标志）。"""
    return MODEL_LOADED
