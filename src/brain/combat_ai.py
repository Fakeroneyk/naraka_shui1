"""
战斗AI模块
根据游戏状态选择最优战斗策略，集成自动瞄准
"""
from loguru import logger

from src.brain.game_state import GameState
from src.action.combat_actions import CombatActions
from src.action.movement import MovementController
from src.action.interaction import InteractionController


class CombatAI:
    """战斗AI决策器"""

    def __init__(
        self,
        combat_actions: CombatActions,
        movement: MovementController,
        interaction: InteractionController,
        combat_config: dict,
    ):
        self._combat = combat_actions
        self._movement = movement
        self._interact = interaction
        self._config = combat_config

        strategy = combat_config.get("strategy", {})
        targeting = strategy.get("targeting", {})
        self._screen_center = tuple(targeting.get("screen_center", [960, 540]))
        self._aim_deadzone = targeting.get("aim_deadzone", 30)
        self._aim_speed = targeting.get("aim_speed", 12)

    def execute_combat_tick(self, state: GameState) -> str:
        """
        执行一个战斗帧的AI决策

        Args:
            state: 当前游戏状态

        Returns:
            执行的动作名称
        """
        # Step 1: 自动瞄准最近的敌人
        if state.nearest_enemy_screen_pos:
            self._auto_aim(state.nearest_enemy_screen_pos)

        # Step 2: 选择并执行连招
        action_name = self._combat.execute_combat_rotation(
            skill_ready=state.skill_f_ready,
            ultimate_ready=state.ultimate_ready,
            enemy_count=state.enemy_count,
            target_distance=state.nearest_enemy_distance,
        )

        return action_name

    def _auto_aim(self, enemy_screen_pos: tuple[int, int]) -> None:
        """自动瞄准：将视角朝向敌人"""
        ex, ey = enemy_screen_pos
        cx, cy = self._screen_center

        offset_x = ex - cx
        offset_y = ey - cy

        # 死区判断
        if abs(offset_x) < self._aim_deadzone and abs(offset_y) < self._aim_deadzone:
            return

        # 限速平滑修正（每帧只修正一部分，避免镜头抖动）
        correction_x = max(-self._aim_speed, min(self._aim_speed, offset_x // 4))
        correction_y = max(-self._aim_speed, min(self._aim_speed, offset_y // 6))

        self._movement._input.mouse_move_relative(correction_x, correction_y, smooth=False)

    def should_enter_combat(self, state: GameState) -> bool:
        """判断是否应进入战斗状态"""
        return state.enemy_count > 0

    def is_combat_finished(self, state: GameState) -> bool:
        """判断战斗是否结束（无敌人且持续一段时间）"""
        return state.enemy_count == 0

    def execute_boss_strategy(self, state: GameState) -> str:
        """
        Boss战特殊策略
        Boss战中更积极使用奥义和五眼铳

        Returns:
            执行的动作名称
        """
        # 自动瞄准Boss
        if state.nearest_enemy_screen_pos:
            self._auto_aim(state.nearest_enemy_screen_pos)

        # Boss战优先释放奥义
        if state.ultimate_ready:
            self._combat.combo_ultimate_release()
            return "boss_ultimate"

        # 化气+长剑冰爆为主
        if state.skill_f_ready:
            self._combat.combo_sword_ice_burst()
            return "boss_sword_ice"

        # 五眼铳远程输出
        if state.nearest_enemy_distance > 300:
            self._combat.combo_musket_burst()
            return "boss_musket"

        # 普攻填充
        self._combat.combo_normal_fill()
        return "boss_normal_fill"