"""
计时器与性能监控模块
"""
import time
from typing import Optional
from loguru import logger


class Timer:
    """高精度计时器，用于性能监控和冷却管理"""

    def __init__(self, name: str = "default"):
        self.name = name
        self._start_time: float = 0.0
        self._elapsed: float = 0.0

    def start(self) -> "Timer":
        """开始计时"""
        self._start_time = time.perf_counter()
        return self

    def stop(self) -> float:
        """停止计时并返回耗时（毫秒）"""
        self._elapsed = (time.perf_counter() - self._start_time) * 1000
        return self._elapsed

    @property
    def elapsed_ms(self) -> float:
        """获取上次计时耗时（毫秒）"""
        return self._elapsed

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
        logger.trace("[Timer:{}] {:.2f}ms", self.name, self._elapsed)


class CooldownTracker:
    """技能冷却追踪器"""

    def __init__(self):
        self._cooldowns: dict[str, float] = {}  # key -> 上次使用时间戳

    def use(self, skill_name: str) -> None:
        """记录技能使用时间"""
        self._cooldowns[skill_name] = time.perf_counter()

    def is_ready(self, skill_name: str, cooldown_ms: float) -> bool:
        """
        检查技能是否已冷却完毕

        Args:
            skill_name: 技能名称
            cooldown_ms: 冷却时间（毫秒）

        Returns:
            True 如果技能可用
        """
        if skill_name not in self._cooldowns:
            return True
        elapsed = (time.perf_counter() - self._cooldowns[skill_name]) * 1000
        return elapsed >= cooldown_ms

    def remaining_ms(self, skill_name: str, cooldown_ms: float) -> float:
        """
        获取剩余冷却时间（毫秒）

        Returns:
            剩余冷却时间，0表示已就绪
        """
        if skill_name not in self._cooldowns:
            return 0.0
        elapsed = (time.perf_counter() - self._cooldowns[skill_name]) * 1000
        remaining = cooldown_ms - elapsed
        return max(0.0, remaining)

    def reset(self, skill_name: Optional[str] = None) -> None:
        """重置冷却记录"""
        if skill_name:
            self._cooldowns.pop(skill_name, None)
        else:
            self._cooldowns.clear()


class FPSCounter:
    """帧率计数器"""

    def __init__(self, sample_size: int = 60):
        self._sample_size = sample_size
        self._frame_times: list[float] = []
        self._last_time: float = time.perf_counter()

    def tick(self) -> float:
        """记录一帧，返回当前帧耗时（毫秒）"""
        now = time.perf_counter()
        frame_time = (now - self._last_time) * 1000
        self._last_time = now

        self._frame_times.append(frame_time)
        if len(self._frame_times) > self._sample_size:
            self._frame_times.pop(0)

        return frame_time

    @property
    def fps(self) -> float:
        """获取平均FPS"""
        if not self._frame_times:
            return 0.0
        avg_ms = sum(self._frame_times) / len(self._frame_times)
        return 1000.0 / avg_ms if avg_ms > 0 else 0.0

    @property
    def avg_frame_time_ms(self) -> float:
        """获取平均帧耗时（毫秒）"""
        if not self._frame_times:
            return 0.0
        return sum(self._frame_times) / len(self._frame_times)