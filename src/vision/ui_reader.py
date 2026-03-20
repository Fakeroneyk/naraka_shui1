"""
UI状态读取模块
负责读取血量、技能CD、钥匙数量、交互提示等UI信息
"""
from typing import Optional, Tuple
import cv2
import numpy as np
from loguru import logger

from src.vision.template_matcher import TemplateMatcher


class UIReader:
    """游戏UI状态读取器"""

    def __init__(self, template_matcher: TemplateMatcher, screen_regions: dict):
        """
        Args:
            template_matcher: 模板匹配器实例
            screen_regions: 屏幕区域配置字典
        """
        self._matcher = template_matcher
        self._regions = screen_regions

    # ─── 技能状态 ───────────────────────────────────────────────────────

    def is_skill_ready(self, skill_bar_frame: np.ndarray) -> bool:
        """
        检测F技能（化气）是否就绪

        Args:
            skill_bar_frame: 技能栏区域截图（RGB）

        Returns:
            True 表示技能可用
        """
        if skill_bar_frame is None:
            return False

        result = self._matcher.match(skill_bar_frame, "skill_ready")
        if result:
            _, _, conf = result
            logger.trace("技能就绪检测: conf={:.2f}", conf)
            return True
        return False

    def is_ultimate_ready(self, skill_bar_frame: np.ndarray) -> bool:
        """
        检测V奥义是否就绪

        Args:
            skill_bar_frame: 技能栏区域截图（RGB）

        Returns:
            True 表示奥义可用
        """
        if skill_bar_frame is None:
            return False

        result = self._matcher.match(skill_bar_frame, "ultimate_ready")
        if result:
            return True
        return False

    # ─── 交互提示 ───────────────────────────────────────────────────────

    def detect_interact_prompt(self, interact_frame: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        检测屏幕上的E交互提示

        Args:
            interact_frame: 交互提示区域截图（RGB）

        Returns:
            (x, y) 交互提示的屏幕坐标，或None
        """
        if interact_frame is None:
            return None

        result = self._matcher.match(interact_frame, "interact_e_prompt")
        if result:
            x, y, conf = result
            logger.debug("检测到交互提示E: ({}, {}), conf={:.2f}", x, y, conf)
            return (x, y)
        return None

    def detect_chest_prompt(self, interact_frame: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        检测开箱提示

        Returns:
            (x, y) 宝箱交互提示坐标，或None
        """
        if interact_frame is None:
            return None

        result = self._matcher.match(interact_frame, "chest_open_prompt")
        if result:
            x, y, conf = result
            logger.debug("检测到宝箱提示: ({}, {}), conf={:.2f}", x, y, conf)
            return (x, y)
        return None

    # ─── 钥匙计数 ───────────────────────────────────────────────────────

    def count_keys(self, item_bar_frame: np.ndarray) -> int:
        """
        检测已拾取的钥匙数量

        Args:
            item_bar_frame: 道具栏区域截图（RGB）

        Returns:
            钥匙数量 (0-3)
        """
        if item_bar_frame is None:
            return 0

        # 方案1: 模板匹配钥匙图标，统计出现次数
        matches = self._matcher.match_all(item_bar_frame, "key_icon", threshold=0.8)
        count = len(matches)
        if count > 0:
            logger.debug("检测到钥匙数量: {}", count)
        return min(count, 3)

    # ─── 血量读取（备用，虽然不考虑生存但可用于日志） ─────────────────

    def read_health_ratio(self, health_bar_frame: np.ndarray) -> float:
        """
        读取角色血量比例

        Args:
            health_bar_frame: 血条区域截图（RGB）

        Returns:
            血量比例 0.0~1.0
        """
        if health_bar_frame is None:
            return 1.0

        try:
            # 血条通常为绿色/红色，通过HSV提取
            hsv = cv2.cvtColor(health_bar_frame, cv2.COLOR_RGB2HSV)

            # 绿色血条
            green_lower = np.array([35, 80, 80])
            green_upper = np.array([85, 255, 255])
            mask = cv2.inRange(hsv, green_lower, green_upper)

            # 计算血条填充比例
            h, w = mask.shape[:2]
            total_pixels = w  # 以宽度为基准
            filled_pixels = 0

            # 扫描血条中间行
            mid_row = mask[h // 2, :]
            filled_pixels = np.sum(mid_row > 0)

            ratio = filled_pixels / total_pixels if total_pixels > 0 else 1.0
            return min(1.0, max(0.0, ratio))

        except Exception as e:
            logger.trace("血量读取失败: {}", e)
            return 1.0

    # ─── 综合状态快照 ───────────────────────────────────────────────────

    def read_all(self, frames: dict[str, Optional[np.ndarray]]) -> dict:
        """
        一次性读取所有UI状态

        Args:
            frames: 各UI区域截图字典 {区域名: 截图}

        Returns:
            状态字典
        """
        return {
            "skill_ready": self.is_skill_ready(frames.get("skill_bar")),
            "ultimate_ready": self.is_ultimate_ready(frames.get("skill_bar")),
            "interact_prompt": self.detect_interact_prompt(frames.get("interact_prompt")),
            "chest_prompt": self.detect_chest_prompt(frames.get("interact_prompt")),
            "key_count": self.count_keys(frames.get("item_bar")),
            "health_ratio": self.read_health_ratio(frames.get("health_bar")),
        }