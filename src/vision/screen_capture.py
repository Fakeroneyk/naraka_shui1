"""
屏幕采集模块
基于 BetterCam (DXGI Desktop Duplication API) 实现高速截图
"""
import numpy as np
from typing import Optional, Tuple
from loguru import logger

try:
    import bettercam
except ImportError:
    bettercam = None
    logger.warning("bettercam 未安装，将回退到 mss 截图")

try:
    from mss import mss
except ImportError:
    mss = None


class ScreenCapture:
    """高性能屏幕采集器"""

    def __init__(self, region: Optional[Tuple[int, int, int, int]] = None):
        """
        Args:
            region: 截图区域 (left, top, right, bottom)，None为全屏
        """
        self._region = region
        self._camera = None
        self._mss = None
        self._backend = "none"

    def initialize(self) -> bool:
        """初始化截图后端"""
        # 优先使用 BetterCam
        if bettercam is not None:
            try:
                self._camera = bettercam.create(output_color="RGB")
                self._backend = "bettercam"
                logger.info("截图后端: BetterCam (DXGI) 初始化成功")
                return True
            except Exception as e:
                logger.warning("BetterCam 初始化失败: {}，回退到 mss", e)

        # 回退到 mss
        if mss is not None:
            self._mss = mss()
            self._backend = "mss"
            logger.info("截图后端: mss 初始化成功")
            return True

        logger.error("无可用的截图后端！请安装 bettercam 或 mss")
        return False

    def grab(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """
        采集一帧画面

        Args:
            region: 自定义截图区域，不传则使用初始化时设定的区域

        Returns:
            RGB格式的numpy数组 (H, W, 3)，失败返回None
        """
        capture_region = region or self._region

        if self._backend == "bettercam" and self._camera:
            return self._grab_bettercam(capture_region)
        elif self._backend == "mss" and self._mss:
            return self._grab_mss(capture_region)
        else:
            return None

    def _grab_bettercam(self, region: Optional[Tuple[int, int, int, int]]) -> Optional[np.ndarray]:
        """BetterCam 截图"""
        try:
            frame = self._camera.grab(region=region)
            return frame  # 已经是 RGB numpy array
        except Exception as e:
            logger.trace("BetterCam grab 失败: {}", e)
            return None

    def _grab_mss(self, region: Optional[Tuple[int, int, int, int]]) -> Optional[np.ndarray]:
        """mss 截图（回退方案）"""
        try:
            if region:
                monitor = {
                    "left": region[0],
                    "top": region[1],
                    "width": region[2] - region[0],
                    "height": region[3] - region[1],
                }
            else:
                monitor = self._mss.monitors[1]  # 主显示器

            screenshot = self._mss.grab(monitor)
            frame = np.array(screenshot)
            # mss 返回 BGRA，转为 RGB
            frame = frame[:, :, :3]  # 去除Alpha
            frame = frame[:, :, ::-1]  # BGR -> RGB
            return frame
        except Exception as e:
            logger.trace("mss grab 失败: {}", e)
            return None

    def grab_region(self, region_name: str, regions_config: dict, window_offset: Optional[Tuple[int, int]] = None) -> Optional[np.ndarray]:
        """
        根据配置名称截取特定UI区域

        Args:
            region_name: 区域名称（如 "minimap", "skill_bar"）
            regions_config: screen_regions 配置字典
            window_offset: 窗口偏移量 (left, top)，配置文件中的坐标是相对于窗口的

        Returns:
            截取的图像，或None
        """
        if region_name not in regions_config:
            logger.warning("未知的截图区域: {}", region_name)
            return None

        cfg = regions_config[region_name]
        # 坐标转换：配置中是相对于窗口的偏移，需要加上窗口在屏幕上的绝对位置
        if window_offset:
            ox, oy = window_offset
            region = (cfg["left"] + ox, cfg["top"] + oy, cfg["right"] + ox, cfg["bottom"] + oy)
        else:
            region = (cfg["left"], cfg["top"], cfg["right"], cfg["bottom"])
        return self.grab(region=region)

    def release(self) -> None:
        """释放截图资源"""
        if self._camera:
            try:
                del self._camera
            except Exception:
                pass
            self._camera = None
        self._backend = "none"
        logger.info("截图资源已释放")

    @property
    def backend_name(self) -> str:
        """获取当前使用的截图后端名称"""
        return self._backend