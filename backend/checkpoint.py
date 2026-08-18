"""断点续跑管理器（路线图 #7，模式移植自 TTS_MultiModel 的 TaskCheckpoint）。

任务执行到一半被中断（用户关闭窗口 / 断电 / OOM 崩溃）时，已完成的进度不会白费。
Checkpoint 记录任务进度，重启后 ``queue_manager.resume_unfinished_tasks`` 会扫描
``generation_tasks``（database.py 建表）中残留的 pending/processing 任务并重新入队。

存储格式: ``{checkpoint_dir}/{task_id}.json``（原子写入）。

适配 MiniMax-H3-lite：checkpoint 文件按 task_id 键控，进度状态与 SQLite
``generation_tasks`` 表对应（单任务 = 单镜头，total=1，completed_items/remaining
记录镜头 id）；默认目录 ``data/checkpoints``，由 config.settings.CHECKPOINT_DIR 覆盖。
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TaskCheckpoint:
    """断点续跑管理器。

    每个 checkpoint 是一个独立的 JSON 文件，存储在 ``checkpoint_dir`` 目录中。
    文件名格式: ``{task_id}.json``。
    """

    def __init__(self, checkpoint_dir: str | Path = "data/checkpoints") -> None:
        """初始化断点续跑管理器。

        Args:
            checkpoint_dir: checkpoint 文件存储目录路径（默认 data/checkpoints）。
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        """获取指定 task_id 的 checkpoint 文件路径（防路径穿越）。"""
        safe_id = task_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self.checkpoint_dir / f"{safe_id}.json"

    def save(self, task_id: str, progress_state: dict[str, Any]) -> None:
        """保存/更新 checkpoint（原子写入，失败仅 warning 不阻塞任务执行）。

        Args:
            task_id: 任务唯一标识符。
            progress_state: 进度状态字典，包含：
                - engine: 推理引擎名称
                - total: 子任务（镜头）总数
                - completed_items: 已完成的子任务列表
                - remaining: 剩余的子任务列表
                - config: 生成配置字典
        """
        data = {
            "task_id": task_id,
            "engine": progress_state.get("engine", ""),
            "total": progress_state.get("total", 0),
            "completed": len(progress_state.get("completed_items", [])),
            "completed_items": progress_state.get("completed_items", []),
            "remaining": progress_state.get("remaining", []),
            "config": progress_state.get("config", {}),
            "updated_at": time.time(),
        }

        path = self._path(task_id)
        dir_ = str(path.parent)
        os.makedirs(dir_, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(prefix=".ckpt_", suffix=".json", dir=dir_)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(path))
            logger.debug("[Checkpoint] 已保存: %s (%s/%s)", task_id, data["completed"], data["total"])
        except Exception as e:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            logger.warning("[Checkpoint] 保存失败 %s: %s", task_id, e)

    def load(self, task_id: str) -> dict[str, Any] | None:
        """加载 checkpoint。

        Args:
            task_id: 任务唯一标识符。

        Returns:
            checkpoint 数据字典；文件不存在或解析失败时返回 None。
        """
        path = self._path(task_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.debug(
                "[Checkpoint] 已加载: %s (%s/%s)",
                task_id, data.get("completed", 0), data.get("total", 0),
            )
            return data
        except Exception as e:
            logger.warning("[Checkpoint] 加载失败 %s: %s", task_id, e)
            return None

    def remove(self, task_id: str) -> bool:
        """删除 checkpoint（任务完成后清理，失败仅 warning）。

        Args:
            task_id: 任务唯一标识符。

        Returns:
            成功删除返回 True；文件不存在或删除失败返回 False。
        """
        path = self._path(task_id)
        if not path.exists():
            return False
        try:
            path.unlink()
            logger.debug("[Checkpoint] 已删除: %s", task_id)
            return True
        except OSError as e:
            logger.warning("[Checkpoint] 删除失败 %s: %s", task_id, e)
            return False

    def list(self) -> list[dict[str, Any]]:
        """列出所有未完成的 checkpoint（completed < total）。

        Returns:
            未完成 checkpoint 的数据列表（按磁盘文件名顺序）。
        """
        results: list[dict[str, Any]] = []
        for p in sorted(self.checkpoint_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("completed", 0) < data.get("total", 0):
                    results.append(data)
            except Exception as exc:
                logger.warning("跳过损坏的 checkpoint 文件 %s: %s", p, exc)
                continue
        return results

    def should_checkpoint(self, completed_count: int, checkpoint_every: int = 5) -> bool:
        """判断是否需要写 checkpoint。

        Args:
            completed_count: 已完成的子任务（镜头）数。
            checkpoint_every: 每隔多少个子任务写一次 checkpoint（<=0 视为关闭）。

        Returns:
            是否需要写 checkpoint。
        """
        if checkpoint_every <= 0:
            return False
        return completed_count > 0 and completed_count % checkpoint_every == 0
