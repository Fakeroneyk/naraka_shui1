"""
全局游戏状态管理
集中存储和更新来自感知层的所有状态信息
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple
import time

from src.vision.yolo_detector import DetectionResult


class GamePhase(Enum):
    """游戏阶段"""
    INIT = "init"                   # 初始化
    SPAWNED = "spawned"             # 刚出生
    NAVIGATING = "navigating"       # 导航中
    EXPLORING_SPOT = "exploring"    # 探索点位（判断是否有怪）
    COMBAT = "combat"               # 战斗中
    LOOTING = "looting"             # 拾取阶段
    NAVIGATE_TO_BOSS = "nav_boss"   # 前往Boss门
    OPEN_DOOR = "open_door"         # 开Boss门
    BOSS_FIGHT = "boss_fight"       # Boss战
    VICTORY = "victory"             # 通关
    STUCK = "stuck"                 # 卡住（临时状态）


@dataclass
class GameState:
    """全局游戏状态快照"""

    # ── 阶段 ──────────────────────────────────────
    phase: GamePhase = GamePhase.INIT
    last_phase_change: float = field(default_factory=time.perf_counter)

    # ── 位置 ──────────────────────────────────────
    player_minimap_pos: Optional[Tuple[int, int]] = None
    player_facing_angle: float = 0.0          # 当前朝向角度（度）
    current_target_spot_id: Optional[str] = None  # 正在前往的点位ID

    # ── 战斗 ──────────────────────────────────────
    detection: Optional[DetectionResult] = None
    enemy_count: int = 0
    nearest_enemy_screen_pos: Optional[Tuple[int, int]] = None
    nearest_enemy_distance: float = 0.0       # 像素距离

    # ── UI状态 ────────────────────────────────────
    skill_f_ready: bool = True                # 化气技能是否就绪
    ultimate_ready: bool = False              # 奥义是否就绪
    key_count: int = 0                        # 已拾取钥匙数量
    interact_prompt_visible: bool = False     # E交互提示是否显示
    chest_prompt_visible: bool = False        # 宝箱提示是否显示
    health_ratio: float = 1.0                 # 血量比例

    # ── 点位追踪 ──────────────────────────────────
    cleared_spot_count: int = 0               # 已清怪点位数量
    explored_spot_ids: set = field(default_factory=set)   # 已探索点位

    # ── 时间追踪 ──────────────────────────────────
    combat_start_time: Optional[float] = None
    loot_start_time: Optional[float] = None
    phase_timeout: float = 60.0              # 当前阶段超时秒数

    def change_phase(self, new_phase: GamePhase, timeout: float = 60.0) -> None:
        """切换游戏阶段"""
        self.phase = new_phase
        self.last_phase_change = time.perf_counter()
        self.phase_timeout = timeout

    def is_phase_timed_out(self) -> bool:
        """当前阶段是否超时"""
        return (time.perf_counter() - self.last_phase_change) > self.phase_timeout

    def phase_elapsed(self) -> float:
        """当前阶段已运行秒数"""
        return time.perf_counter() - self.last_phase_change

    def update_from_detection(self, detection: DetectionResult,
                               screen_center: Tuple[int, int] = (960, 540)) -> None:
        """从YOLO检测结果更新状态"""
        self.detection = detection
        self.enemy_count = len(detection.all_enemies)

        if detection.nearest_enemy:
            cx, cy = detection.nearest_enemy.center
            scx, scy = screen_center
            self.nearest_enemy_screen_pos = (cx, cy)
            self.nearest_enemy_distance = ((cx - scx) ** 2 + (cy - scy) ** 2) ** 0.5
        else:
            self.nearest_enemy_screen_pos = None
            self.nearest_enemy_distance = 0.0

    def update_from_ui(self, ui_data: dict) -> None:
        """从UI读取结果更新状态"""
        self.skill_f_ready = ui_data.get("skill_ready", self.skill_f_ready)
        self.ultimate_ready = ui_data.get("ultimate_ready", self.ultimate_ready)
        self.key_count = ui_data.get("key_count", self.key_count)
        self.interact_prompt_visible = ui_data.get("interact_prompt") is not None
        self.chest_prompt_visible = ui_data.get("chest_prompt") is not None
        self.health_ratio = ui_data.get("health_ratio", self.health_ratio)

    def update_position(self, pos: Optional[Tuple[int, int]], angle: float) -> None:
        """更新位置信息"""
        self.player_minimap_pos = pos
        self.player_facing_angle = angle

    @property
    def has_all_keys(self) -> bool:
        """是否已集齐3把钥匙"""
        return self.key_count >= 3

    def __repr__(self) -> str:
        return (
            f"GameState(phase={self.phase.value}, "
            f"keys={self.key_count}/3, "
            f"cleared={self.cleared_spot_count}, "
            f"enemies={self.enemy_count})"
        )