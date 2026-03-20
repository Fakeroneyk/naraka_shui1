"""
游戏窗口管理模块
负责查找、定位、激活游戏窗口
"""
import ctypes
from typing import Optional, Tuple
from loguru import logger

try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    logger.warning("pywin32 未安装，窗口管理功能不可用（仅Windows支持）")
    win32gui = None


class WindowManager:
    """游戏窗口管理器"""

    def __init__(self, window_title: str = "永劫无间"):
        self.window_title = window_title
        self._hwnd: Optional[int] = None
        self._window_rect: Optional[Tuple[int, int, int, int]] = None

    def find_window(self) -> bool:
        """
        查找游戏窗口

        Returns:
            True 如果找到窗口
        """
        if win32gui is None:
            logger.error("pywin32 不可用，无法查找窗口")
            return False

        def _enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if self.window_title in title:
                    results.append(hwnd)

        results = []
        win32gui.EnumWindows(_enum_callback, results)

        if results:
            self._hwnd = results[0]
            self._update_rect()
            logger.info("找到游戏窗口: hwnd={}, title='{}'",
                        self._hwnd, win32gui.GetWindowText(self._hwnd))
            return True
        else:
            logger.warning("未找到标题包含 '{}' 的窗口", self.window_title)
            return False

    def _update_rect(self) -> None:
        """更新窗口矩形信息"""
        if self._hwnd and win32gui:
            try:
                self._window_rect = win32gui.GetWindowRect(self._hwnd)
            except Exception as e:
                logger.error("获取窗口矩形失败: {}", e)
                self._window_rect = None

    @property
    def hwnd(self) -> Optional[int]:
        """获取窗口句柄"""
        return self._hwnd

    @property
    def window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口矩形 (left, top, right, bottom)"""
        self._update_rect()
        return self._window_rect

    @property
    def client_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """获取客户区矩形（不含标题栏和边框）"""
        if self._hwnd and win32gui:
            try:
                rect = win32gui.GetClientRect(self._hwnd)
                # 转换为屏幕坐标
                point = win32gui.ClientToScreen(self._hwnd, (0, 0))
                left, top = point
                right = left + rect[2]
                bottom = top + rect[3]
                return (left, top, right, bottom)
            except Exception as e:
                logger.error("获取客户区矩形失败: {}", e)
        return None

    @property
    def client_size(self) -> Tuple[int, int]:
        """获取客户区大小 (width, height)"""
        rect = self.client_rect
        if rect:
            return (rect[2] - rect[0], rect[3] - rect[1])
        return (1920, 1080)  # 默认分辨率

    def activate(self) -> bool:
        """
        激活（前置）游戏窗口

        Returns:
            True 如果成功激活
        """
        if not self._hwnd or not win32gui:
            return False

        try:
            # 如果窗口最小化，先恢复
            if win32gui.IsIconic(self._hwnd):
                win32gui.ShowWindow(self._hwnd, win32con.SW_RESTORE)

            # 置前
            win32gui.SetForegroundWindow(self._hwnd)
            logger.debug("游戏窗口已激活")
            return True
        except Exception as e:
            logger.error("激活窗口失败: {}", e)
            return False

    def is_foreground(self) -> bool:
        """检查游戏窗口是否在前台"""
        if not win32gui:
            return True  # 无法检测时假设在前台
        return win32gui.GetForegroundWindow() == self._hwnd

    def get_capture_region(self) -> Optional[Tuple[int, int, int, int]]:
        """
        获取用于BetterCam截图的区域坐标 (left, top, right, bottom)

        Returns:
            截图区域，或None使用全屏
        """
        rect = self.client_rect
        if rect:
            logger.debug("截图区域: {}", rect)
            return rect
        return None