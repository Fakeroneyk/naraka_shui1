"""
永劫无间 - 征神之路「净水流深·噩梦」自动化脚本
主入口

使用方法:
    1. 先启动游戏并进入征神之路「净水流深·噩梦」
    2. 运行脚本: python -m src.main
    3. 按 Ctrl+C 停止脚本
"""
import sys
import signal
from loguru import logger

from src.brain.bot_brain import NarakaBot


def main():
    """主入口"""
    bot = NarakaBot(config_dir="config")

    # 注册Ctrl+C信号处理
    def signal_handler(sig, frame):
        logger.info("收到 Ctrl+C，正在停止...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # 初始化
    logger.info("初始化中...")
    if not bot.initialize():
        logger.error("初始化失败，请检查:")
        logger.error("  1. 游戏是否已启动并进入征神之路")
        logger.error("  2. 是否安装了所有依赖: pip install -r requirements.txt")
        logger.error("  3. YOLO模型文件是否存在（可选）")
        sys.exit(1)

    # 运行主循环
    logger.info("开始运行！按 Ctrl+C 停止...")
    logger.info("请确保游戏窗口为活动窗口")
    bot.run()


if __name__ == "__main__":
    main()

