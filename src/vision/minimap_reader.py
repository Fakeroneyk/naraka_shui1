"""
小地图解析模块
负责从小地图截图中提取玩家位置和朝向
"""
import math
from typing import Optional, Tuple
import cv2
import numpy as np
from loguru import logger


class MinimapReader:
    """小地图解析器"""

    def __init__(self, minimap_size: Tuple[int, int] = (160, 160)):
        """
        Args:
            minimap_size: 小地图截取尺寸 (width, height)
        """
        self._size = minimap_size
        self._last_pos: Optional[Tuple[int, int]] = None
        self._last_angle: float = 0.0

        # 玩家标记颜色范围（HSV空间，需根据实际游戏截图校准）
        # 玩家标记是黄色箭头
        self._player_hsv_lower = np.array([75, 100, 100])
        self._player_hsv_upper = np.array([95, 255, 255])
        # 最小轮廓面积阈值
        self._min_player_area = 3

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

        try:
            # 转为HSV
            hsv = cv2.cvtColor(minimap_frame, cv2.COLOR_BGR2HSV)

            # 提取玩家标记（亮色掩模）
            mask = cv2.inRange(hsv, self._player_hsv_lower, self._player_hsv_upper)

            # 形态学操作去噪
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                # 过滤：排除过大(背景)和过小(噪点)的轮廓
                valid = [c for c in contours 
                        if self._min_player_area <= cv2.contourArea(c) <= 30000]
                if not valid:
                    valid = [c for c in contours if cv2.contourArea(c) >= self._min_player_area]
                
                if valid:
                    # 选择最大的轮廓（玩家标记应该相对较大）
                    largest = max(valid, key=cv2.contourArea)
                    M = cv2.moments(largest)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        self._last_pos = (cx, cy)
                        return (cx, cy)

        except Exception as e:
            logger.trace("小地图玩家定位失败: {}", e)

        return self._last_pos

    def read_player_angle(self, minimap_frame: np.ndarray) -> float:
        """
        从小地图截图中估算玩家朝向角度

        Args:
            minimap_frame: 小地图区域的RGB图像

        Returns:
            角度（度），0=正上方，顺时针增加
        """
        if minimap_frame is None:
            return self._last_angle

        try:
            hsv = cv2.cvtColor(minimap_frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, self._player_hsv_lower, self._player_hsv_upper)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                largest = max(contours, key=cv2.contourArea)
                if len(largest) >= 5:
                    # 拟合椭圆获取角度
                    ellipse = cv2.fitEllipse(largest)
                    angle = ellipse[2]  # 椭圆旋转角
                    self._last_angle = angle
                    return angle

        except Exception as e:
            logger.trace("小地图朝向检测失败: {}", e)

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