"""
战斗动作模块
实现宁红夜百化冰爆流的所有连招宏
"""
import time
from loguru import logger

from src.action.input_controller import InputController
from src.action.movement import MovementController
from src.utils.humanize import random_delay
from src.utils.timer import CooldownTracker


class CombatActions:
    """战斗动作执行器"""

    def __init__(
        self,
        input_ctrl: InputController,
        movement: MovementController,
        keys_config: dict,
        combat_config: dict,
    ):
        """
        Args:
            input_ctrl: 输入控制器
            movement: 移动控制器
            keys_config: 按键映射
            combat_config: 战斗配置
        """
        self._input = input_ctrl
        self._movement = movement
        self._keys = keys_config
        self._config = combat_config
        self._cooldowns = CooldownTracker()

        # 从配置读取CD
        strategy = combat_config.get("strategy", {})
        combo_sel = strategy.get("combo_selection", {})
        self._skill_f_cd = combo_sel.get("skill_f_cooldown", 8000)

    # ─── 单体动作 ──────────────────────────────────────────────────────

    def use_skill_f(self) -> bool:
        """
        释放F技能（化气）

        Returns:
            True 如果成功释放
        """
        if not self._cooldowns.is_ready("skill_f", self._skill_f_cd):
            remaining = self._cooldowns.remaining_ms("skill_f", self._skill_f_cd)
            logger.trace("化气CD中，剩余: {:.0f}ms", remaining)
            return False

        self._input.key_press(self._keys["skill"], delay_ms=200)
        self._cooldowns.use("skill_f")
        logger.debug("释放化气(F)")
        return True

    def use_ultimate(self) -> None:
        """释放V奥义"""
        self._input.key_press(self._keys["ultimate"], delay_ms=1500)
        logger.debug("释放奥义(V)")

    def normal_attack(self, count: int = 1) -> None:
        """
        普通攻击

        Args:
            count: 连击次数
        """
        for i in range(count):
            self._input.mouse_click("left", delay_ms=150)

    def charge_attack(self, duration_ms: float = 800) -> None:
        """
        蓄力攻击（长剑蓄力剑气）

        Args:
            duration_ms: 蓄力时长（毫秒）
        """
        self._input.mouse_hold("left", duration_ms)
        logger.trace("蓄力攻击 {}ms", duration_ms)

    def switch_weapon(self, weapon_slot: int) -> None:
        """
        切换武器

        Args:
            weapon_slot: 1=长剑, 2=五眼铳
        """
        key = self._keys.get(f"weapon_{weapon_slot}", str(weapon_slot))
        self._input.key_press(key, delay_ms=300)
        logger.debug("切换武器: 槽位{}", weapon_slot)

    def dodge_cancel(self, direction: str = "forward") -> None:
        """
        闪避取消后摇（提升DPS的关键操作）

        Args:
            direction: 闪避方向
        """
        self._movement.dodge_direction(direction)
        random_delay(100)

    # ─── 连招宏 ────────────────────────────────────────────────────────

    def combo_sword_ice_burst(self) -> None:
        """
        长剑冰爆连招（主输出循环）
        F(化气) → 蓄力×3 + 闪避取消
        """
        logger.info("执行连招: 长剑冰爆循环")

        # 1. 化气开启
        self.use_skill_f()
        random_delay(200)

        # 2. 蓄力剑气循环（3次蓄力+闪避取消）
        for i in range(3):
            self.charge_attack(800)
            random_delay(50)
            self.dodge_cancel("forward")
            random_delay(100)

    def combo_musket_burst(self) -> None:
        """
        五眼铳爆发连招
        切铳 → 化气 → 蓄力×2 → 切回长剑
        """
        logger.info("执行连招: 五眼铳爆发")

        # 1. 切换五眼铳
        self.switch_weapon(2)
        random_delay(300)

        # 2. 化气
        self.use_skill_f()
        random_delay(200)

        # 3. 两发蓄力炮击
        self.charge_attack(1000)
        random_delay(100)
        self.charge_attack(1000)
        random_delay(100)

        # 4. 切回长剑
        self.switch_weapon(1)

    def combo_normal_fill(self) -> None:
        """
        普攻填充循环（无技能CD时的持续输出）
        平A×3 → 闪避取消
        """
        logger.trace("执行连招: 普攻填充")
        self.normal_attack(3)
        random_delay(50)
        self.dodge_cancel("forward")

    def combo_ultimate_release(self) -> None:
        """
        奥义释放（群体控制+伤害）
        """
        logger.info("执行连招: 奥义释放")
        self.use_ultimate()

    # ─── 战斗循环决策 ──────────────────────────────────────────────────

    def execute_combat_rotation(
        self,
        skill_ready: bool,
        ultimate_ready: bool,
        enemy_count: int,
        target_distance: float = 0,
    ) -> str:
        """
        根据当前状态选择并执行最优连招

        Args:
            skill_ready: F技能是否就绪（来自UI识别或CD追踪）
            ultimate_ready: V奥义是否就绪
            enemy_count: 当前检测到的敌人数量
            target_distance: 最近目标的屏幕距离（像素）

        Returns:
            执行的连招名称
        """
        # 获取配置
        strategy = self._config.get("strategy", {})
        combo_sel = strategy.get("combo_selection", {})
        ult_min_enemies = combo_sel.get("ultimate_min_enemies", 2)
        musket_min_dist = combo_sel.get("musket_min_distance", 400)

        # 优先级1: 奥义（多敌人时AOE效率最高）
        if ultimate_ready and enemy_count >= ult_min_enemies:
            self.combo_ultimate_release()
            return "ultimate"

        # 优先级2: 化气可用时 → 长剑冰爆连招
        if skill_ready or self._cooldowns.is_ready("skill_f", self._skill_f_cd):
            # 如果敌人远，先用五眼铳
            if target_distance > musket_min_dist:
                self.combo_musket_burst()
                return "musket_burst"
            else:
                self.combo_sword_ice_burst()
                return "sword_ice_burst"

        # 优先级3: 五眼铳远程（敌人较远时）
        if target_distance > musket_min_dist:
            self.combo_musket_burst()
            return "musket_burst"

        # 优先级4: 普攻填充
        self.combo_normal_fill()
        return "normal_fill"

    @property
    def cooldown_tracker(self) -> CooldownTracker:
        return self._cooldowns