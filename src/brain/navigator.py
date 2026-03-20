"""
导航决策模块
基于小地图坐标控制角色移动到目标点位

导航层次：
    1. 优先跟随预设路径点（route_waypoints）
    2. 卡住时触发 A* 动态寻路绕过障碍（Pathfinder）
    3. 多次卡住时执行 StuckDetector 脱困策略
"""
import math
import time
from typing import Optional, Tuple
from loguru import logger

from src.brain.game_state import GameState
from src.navigation.waypoint_manager import WaypointManager, MonsterSpot, Waypoint
from src.navigation.stuck_detector import StuckDetector
from src.navigation.pathfinder import Pathfinder
from src.action.movement import MovementController
from src.utils.humanize import random_delay


class Navigator:
    """导航控制器：从小地图坐标到键盘控制的闭环"""

    def __init__(
        self,
        movement: MovementController,
        waypoint_mgr: WaypointManager,
        stuck_detector: StuckDetector,
        nav_config: dict,
        pathfinder: Optional[Pathfinder] = None,
    ):
        self._movement = movement
        self._waypoints = waypoint_mgr
        self._stuck = stuck_detector
        self._nav_cfg = nav_config.get("navigation", {})

        # A* 寻路器（可选，卡住时启用）
        minimap_size = nav_config.get("map", {}).get("minimap_size", [160, 160])
        self._pathfinder: Pathfinder = pathfinder or Pathfinder(
            grid_width=minimap_size[0],
            grid_height=minimap_size[1],
        )
        self._use_astar = False              # 是否当前使用A*路径
        self._astar_fail_count = 0          # A*连续失败次数

        self._arrival_threshold = self._nav_cfg.get("arrival_threshold", 8)
        self._current_route: list[Tuple[int, int]] = []
        self._current_route_idx: int = 0
        self._target_spot: Optional[MonsterSpot] = None
        self._target_waypoint: Optional[Waypoint] = None

    # ─── 目标设置 ──────────────────────────────────────────────────────

    def set_target_spot(self, spot: MonsterSpot) -> None:
        """设置导航目标为怪物点位"""
        self._target_spot = spot
        self._target_waypoint = None
        self._current_route = spot.route_waypoints.copy()
        self._current_route_idx = 0
        self._stuck.reset()
        logger.info("导航目标: {} ({})", spot.name, spot.minimap_pos)

    def set_target_waypoint(self, waypoint: Waypoint) -> None:
        """设置导航目标为单个路径点（如Boss门）"""
        self._target_waypoint = waypoint
        self._target_spot = None
        self._current_route = [waypoint.minimap_pos]
        self._current_route_idx = 0
        self._stuck.reset()
        logger.info("导航目标: {} ({})", waypoint.description, waypoint.minimap_pos)

    # ─── 导航执行 ──────────────────────────────────────────────────────

    def navigate_step(self, state: GameState) -> bool:
        """
        执行一步导航逻辑

        Args:
            state: 当前游戏状态

        Returns:
            True 表示已到达目标，False 表示仍在导航中
        """
        player_pos = state.player_minimap_pos
        player_angle = state.player_facing_angle

        if player_pos is None:
            # 无法获取位置，继续向前
            self._movement.start_sprint_forward()
            return False

        # 检测卡住
        if self._stuck.update(player_pos):
            logger.warning("导航中检测到卡住，尝试A*动态寻路")
            self._movement.stop_movement()

            # 先尝试 A* 绕路
            if self._current_route and not self._use_astar:
                final_target = self._current_route[-1]
                astar_path = self._pathfinder.find_path(player_pos, final_target)
                if astar_path and len(astar_path) > 1:
                    # 简化路径并替换当前路由
                    simplified = self._pathfinder.simplify_path(astar_path, tolerance=4.0)
                    self._current_route = simplified
                    self._current_route_idx = 0
                    self._use_astar = True
                    self._stuck.reset()
                    logger.info("A*寻路成功，路径长度: {} 个点", len(simplified))
                    return False
                else:
                    self._astar_fail_count += 1
                    logger.warning("A*寻路无路径（失败{}次），执行物理脱困", self._astar_fail_count)

            # A* 也无法规划或已在使用A*仍然卡住 → 物理脱困
            self._use_astar = False
            self._stuck.try_unstuck()
            return False

        # 获取当前目标路径点
        if self._current_route_idx >= len(self._current_route):
            # 路径已走完
            self._movement.stop_movement()
            return True

        current_target = self._current_route[self._current_route_idx]
        dist = self._euclidean(player_pos, current_target)

        # 到达当前路径点
        if dist <= self._arrival_threshold:
            logger.debug("到达路径点 {}/{}: {}",
                         self._current_route_idx + 1,
                         len(self._current_route),
                         current_target)
            self._current_route_idx += 1

            # 判断是否到达最终目标
            if self._current_route_idx >= len(self._current_route):
                self._movement.stop_movement()
                logger.info("✅ 已到达目标位置")
                return True

            current_target = self._current_route[self._current_route_idx]

        # 朝目标移动
        self._navigate_toward(player_pos, current_target, player_angle)
        return False

    def _navigate_toward(
        self,
        player_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        player_angle: float,
    ) -> None:
        """朝目标方向移动（调整视角+前进）"""
        # 计算目标方向角
        dx = target_pos[0] - player_pos[0]
        dy = -(target_pos[1] - player_pos[1])  # 屏幕Y轴反转
        target_angle = math.degrees(math.atan2(dx, dy))
        if target_angle < 0:
            target_angle += 360

        # 如果偏差较大，先调整视角再前进
        angle_diff = target_angle - player_angle
        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360

        if abs(angle_diff) > 10:
            self._movement.rotate_view(angle_diff * 0.5)  # 每帧修正50%偏差
            random_delay(30)

        # 持续疾跑前进
        self._movement.start_sprint_forward()

    def use_hook_if_needed(self, spot: MonsterSpot) -> None:
        """根据点位配置决定是否使用钩索加速"""
        if spot.approach_key == "hook":
            self._movement.use_hook()
            random_delay(500)

    def is_near_target(self, player_pos: Tuple[int, int]) -> bool:
        """检查是否接近当前目标"""
        if not self._current_route:
            return False
        if self._current_route_idx >= len(self._current_route):
            return True
        target = self._current_route[-1]  # 最终目标点
        return self._euclidean(player_pos, target) <= self._arrival_threshold * 2

    @staticmethod
    def _euclidean(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

    def clear_target(self) -> None:
        """清除当前导航目标"""
        self._current_route = []
        self._current_route_idx = 0
        self._target_spot = None
        self._target_waypoint = None
        self._movement.stop_movement()