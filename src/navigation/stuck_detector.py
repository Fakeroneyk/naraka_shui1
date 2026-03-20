"""
卡住检测与脱困模块
监控角色是否卡在障碍物上，并执行脱困策略
"""
import time
import random
from typing import Optional, Tuple
from loguru import logger

from src.action.movement import MovementController
from src.action.input_controller import InputController
from src.utils.humanize import random_delay


class StuckDetector:
    """卡住检测器"""

    def __init__(
        self,
        movement: MovementController,
        input_ctrl: InputController,
        nav_config: dict,
    ):
        """
        Args:
            movement: 移动控制器
            input_ctrl: 输入控制器
            nav_config: 导航配置（navigation_config.yaml）
        """
        self._movement = movement
        self._input = input_ctrl
        self._nav_cfg = nav_config.get("navigation", {})

        # 配置参数
        self._check_interval = self._nav_cfg.get("stuck_check_interval", 2.0)
        self._stuck_threshold = self._nav_cfg.get("stuck_threshold", 5)
        self._min_move = self._nav_cfg.get("stuck_min_move", 3)

        # 状态
        self._position_history: list[Tuple[int, int]] = []
        self._last_check_time: float = 0.0
        self._no_move_count: int = 0
        self._is_stuck: bool = False
        self._unstuck_attempt: int = 0

    def update(self, current_pos: Optional[Tuple[int, int]]) -> bool:
        """
        更新位置历史，检测是否卡住

        Args:
            current_pos: 当前小地图坐标

        Returns:
            True 如果检测到卡住
        """
        now = time.perf_counter()
        if now - self._last_check_time < self._check_interval:
            return self._is_stuck

        self._last_check_time = now

        if current_pos is None:
            return self._is_stuck

        # 添加历史记录
        self._position_history.append(current_pos)
        if len(self._position_history) > self._stuck_threshold + 1:
            self._position_history.pop(0)

        # 需要足够的历史数据才能判断
        if len(self._position_history) < 2:
            return False

        # 计算最近几次检测的总位移
        oldest = self._position_history[0]
        newest = self._position_history[-1]
        total_move = self._euclidean(oldest, newest)

        if total_move < self._min_move:
            self._no_move_count += 1
            logger.trace("位移过小: {:.1f}px，连续计数: {}", total_move, self._no_move_count)
        else:
            self._no_move_count = 0
            self._is_stuck = False
            self._unstuck_attempt = 0

        if self._no_move_count >= self._stuck_threshold:
            if not self._is_stuck:
                logger.warning("检测到角色卡住！位置: {}", current_pos)
            self._is_stuck = True

        return self._is_stuck

    def try_unstuck(self) -> None:
        """执行脱困动作序列"""
        actions = self._nav_cfg.get("unstuck_actions", [])
        if not actions:
            actions = [
                {"action": "jump"},
                {"action": "dodge_random"},
                {"action": "move_backward", "duration": 800},
            ]

        # 循环尝试脱困动作
        action_cfg = actions[self._unstuck_attempt % len(actions)]
        action_type = action_cfg.get("action", "jump")

        logger.info("尝试脱困: {} (第{}次)", action_type, self._unstuck_attempt + 1)

        self._movement.stop_movement()
        random_delay(100)

        if action_type == "jump":
            self._movement.jump()
            random_delay(400)
            self._movement.move_forward(500)

        elif action_type == "dodge_random":
            direction = random.choice(["forward", "backward", "left", "right"])
            self._movement.dodge_direction(direction)
            random_delay(300)

        elif action_type == "hook_forward":
            self._movement.use_hook()
            random_delay(500)

        elif action_type == "move_backward":
            duration = action_cfg.get("duration", 800)
            self._movement.move_backward(duration)

        self._unstuck_attempt += 1

        # 重置卡住状态，给一段时间观察效果
        self._no_move_count = 0
        self._is_stuck = False
        self._position_history.clear()

    def reset(self) -> None:
        """重置卡住检测状态（到达新目标点时调用）"""
        self._position_history.clear()
        self._no_move_count = 0
        self._is_stuck = False
        self._unstuck_attempt = 0

    @staticmethod
    def _euclidean(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return (dx * dx + dy * dy) ** 0.5

    @property
    def is_stuck(self) -> bool:
        return self._is_stuck