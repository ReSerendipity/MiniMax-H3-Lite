"""进程内轻量运行时状态（无 DB 依赖），供 /api/health 暴露真实就绪度。

运维稳定性评估发现：原 ``GET /api/health`` 仅回显静态配置（engine/model/quantization），
不含「模型是否已实际加载完成」「队列深度」等就绪信号 → healthy ≠ 可推理。
本模块保存首次成功推理后的 ``model_loaded`` 标志，由 queue_manager 在任务成功后置位。

后端服务设计评估 P1-3（2026-10-11）：新增超时孤儿推理线程计数——Python 线程不可取消，
推理超时后线程残留占用 GPU 槽；进程内计数该孤儿数，供 /api/health 暴露与
queue_manager 槽位守卫（孤儿存在时 fail-fast 拒绝新推理，提示重启回收）。
"""
import threading

MODEL_LOADED = False

# 超时孤儿推理线程计数（线程安全，进程生命周期内单调递增；重启后归零）
_ORPHAN_INFERENCE_COUNT = 0
_orphan_lock = threading.Lock()


def mark_model_loaded() -> None:
    """标记模型已就绪（首次成功推理后调用）。"""
    global MODEL_LOADED
    MODEL_LOADED = True


def is_model_loaded() -> bool:
    """模型是否已完成过一次成功推理（粗粒度就绪标志）。"""
    return MODEL_LOADED


def mark_orphan_inference() -> None:
    """标记一个超时孤儿推理线程（推理超时后由 queue_manager 调用）。"""
    global _ORPHAN_INFERENCE_COUNT
    with _orphan_lock:
        _ORPHAN_INFERENCE_COUNT += 1


def orphan_inference_count() -> int:
    """当前未回收的超时孤儿推理线程数（重启后归零）。"""
    with _orphan_lock:
        return _ORPHAN_INFERENCE_COUNT


def reset_orphan_inference() -> None:
    """清零孤儿计数（测试用/运维排查用；正常路径只在进程重启时自然归零）。"""
    global _ORPHAN_INFERENCE_COUNT
    with _orphan_lock:
        _ORPHAN_INFERENCE_COUNT = 0
