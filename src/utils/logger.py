"""
日志工具模块
基于 loguru 提供结构化日志支持
"""
import sys
from pathlib import Path
from loguru import logger


def setup_logger(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """
    初始化日志系统

    Args:
        log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_dir: 日志文件目录
    """
    # 清除默认处理器
    logger.remove()

    # 控制台输出（彩色格式）
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
    )

    # 文件输出（详细格式，按天轮转）
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_path / "naraka_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="00:00",      # 每天午夜轮转
        retention="7 days",    # 保留7天
        encoding="utf-8",
    )

    logger.info("日志系统初始化完成，级别: {}", log_level)


# 模块级快捷访问
__all__ = ["logger", "setup_logger"]