"""
拟人化工具模块
为所有输入操作添加随机化，模拟人类操作特征
"""
import random
import time
import math
from typing import Tuple


def random_delay(base_ms: float, variance_pct: float = 0.15) -> None:
    """
    随机延迟，模拟人类反应时间

    Args:
        base_ms: 基准延迟（毫秒）
        variance_pct: 变化幅度百分比（默认±15%）
    """
    min_ms = base_ms * (1.0 - variance_pct)
    max_ms = base_ms * (1.0 + variance_pct)
    delay = random.uniform(min_ms, max_ms) / 1000.0
    time.sleep(max(0.001, delay))


def random_offset(x: int, y: int, radius: int = 3) -> Tuple[int, int]:
    """
    为坐标添加随机偏移，模拟人类点击不精准

    Args:
        x: 原始X坐标
        y: 原始Y坐标
        radius: 最大偏移像素

    Returns:
        (偏移后X, 偏移后Y)
    """
    dx = random.randint(-radius, radius)
    dy = random.randint(-radius, radius)
    return (x + dx, y + dy)


def smooth_move_steps(
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    steps: int = 10,
    curve_factor: float = 0.3
) -> list[Tuple[int, int]]:
    """
    生成贝塞尔曲线平滑移动路径点，模拟人类鼠标移动

    Args:
        start_x, start_y: 起始坐标
        end_x, end_y: 目标坐标
        steps: 插值步数
        curve_factor: 曲线弯曲程度（0=直线，1=大幅弯曲）

    Returns:
        坐标点列表 [(x, y), ...]
    """
    # 生成控制点（二次贝塞尔曲线）
    mid_x = (start_x + end_x) / 2 + random.uniform(-1, 1) * abs(end_x - start_x) * curve_factor
    mid_y = (start_y + end_y) / 2 + random.uniform(-1, 1) * abs(end_y - start_y) * curve_factor

    points = []
    for i in range(steps + 1):
        t = i / steps
        # 二次贝塞尔插值
        bx = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * mid_x + t ** 2 * end_x
        by = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * mid_y + t ** 2 * end_y
        points.append((int(bx), int(by)))

    return points


def relative_move_steps(
    dx: int, dy: int,
    steps: int = 8
) -> list[Tuple[int, int]]:
    """
    将一个大的相对移动拆分成多个小步，模拟人类平滑转向

    Args:
        dx: 总X相对移动量
        dy: 总Y相对移动量
        steps: 拆分步数

    Returns:
        相对移动增量列表 [(delta_x, delta_y), ...]
    """
    if steps <= 1:
        return [(dx, dy)]

    increments = []
    remaining_x = dx
    remaining_y = dy

    for i in range(steps):
        if i == steps - 1:
            # 最后一步补齐剩余
            increments.append((remaining_x, remaining_y))
        else:
            # 加一点随机波动
            ratio = 1.0 / (steps - i)
            step_x = int(remaining_x * ratio * random.uniform(0.8, 1.2))
            step_y = int(remaining_y * ratio * random.uniform(0.8, 1.2))
            increments.append((step_x, step_y))
            remaining_x -= step_x
            remaining_y -= step_y

    return increments


def random_hold_duration(base_ms: float, variance_pct: float = 0.1) -> float:
    """
    随机化按键持续时间

    Args:
        base_ms: 基准时长（毫秒）
        variance_pct: 变化幅度

    Returns:
        随机化后的时长（秒）
    """
    min_ms = base_ms * (1.0 - variance_pct)
    max_ms = base_ms * (1.0 + variance_pct)
    return random.uniform(min_ms, max_ms) / 1000.0