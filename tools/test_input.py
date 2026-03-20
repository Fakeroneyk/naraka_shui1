"""
输入测试工具
测试键盘鼠标模拟是否在游戏中生效

使用方法:
    python tools/test_input.py

注意：运行后会在3秒后开始模拟操作，请切换到游戏窗口！
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.action.input_controller import InputController
from src.utils.humanize import random_delay


def main():
    print("=" * 40)
    print("输入模拟测试工具")
    print("3秒后开始测试，请切换到游戏窗口！")
    print("=" * 40)

    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    ctrl = InputController(mouse_sensitivity=0.8)

    print("\n[测试1] 按键测试：按W前进 1秒")
    ctrl.key_hold("w", 1000)
    time.sleep(0.5)

    print("[测试2] 跳跃测试：按Space")
    ctrl.key_press("space", delay_ms=200)
    time.sleep(0.5)

    print("[测试3] 交互测试：按E")
    ctrl.key_press("e", delay_ms=200)
    time.sleep(0.5)

    print("[测试4] 鼠标移动测试：视角右转")
    ctrl.mouse_move_relative(200, 0, smooth=True)
    time.sleep(0.5)

    print("[测试5] 鼠标移动测试：视角左转")
    ctrl.mouse_move_relative(-200, 0, smooth=True)
    time.sleep(0.5)

    print("[测试6] 鼠标点击：左键攻击")
    ctrl.mouse_click("left", delay_ms=200)
    time.sleep(0.5)

    print("[测试7] 鼠标长按：蓄力攻击 800ms")
    ctrl.mouse_hold("left", 800)
    time.sleep(0.5)

    print("[测试8] 组合键：Shift+W 疾跑 1秒")
    ctrl.keys_hold(["shift", "w"], 1000)
    time.sleep(0.5)

    print("[测试9] 技能键：按F (化气)")
    ctrl.key_press("f", delay_ms=200)
    time.sleep(0.5)

    print("[测试10] 钩索键：按Q")
    ctrl.key_press("q", delay_ms=200)

    # 安全释放所有按键
    ctrl.release_all_keys()
    print("\n✅ 测试完成！所有按键已释放")
    print("如果上述操作在游戏中无效，请检查:")
    print("  1. pydirectinput 是否正确安装")
    print("  2. 游戏窗口是否为活动窗口")
    print("  3. 是否有反作弊软件拦截了模拟输入")


if __name__ == "__main__":
    main()
