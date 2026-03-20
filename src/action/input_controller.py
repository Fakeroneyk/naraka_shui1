"""
输入控制器 - 底层键盘鼠标模拟
基于 pydirectinput 实现 DirectInput 级别的输入注入
"""
import time
import ctypes
from typing import Optional
from loguru import logger

from src.utils.humanize import random_delay, relative_move_steps

try:
    import pydirectinput
    pydirectinput.PAUSE = 0.0   # 禁用内置延迟，由我们自己控制
    _INPUT_BACKEND = "pydirectinput"
except ImportError:
    pydirectinput = None
    _INPUT_BACKEND = "none"
    logger.warning("pydirectinput 未安装！键盘鼠标模拟不可用")


# Win32 SendInput 常量（备用低级方案）
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MOVE_NOCOALESCE = 0x2000


class InputController:
    """DirectInput 键盘鼠标控制器"""

    def __init__(self, mouse_sensitivity: float = 0.8):
        """
        Args:
            mouse_sensitivity: 视角旋转灵敏度系数（与游戏内设置匹配）
        """
        self._sensitivity = mouse_sensitivity
        self._held_keys: set[str] = set()   # 当前按住的按键
        logger.info("输入控制器初始化，后端: {}", _INPUT_BACKEND)

    # ─── 键盘操作 ──────────────────────────────────────────────────────

    def key_press(self, key: str, delay_ms: float = 50) -> None:
        """
        按下并释放一个按键

        Args:
            key: 按键名称（如 "w", "space", "f"）
            delay_ms: 按下后的等待时间（毫秒）
        """
        if pydirectinput is None:
            return
        try:
            pydirectinput.press(key)
            if delay_ms > 0:
                random_delay(delay_ms)
        except Exception as e:
            logger.error("key_press({}) 失败: {}", key, e)

    def key_down(self, key: str) -> None:
        """按住一个按键"""
        if pydirectinput is None:
            return
        try:
            if key not in self._held_keys:
                pydirectinput.keyDown(key)
                self._held_keys.add(key)
        except Exception as e:
            logger.error("key_down({}) 失败: {}", key, e)

    def key_up(self, key: str) -> None:
        """释放一个按键"""
        if pydirectinput is None:
            return
        try:
            pydirectinput.keyUp(key)
            self._held_keys.discard(key)
        except Exception as e:
            logger.error("key_up({}) 失败: {}", key, e)

    def key_hold(self, key: str, duration_ms: float) -> None:
        """
        按住按键一段时间后释放

        Args:
            key: 按键名称
            duration_ms: 按住时长（毫秒）
        """
        self.key_down(key)
        random_delay(duration_ms, variance_pct=0.05)
        self.key_up(key)

    def keys_hold(self, keys: list[str], duration_ms: float) -> None:
        """
        同时按住多个按键一段时间（用于组合键如 Shift+W）

        Args:
            keys: 按键列表
            duration_ms: 按住时长（毫秒）
        """
        for key in keys:
            self.key_down(key)
        random_delay(duration_ms, variance_pct=0.05)
        for key in reversed(keys):
            self.key_up(key)

    def release_all_keys(self) -> None:
        """释放所有当前按住的按键（紧急清理）"""
        for key in list(self._held_keys):
            self.key_up(key)
        self._held_keys.clear()

    # ─── 鼠标操作 ──────────────────────────────────────────────────────

    def mouse_click(self, button: str = "left", delay_ms: float = 80) -> None:
        """
        鼠标点击

        Args:
            button: "left" 或 "right"
            delay_ms: 点击后延迟
        """
        if pydirectinput is None:
            return
        try:
            if button == "left":
                pydirectinput.click(button="left")
            else:
                pydirectinput.click(button="right")
            if delay_ms > 0:
                random_delay(delay_ms)
        except Exception as e:
            logger.error("mouse_click({}) 失败: {}", button, e)

    def mouse_down(self, button: str = "left") -> None:
        """按下鼠标键"""
        if pydirectinput is None:
            return
        try:
            if button == "left":
                pydirectinput.mouseDown(button="left")
            else:
                pydirectinput.mouseDown(button="right")
        except Exception as e:
            logger.error("mouse_down({}) 失败: {}", button, e)

    def mouse_up(self, button: str = "left") -> None:
        """释放鼠标键"""
        if pydirectinput is None:
            return
        try:
            if button == "left":
                pydirectinput.mouseUp(button="left")
            else:
                pydirectinput.mouseUp(button="right")
        except Exception as e:
            logger.error("mouse_up({}) 失败: {}", button, e)

    def mouse_hold(self, button: str = "left", duration_ms: float = 800) -> None:
        """
        按住鼠标键一段时间（用于蓄力攻击）

        Args:
            button: "left" 或 "right"
            duration_ms: 按住时长（毫秒）
        """
        self.mouse_down(button)
        random_delay(duration_ms, variance_pct=0.08)
        self.mouse_up(button)

    def mouse_move_relative(self, dx: int, dy: int, smooth: bool = True) -> None:
        """
        相对移动鼠标（控制游戏视角）

        Args:
            dx: X方向偏移量（正=右）
            dy: Y方向偏移量（正=下）
            smooth: 是否平滑移动（多步）
        """
        if pydirectinput is None:
            return

        if smooth and (abs(dx) > 20 or abs(dy) > 20):
            # 拆分为多步平滑移动
            steps = relative_move_steps(dx, dy, steps=8)
            for step_dx, step_dy in steps:
                if step_dx != 0 or step_dy != 0:
                    try:
                        pydirectinput.moveRel(step_dx, step_dy)
                    except Exception:
                        pass
                    time.sleep(0.002)  # 2ms 步进间隔
        else:
            try:
                pydirectinput.moveRel(dx, dy)
            except Exception as e:
                logger.error("mouse_move_relative 失败: {}", e)

    def aim_at_screen_offset(self, offset_x: int, offset_y: int) -> None:
        """
        根据屏幕偏移量调整视角（自动瞄准辅助）

        Args:
            offset_x: 目标相对屏幕中心的X偏移（像素）
            offset_y: 目标相对屏幕中心的Y偏移（像素）
        """
        # 将屏幕偏移转换为鼠标移动量（需根据游戏灵敏度校准）
        mouse_dx = int(offset_x * self._sensitivity)
        mouse_dy = int(offset_y * self._sensitivity)
        self.mouse_move_relative(mouse_dx, mouse_dy, smooth=True)