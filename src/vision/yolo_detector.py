"""
YOLOv8 目标检测模块
负责识别敌人、宝箱、钥匙、Boss门等游戏目标
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from loguru import logger

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None
    logger.warning("ultralytics 未安装，YOLO检测不可用")


# ─── 检测结果数据类 ────────────────────────────────────────────────────────────

@dataclass
class Detection:
    """单个目标检测结果"""
    class_id: int
    class_name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center(self) -> tuple[int, int]:
        """目标中心坐标"""
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class DetectionResult:
    """一帧的检测结果集合"""
    enemies_normal: list[Detection] = field(default_factory=list)
    enemies_elite: list[Detection] = field(default_factory=list)
    enemies_boss: list[Detection] = field(default_factory=list)
    chests_locked: list[Detection] = field(default_factory=list)
    chests_unlocked: list[Detection] = field(default_factory=list)
    key_items: list[Detection] = field(default_factory=list)
    boss_doors: list[Detection] = field(default_factory=list)
    loot_drops: list[Detection] = field(default_factory=list)
    raw: list[Detection] = field(default_factory=list)

    @property
    def all_enemies(self) -> list[Detection]:
        """所有敌人（按优先级：boss > elite > normal）"""
        return self.enemies_boss + self.enemies_elite + self.enemies_normal

    @property
    def has_enemies(self) -> bool:
        return bool(self.enemies_normal or self.enemies_elite or self.enemies_boss)

    @property
    def nearest_enemy(self) -> Optional[Detection]:
        """获取距屏幕中心最近的敌人"""
        all_e = self.all_enemies
        if not all_e:
            return None
        screen_cx, screen_cy = 960, 540
        return min(all_e, key=lambda d: abs(d.center[0] - screen_cx) + abs(d.center[1] - screen_cy))


# ─── 检测器 ────────────────────────────────────────────────────────────────────

# 类别ID到字段名的映射
CLASS_ID_MAP = {
    0: "enemy_normal",
    1: "enemy_elite",
    2: "enemy_boss",
    3: "health_bar_enemy",
    4: "chest_locked",
    5: "chest_unlocked",
    6: "key_item",
    7: "door_boss",
    8: "loot_drop",
}


class YoloDetector:
    """YOLOv8 目标检测器"""

    def __init__(self, model_path: str, conf_threshold: float = 0.6,
                 imgsz: int = 640, device: str = "cuda"):
        """
        Args:
            model_path: 模型权重路径 (.pt 文件)
            conf_threshold: 置信度阈值
            imgsz: 推理输入尺寸
            device: 推理设备 (cuda / cpu)
        """
        self._model_path = model_path
        self._conf = conf_threshold
        self._imgsz = imgsz
        self._device = device
        self._model: Optional[object] = None
        self._class_names: dict[int, str] = {}

    def load(self) -> bool:
        """加载 YOLO 模型"""
        if YOLO is None:
            logger.error("ultralytics 未安装，无法加载模型")
            return False

        try:
            import os
            if not os.path.exists(self._model_path):
                logger.warning("模型文件不存在: {}，YOLO检测将不可用", self._model_path)
                return False

            self._model = YOLO(self._model_path)
            # 预热推理（减少首次推理延迟）
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model.predict(dummy, verbose=False, device=self._device)
            logger.info("YOLO模型加载成功: {}，设备: {}", self._model_path, self._device)
            return True
        except Exception as e:
            logger.error("YOLO模型加载失败: {}", e)
            return False

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """
        对一帧图像执行目标检测

        Args:
            frame: RGB格式图像 (H, W, 3)

        Returns:
            DetectionResult 检测结果
        """
        result = DetectionResult()

        if self._model is None:
            return result

        try:
            # 执行推理
            predictions = self._model.predict(
                frame,
                conf=self._conf,
                imgsz=self._imgsz,
                device=self._device,
                verbose=False,
                stream=False,
            )

            for pred in predictions:
                for box in pred.boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    class_name = CLASS_ID_MAP.get(class_id, f"class_{class_id}")

                    det = Detection(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence,
                        x1=x1, y1=y1, x2=x2, y2=y2,
                    )
                    result.raw.append(det)

                    # 分类存放
                    if class_id == 0:
                        result.enemies_normal.append(det)
                    elif class_id == 1:
                        result.enemies_elite.append(det)
                    elif class_id == 2:
                        result.enemies_boss.append(det)
                    elif class_id == 4:
                        result.chests_locked.append(det)
                    elif class_id == 5:
                        result.chests_unlocked.append(det)
                    elif class_id == 6:
                        result.key_items.append(det)
                    elif class_id == 7:
                        result.boss_doors.append(det)
                    elif class_id == 8:
                        result.loot_drops.append(det)

        except Exception as e:
            logger.error("YOLO推理出错: {}", e)

        return result

    @property
    def is_loaded(self) -> bool:
        return self._model is not None