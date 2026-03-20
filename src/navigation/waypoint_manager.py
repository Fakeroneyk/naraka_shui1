"""
路径点管理模块
管理净水流深地图的预设路径点，支持点位优先级排序
"""
import math
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class SpotStatus(Enum):
    """怪物点位状态"""
    UNKNOWN = "unknown"       # 尚未探索
    ACTIVE = "active"         # 有怪物/活跃
    CLEARED = "cleared"       # 已清怪
    EMPTY = "empty"           # 本局无怪（空点）


@dataclass
class Waypoint:
    """路径点"""
    id: str
    minimap_pos: tuple[int, int]
    approach_key: str = "walk"  # walk / jump / hook
    description: str = ""


@dataclass
class MonsterSpot:
    """怪物刷新点位"""
    id: str
    name: str
    minimap_pos: tuple[int, int]
    priority: int
    route_waypoints: list[tuple[int, int]] = field(default_factory=list)
    approach_key: str = "walk"
    note: str = ""
    status: SpotStatus = SpotStatus.UNKNOWN

    @property
    def is_done(self) -> bool:
        return self.status in (SpotStatus.CLEARED, SpotStatus.EMPTY)


class WaypointManager:
    """净水流深地图路径点管理器"""

    def __init__(self, nav_config: dict):
        """
        Args:
            nav_config: navigation_config.yaml 的内容
        """
        self._config = nav_config
        self._monster_spots: list[MonsterSpot] = []
        self._boss_door: Optional[Waypoint] = None
        self._boss_arena: Optional[Waypoint] = None
        self._spawn: Optional[Waypoint] = None
        self._current_waypoint_index: int = 0

        self._load_from_config()

    def _load_from_config(self) -> None:
        """从配置文件加载所有路径点"""
        # 出生点
        spawn_cfg = self._config.get("spawn", {})
        if spawn_cfg:
            self._spawn = Waypoint(
                id="spawn",
                minimap_pos=tuple(spawn_cfg["minimap_pos"]),
                description=spawn_cfg.get("description", "出生点"),
            )

        # 怪物点位（按priority排序）
        spots_cfg = self._config.get("monster_spots", [])
        for spot in spots_cfg:
            ms = MonsterSpot(
                id=spot["id"],
                name=spot["name"],
                minimap_pos=tuple(spot["minimap_pos"]),
                priority=spot["priority"],
                route_waypoints=[tuple(wp) for wp in spot.get("route_waypoints", [])],
                approach_key=spot.get("approach_key", "walk"),
                note=spot.get("note", ""),
            )
            self._monster_spots.append(ms)

        # 按priority排序
        self._monster_spots.sort(key=lambda s: s.priority)

        # Boss门
        door_cfg = self._config.get("boss_door", {})
        if door_cfg:
            self._boss_door = Waypoint(
                id="boss_door",
                minimap_pos=tuple(door_cfg["minimap_pos"]),
                approach_key=door_cfg.get("approach_key", "walk"),
                description=door_cfg.get("name", "Boss门"),
            )

        # Boss房中心
        arena_cfg = self._config.get("boss_arena", {})
        if arena_cfg:
            self._boss_arena = Waypoint(
                id="boss_arena",
                minimap_pos=tuple(arena_cfg["minimap_pos"]),
                description=arena_cfg.get("name", "Boss战斗区域"),
            )

        logger.info("路径点加载完成: {} 个怪物点位", len(self._monster_spots))

    # ─── 点位状态管理 ──────────────────────────────────────────────────

    def mark_spot_active(self, spot_id: str) -> None:
        """标记点位为有怪"""
        for spot in self._monster_spots:
            if spot.id == spot_id:
                spot.status = SpotStatus.ACTIVE
                logger.info("点位 {} 标记为: ACTIVE", spot_id)

    def mark_spot_cleared(self, spot_id: str) -> None:
        """标记点位为已清怪"""
        for spot in self._monster_spots:
            if spot.id == spot_id:
                spot.status = SpotStatus.CLEARED
                logger.info("点位 {} 标记为: CLEARED", spot_id)

    def mark_spot_empty(self, spot_id: str) -> None:
        """标记点位为空点（本局无怪）"""
        for spot in self._monster_spots:
            if spot.id == spot_id:
                spot.status = SpotStatus.EMPTY
                logger.info("点位 {} 标记为: EMPTY", spot_id)

    # ─── 查询接口 ──────────────────────────────────────────────────────

    def get_next_target_spot(self) -> Optional[MonsterSpot]:
        """
        获取下一个需要探索的怪物点位（按priority顺序，跳过已完成的）

        Returns:
            下一个目标点位，或None（全部已完成）
        """
        for spot in self._monster_spots:
            if not spot.is_done:
                return spot
        return None

    def get_nearest_undone_spot(
        self, player_pos: tuple[int, int]
    ) -> Optional[MonsterSpot]:
        """
        获取距玩家最近的未完成点位（用于效率优化）

        Args:
            player_pos: 玩家当前小地图坐标

        Returns:
            最近的未完成点位
        """
        undone = [s for s in self._monster_spots if not s.is_done]
        if not undone:
            return None

        def dist(spot: MonsterSpot) -> float:
            dx = spot.minimap_pos[0] - player_pos[0]
            dy = spot.minimap_pos[1] - player_pos[1]
            return math.sqrt(dx * dx + dy * dy)

        return min(undone, key=dist)

    def all_spots_done(self) -> bool:
        """检查是否所有已激活点位都已完成"""
        active = [s for s in self._monster_spots if s.status == SpotStatus.ACTIVE]
        cleared = [s for s in self._monster_spots if s.status == SpotStatus.CLEARED]
        # 三个激活点位全部清怪
        return len(cleared) >= 3

    def get_cleared_count(self) -> int:
        """获取已清怪点位数量"""
        return sum(1 for s in self._monster_spots if s.status == SpotStatus.CLEARED)

    @property
    def boss_door(self) -> Optional[Waypoint]:
        return self._boss_door

    @property
    def boss_arena(self) -> Optional[Waypoint]:
        return self._boss_arena

    @property
    def spawn_point(self) -> Optional[Waypoint]:
        return self._spawn

    @property
    def all_spots(self) -> list[MonsterSpot]:
        return self._monster_spots