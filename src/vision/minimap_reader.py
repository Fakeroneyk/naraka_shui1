"""
小地图解析模块
负责从小地图截图中提取玩家位置和朝向
"""
import math
import os
from typing import Optional, Tuple
import cv2
import numpy as np
from loguru import logger


class MinimapReader:
    """小地图解析器"""

    def __init__(self, minimap_size: Tuple[int, int] = (160, 160), template_path: str = "player.png"):
        """
        Args:
            minimap_size: 小地图截取尺寸 (width, height)
            template_path: 玩家标记模板图片路径
        """
        self._size = minimap_size
        self._last_pos: Optional[Tuple[int, int]] = None
        self._last_angle: float = 0.0

        # 加载玩家标记模板
        self._player_template = None
        # 优先从template文件夹查找
        template_dir = "template"
        full_path = os.path.join(template_dir, template_path) if not os.path.dirname(template_path) else template_path
        
        if os.path.exists(full_path):
            self._player_template = cv2.imread(full_path, cv2.IMREAD_COLOR)
            if self._player_template is not None:
                logger.info("玩家标记模板已加载: {}", full_path)
            else:
                logger.warning("玩家标记模板加载失败: {}", full_path)
        elif os.path.exists(template_path):
            self._player_template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if self._player_template is not None:
                logger.info("玩家标记模板已加载: {}", template_path)
            else:
                logger.warning("玩家标记模板加载失败: {}", template_path)
        else:
            logger.warning("玩家标记模板不存在: {}", full_path)

        # 模板匹配阈值
        self._template_match_threshold = 0.7

        # 敌人标记颜色范围（红色）
        self._enemy_hsv_lower1 = np.array([0, 100, 100])
        self._enemy_hsv_upper1 = np.array([10, 255, 255])
        self._enemy_hsv_lower2 = np.array([160, 100, 100])
        self._enemy_hsv_upper2 = np.array([180, 255, 255])

    def read_player_position(self, minimap_frame: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        从小地图截图中识别玩家位置

        Args:
            minimap_frame: 小地图区域的RGB图像

        Returns:
            (x, y) 玩家在小地图上的坐标，或None
        """
        if minimap_frame is None:
            return self._last_pos

        if self._player_template is None:
            logger.warning("玩家标记模板未加载")
            return self._last_pos

        try:
            # 模板匹配
            result = cv2.matchTemplate(minimap_frame, self._player_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= self._template_match_threshold:
                # 计算模板中心点
                template_h, template_w = self._player_template.shape[:2]
                cx = max_loc[0] + template_w // 2
                cy = max_loc[1] + template_h // 2
                self._last_pos = (cx, cy)
                logger.trace("模板匹配成功: 位置({}, {}), 置信度: {:.2f}", cx, cy, max_val)
                return (cx, cy)
            else:
                logger.trace("模板匹配置信度不足: {:.2f}", max_val)

        except Exception as e:
            logger.trace("小地图玩家定位失败: {}", e)

        return self._last_pos

    def read_player_angle(self, minimap_frame: np.ndarray) -> float:
        """
        从小地图截图中估算玩家朝向角度
        注意：使用模板匹配时无法直接获取角度，暂时返回上一次检测的角度

        Args:
            minimap_frame: 小地图区域的RGB图像

        Returns:
            角度（度），0=正上方，顺时针增加
        """
        if minimap_frame is None:
            return self._last_angle

        # 模板匹配方式无法直接获取角度，返回上次角度
        # 如果需要角度检测，可以保留HSV方式或使用其他方法
        return self._last_angle

    def detect_enemies_on_minimap(self, minimap_frame: np.ndarray) -> list[Tuple[int, int]]:
        """
        检测小地图上的敌人标记（红点）

        Args:
            minimap_frame: 小地图区域的RGB图像

        Returns:
            [(x, y), ...] 敌人在小地图上的坐标列表
        """
        if minimap_frame is None:
            return []

        try:
            hsv = cv2.cvtColor(minimap_frame, cv2.COLOR_BGR2HSV)

            # 红色有两段HSV范围
            mask1 = cv2.inRange(hsv, self._enemy_hsv_lower1, self._enemy_hsv_upper1)
            mask2 = cv2.inRange(hsv, self._enemy_hsv_lower2, self._enemy_hsv_upper2)
            mask = cv2.bitwise_or(mask1, mask2)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            enemies = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 5:  # 最小面积过滤
                    M = cv2.moments(cnt)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        enemies.append((cx, cy))

            return enemies

        except Exception as e:
            logger.trace("小地图敌人检测失败: {}", e)
            return []

    @staticmethod
    def calculate_angle_to_target(
        player_pos: Tuple[int, int],
        target_pos: Tuple[int, int]
    ) -> float:
        """
        计算从玩家位置到目标位置需要转向的角度

        Args:
            player_pos: 玩家小地图坐标
            target_pos: 目标小地图坐标

        Returns:
            角度（度），0=正上方，顺时针增加
        """
        dx = target_pos[0] - player_pos[0]
        dy = -(target_pos[1] - player_pos[1])  # 屏幕Y轴反转
        angle = math.degrees(math.atan2(dx, dy))
        if angle < 0:
            angle += 360
        return angle

    @staticmethod
    def calculate_distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """计算两点间的小地图距离"""
        dx = pos2[0] - pos1[0]
        dy = pos2[1] - pos1[1]
        return math.sqrt(dx * dx + dy * dy)

    @property
    def last_position(self) -> Optional[Tuple[int, int]]:
        return self._last_pos

    @property
    def last_angle(self) -> float:
        return self._last_angle