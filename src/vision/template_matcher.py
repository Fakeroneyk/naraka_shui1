"""
OpenCV 模板匹配模块
用于识别固定UI元素（技能状态、交互提示等）
"""
import os
from typing import Optional, Tuple
import cv2
import numpy as np
from loguru import logger


class TemplateMatcher:
    """OpenCV 模板匹配器"""

    def __init__(self, templates_dir: str, threshold: float = 0.85):
        """
        Args:
            templates_dir: 模板图片目录路径
            threshold: 匹配置信度阈值
        """
        self._templates_dir = templates_dir
        self._threshold = threshold
        self._templates: dict[str, np.ndarray] = {}       # name -> 彩色模板
        self._templates_gray: dict[str, np.ndarray] = {}  # name -> 灰度模板
        self._template_sizes: dict[str, Tuple[int, int]] = {}  # name -> (h, w)

    def load_templates(self, template_files: dict[str, str]) -> int:
        """
        加载所有模板图片

        Args:
            template_files: {模板名: 文件名} 字典

        Returns:
            成功加载的模板数量
        """
        loaded = 0
        for name, filename in template_files.items():
            filepath = os.path.join(self._templates_dir, filename)
            if not os.path.exists(filepath):
                logger.warning("模板文件不存在: {} -> {}", name, filepath)
                continue

            img = cv2.imread(filepath, cv2.IMREAD_COLOR)
            if img is None:
                logger.warning("无法读取模板: {}", filepath)
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self._templates[name] = img
            self._templates_gray[name] = gray
            self._template_sizes[name] = gray.shape[:2]  # (h, w)
            loaded += 1
            logger.debug("加载模板: {} ({} x {})", name, gray.shape[1], gray.shape[0])

        logger.info("模板加载完成: {}/{} 个", loaded, len(template_files))
        return loaded

    def match(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: Optional[float] = None,
        use_gray: bool = True,
    ) -> Optional[Tuple[int, int, float]]:
        """
        在画面中查找模板

        Args:
            frame: 待匹配的画面 (RGB格式的numpy数组)
            template_name: 模板名称
            threshold: 自定义阈值，不传使用默认
            use_gray: 是否使用灰度匹配（更快）

        Returns:
            (center_x, center_y, confidence) 或 None（未匹配到）
        """
        thresh = threshold or self._threshold

        if use_gray:
            if template_name not in self._templates_gray:
                return None
            template = self._templates_gray[template_name]
            # 将RGB帧转为灰度
            frame_proc = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        else:
            if template_name not in self._templates:
                return None
            template = self._templates[template_name]
            # 将RGB转为BGR（OpenCV格式）
            frame_proc = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        h, w = template.shape[:2]

        # 检查帧尺寸是否足够
        if frame_proc.shape[0] < h or frame_proc.shape[1] < w:
            return None

        # 执行模板匹配
        result = cv2.matchTemplate(frame_proc, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= thresh:
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y, max_val)

        return None

    def match_all(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: Optional[float] = None,
    ) -> list[Tuple[int, int, float]]:
        """
        在画面中查找模板的所有匹配位置

        Returns:
            [(center_x, center_y, confidence), ...] 列表
        """
        thresh = threshold or self._threshold

        if template_name not in self._templates_gray:
            return []

        template = self._templates_gray[template_name]
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        h, w = template.shape[:2]

        if frame_gray.shape[0] < h or frame_gray.shape[1] < w:
            return []

        result = cv2.matchTemplate(frame_gray, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= thresh)

        matches = []
        for pt_y, pt_x in zip(*locations):
            center_x = pt_x + w // 2
            center_y = pt_y + h // 2
            conf = result[pt_y, pt_x]
            matches.append((center_x, center_y, float(conf)))

        # 非极大值抑制（简易版：移除距离过近的重复匹配）
        if matches:
            matches = self._nms(matches, min_distance=20)

        return matches

    def has_template(self, template_name: str) -> bool:
        """检查模板是否已加载"""
        return template_name in self._templates_gray

    @staticmethod
    def _nms(matches: list[Tuple[int, int, float]], min_distance: int = 20) -> list[Tuple[int, int, float]]:
        """简易非极大值抑制"""
        if not matches:
            return []

        # 按置信度降序排列
        matches.sort(key=lambda m: m[2], reverse=True)
        keep = []

        for match in matches:
            x, y, conf = match
            is_duplicate = False
            for kept in keep:
                kx, ky, _ = kept
                if abs(x - kx) < min_distance and abs(y - ky) < min_distance:
                    is_duplicate = True
                    break
            if not is_duplicate:
                keep.append(match)

        return keep