"""
截图采集工具
用途：在游戏中截取训练数据（用于YOLO模型训练标注）

使用方法:
    python tools/capture_screenshots.py --interval 2 --output data/screenshots

按 'q' 退出，按 's' 手动截一张
"""
import os
import sys
import time
import argparse
import keyboard  # 需要安装: pip install keyboard

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision.screen_capture import ScreenCapture
from src.utils.window_manager import WindowManager

try:
    import cv2
    import numpy as np
except ImportError:
    print("请安装: pip install opencv-python numpy")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="游戏截图采集工具")
    parser.add_argument("--interval", type=float, default=0, help="自动截图间隔(秒)，0=手动模式")
    parser.add_argument("--output", type=str, default="data/screenshots", help="截图保存目录")
    parser.add_argument("--window", type=str, default="永劫无间", help="游戏窗口标题")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # 初始化
    wm = WindowManager(args.window)
    if not wm.find_window():
        print(f"未找到窗口: {args.window}")
        return

    capture = ScreenCapture(region=wm.get_capture_region())
    if not capture.initialize():
        print("截图初始化失败")
        return

    print("=" * 40)
    print(f"截图工具已启动 | 保存到: {args.output}")
    if args.interval > 0:
        print(f"自动截图模式: 每 {args.interval} 秒一张")
    else:
        print("手动模式: 按 's' 截图, 按 'q' 退出")
    print("=" * 40)

    count = 0
    last_capture_time = 0

    while True:
        # 检查退出
        if keyboard.is_pressed('q'):
            print(f"\n退出，共截取 {count} 张")
            break

        now = time.time()

        should_capture = False
        if args.interval > 0 and (now - last_capture_time >= args.interval):
            should_capture = True
        elif keyboard.is_pressed('s'):
            should_capture = True
            time.sleep(0.3)  # 防止连续触发

        if should_capture:
            frame = capture.grab()
            if frame is not None:
                filename = f"screenshot_{int(now)}_{count:04d}.png"
                filepath = os.path.join(args.output, filename)
                # RGB -> BGR for OpenCV
                bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                cv2.imwrite(filepath, bgr)
                count += 1
                last_capture_time = now
                print(f"[{count}] 已保存: {filename} ({frame.shape[1]}x{frame.shape[0]})")

        time.sleep(0.05)

    capture.release()


if __name__ == "__main__":
    main()
