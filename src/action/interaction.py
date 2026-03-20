"""
交互动作模块
负责拾取、开箱、开门等交互操作
"""
from loguru import logger

from src.action.input_controller import InputController
from src.utils.humanize import random_delay


class InteractionController:
    """交互动作控制器"""

    def __init__(self, input_ctrl: InputController, keys_config: dict):
        self._input = input_ctrl
        self._keys = keys_config

    def interact(self) -> None:
        """按E执行交互（拾取/开箱/开门）"""
        self._input.key_press(self._keys["interact"], delay_ms=200)
        logger.debug("执行交互(E)")

    def pickup_loot(self) -> None:
        """拾取地面掉落物（连按E）"""
        for _ in range(3):
            self._input.key_press(self._keys["interact"], delay_ms=150)
        logger.debug("拾取掉落物")

    def open_chest(self) -> None:
        """开箱（按E + 等待动画）"""
        self._input.key_press(self._keys["interact"], delay_ms=100)
        random_delay(2000, variance_pct=0.1)  # 等待开箱动画
        logger.debug("开箱")

    def open_boss_door(self) -> None:
        """开Boss门（按E + 等待较长动画）"""
        self._input.key_press(self._keys["interact"], delay_ms=100)
        random_delay(3000, variance_pct=0.1)  # 等待开门动画
        logger.info("开启Boss门")

    def pickup_key(self) -> None:
        """拾取钥匙道具"""
        self._input.key_press(self._keys["interact"], delay_ms=200)
        logger.info("拾取钥匙")

    def loot_area_sweep(self, sweep_count: int = 5) -> None:
        """
        区域拾取扫荡 - 原地旋转+连按E拾取周围所有掉落物

        Args:
            sweep_count: 旋转拾取次数
        """
        logger.debug("开始区域拾取扫荡")
        for i in range(sweep_count):
            # 小角度旋转视角
            self._input.mouse_move_relative(120, 0, smooth=False)
            random_delay(100)
            # 连按E拾取
            self._input.key_press(self._keys["interact"], delay_ms=100)
            self._input.key_press(self._keys["interact"], delay_ms=100)
        logger.debug("区域拾取扫荡完成")