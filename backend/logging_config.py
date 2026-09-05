"""统一日志配置：在默认控制台之外，落盘到 logs/backend.log（滚动）。

运维稳定性评估发现：此前 backend 仅用 ``logging.getLogger(__name__)``，无任何落盘，
崩溃/断电后无事后证据（checkpoint 除外）。本模块在进程启动早期为 root logger 追加一个
RotatingFileHandler，使关键报错、traceback、checkpoint 恢复等信息可回放。

幂等：重复调用不会重复添加 handler；保留默认 StreamHandler（控制台仍可用）。
"""
import logging
import logging.handlers

from config import settings


def configure_logging(level: int = logging.INFO) -> None:
    """为 root logger 追加 RotatingFileHandler（logs/backend.log）。

    Args:
        level: 落盘最低级别，默认 INFO。
    """
    logs_dir = settings.BASE_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "backend.log"

    root = logging.getLogger()
    for h in root.handlers:
        if getattr(h, "_mmh3_log", False):
            return  # 已配置，避免重复

    fh = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh._mmh3_log = True  # type: ignore[attr-defined]  # 标记，便于幂等检测
    fh.setLevel(level)
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.addHandler(fh)

    # 确保 INFO 能到达落盘 handler：root logger 默认级别常为 WARNING/NOTSET，
    # 不调整会让 INFO 在 logger 层被丢弃（handler 即便存在也收不到）。
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    logging.getLogger(__name__).info("日志已落盘到 %s（滚动 5MB x 5，崩溃后可回放）", log_file)
