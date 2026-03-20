"""
移动控制模块
负责角色移动、跑步、跳跃、视角旋转
"""
import math
import time
from typing import Tuple
from loguru import logger

from src.action.input_controller import InputController
from src.utils.humanize import random_delay


class MovementController:
    """角色移动控制器"""

    def __init__(self, input_ctrl: InputController, keys_config: dict):
        """
        Args:
            input_ctrl: 输入控制器实例
            keys_config: 按键映射配置
        """
        self._input = input_ctrl
        self._keys = keys_config
        self._is_moving = False

    # ─── 基础移动 ──────────────────────────────────────────────────────

    def move_forward(self, duration_ms: float = 500) -> None:
        """向前移动"""
        self._input.key_hold(self._keys["move_forward"], duration_ms)

    def move_backward(self, duration_ms: float = 300) -> None:
        """向后移动"""
        self._input.key_hold(self._keys["move_backward"], duration_ms)

    def move_left(self, duration_ms: float = 300) -> None:
        """向左移动"""
        self._input.key_hold(self._keys["move_left"], duration_ms)

    def move_right(self, duration_ms: float = 300) -> None:
        """向右移动"""
        self._input.key_hold(self._keys["move_right"], duration_ms)

    def start_sprint_forward(self) -> None:
        """开始疾跑前进（按住Shift+W）"""
        self._input.key_down(self._keys["sprint_hold"])
        self._input.key_down(self._keys["move_forward"])
        self._is_moving = True

    def stop_movement(self) -> None:
        """停止所有移动"""
        for key in ["move_forward", "move_backward", "move_left",
                     "move_right", "sprint_hold"]:
            self._input.key_up(self._keys[key])
        self._is_moving = False

    # ─── 跳跃与闪避 ────────────────────────────────────────────────────

    def jump(self) -> None:
        """跳跃"""
        self._input.key_press(self._keys["jump"], delay_ms=100)

    def dodge_forward(self) -> None:
        """前闪"""
        self._input.keys_hold(
            [self._keys["dodge"], self._keys["move_forward"]],
            duration_ms=80
        )

    def dodge_backward(self) -> None:
        """后闪"""
        self._input.keys_hold(
            [self._keys["dodge"], self._keys["move_backward"]],
            duration_ms=80
        )

    def dodge_left(self) -> None:
        """左闪"""
        self._input.keys_hold(
            [self._keys["dodge"], self._keys["move_left"]],
            duration_ms=80
        )

    def dodge_right(self) -> None:
        """右闪"""
        self._input.keys_hold(
            [self._keys["dodge"], self._keys["move_right"]],
            duration_ms=80
        )

    def dodge_direction(self, direction: str) -> None:
        """根据方向字符串闪避"""
        dodge_map = {
            "forward": self.dodge_forward,
            "backward": self.dodge_backward,
            "left": self.dodge_left,
            "right": self.dodge_right,
        }
        fn = dodge_map.get(direction, self.dodge_forward)
        fn()

    # ─── 钩索 ──────────────────────────────────────────────────────────

    def use_hook(self) -> None:
        """使用钩索（Q键）"""
        self._input.key_press(self._keys["hook"], delay_ms=400)
        logger.debug("使用钩索")

    # ─── 视角控制 ──────────────────────────────────────────────────────

    def rotate_view(self, angle_delta: float) -> None:
        """
        水平旋转视角

        Args:
            angle_delta: 旋转角度（正=右转，负=左转）
        """
        # 将角度转换为鼠标像素移动量
        # 经验公式：每像素约0.1度（需根据游戏灵敏度校准）
        pixels_per_degree = 8.0
        dx = int(angle_delta * pixels_per_degree)
        self._input.mouse_move_relative(dx, 0, smooth=True)

    def look_at_direction(self, current_angle: float, target_angle: float) -> None:
        """
        转向目标方向

        Args:
            current_angle: 当前朝向角度（0=正北，顺时针）
            target_angle: 目标方向角度
        """
        delta = target_angle - current_angle
        # 取最短旋转路径
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360

        if abs(delta) > 2.0:  # 死区：小于2度不修正
            self.rotate_view(delta)
            logger.trace("视角修正: {:.1f}° -> {:.1f}° (delta={:.1f}°)",
                         current_angle, target_angle, delta)

    def aim_at_target(self, target_screen_x: int, target_screen_y: int,
                      screen_center: Tuple[int, int] = (960, 540)) -> None:
        """
        视角瞄准屏幕上的目标

        Args:
            target_screen_x, target_screen_y: 目标屏幕坐标
            screen_center: 屏幕中心坐标
        """
        offset_x = target_screen_x - screen_center[0]
        offset_y = target_screen_y - screen_center[1]

        # 死区过滤
        if abs(offset_x) < 30 and abs(offset_y) < 30:
            return

        self._input.aim_at_screen_offset(offset_x, offset_y)

    # ─── 导航辅助 ──────────────────────────────────────────────────────

    def move_toward_minimap_target(
        self,
        player_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        player_angle: float,
    ) -> None:
        """
        根据小地图坐标朝目标方向移动

        Args:
            player_pos: 玩家小地图坐标
            target_pos: 目标小地图坐标
            player_angle: 当前朝向角度
        """
        # 计算目标方向角度
        dx = target_pos[0] - player_pos[0]
        dy = -(target_pos[1] - player_pos[1])  # 屏幕Y轴反转
        target_angle = math.degrees(math.atan2(dx, dy))
        if target_angle < 0:
            target_angle += 360

        # 调整视角
        self.look_at_direction(player_angle, target_angle)
        random_delay(50)

        # 前进
        self._input.key_down(self._keys["sprint_hold"])
        self._input.key_down(self._keys["move_forward"])
        self._is_moving = True

    @property
    def is_moving(self) -> bool:
        return self._is_moving