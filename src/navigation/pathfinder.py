"""
A* 寻路模块
基于小地图栅格化数据的路径搜索，支持动态障碍物规避

用途：
    - 当预设路径点无法直达时，计算绕行路径
    - 从玩家当前位置到任意目标的实时路径规划
    - 结合小地图地形识别生成可行走区域图
"""
import heapq
import math
from typing import Optional, Tuple
from loguru import logger

try:
    from pathfinding.core.diagonal_movement import DiagonalMovement
    from pathfinding.core.grid import Grid
    from pathfinding.finder.a_star import AStarFinder
    _HAS_PATHFINDING_LIB = True
except ImportError:
    _HAS_PATHFINDING_LIB = False
    logger.debug("python-pathfinding 未安装，使用内置A*实现")

import numpy as np


# ─── 内置轻量级 A* 实现 ──────────────────────────────────────────────────────

class _Node:
    """A* 搜索节点"""
    __slots__ = ("x", "y", "g", "h", "f", "parent")

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.g: float = 0.0    # 起点到当前的实际代价
        self.h: float = 0.0    # 当前到终点的启发式估计
        self.f: float = 0.0    # g + h
        self.parent: Optional["_Node"] = None

    def __lt__(self, other: "_Node"):
        return self.f < other.f

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))


def _builtin_astar(
    grid: np.ndarray,
    start: Tuple[int, int],
    end: Tuple[int, int],
    allow_diagonal: bool = True,
) -> list[Tuple[int, int]]:
    """
    内置A*寻路实现（不依赖外部库）

    Args:
        grid: 二维数组，1=可走，0=障碍
        start: 起点 (x, y)
        end: 终点 (x, y)
        allow_diagonal: 是否允许对角线移动

    Returns:
        路径坐标列表 [(x, y), ...]，空列表表示无路径
    """
    rows, cols = grid.shape

    # 边界检查
    if not (0 <= start[0] < cols and 0 <= start[1] < rows):
        return []
    if not (0 <= end[0] < cols and 0 <= end[1] < rows):
        return []
    if grid[start[1], start[0]] == 0 or grid[end[1], end[0]] == 0:
        return []

    # 方向定义
    if allow_diagonal:
        directions = [
            (0, 1), (0, -1), (1, 0), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        ]
    else:
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    start_node = _Node(start[0], start[1])
    end_node = _Node(end[0], end[1])

    open_list: list[_Node] = []
    closed_set: set[Tuple[int, int]] = set()

    heapq.heappush(open_list, start_node)

    while open_list:
        current = heapq.heappop(open_list)

        if current.x == end_node.x and current.y == end_node.y:
            # 回溯路径
            path = []
            node = current
            while node is not None:
                path.append((node.x, node.y))
                node = node.parent
            path.reverse()
            return path

        closed_set.add((current.x, current.y))

        for dx, dy in directions:
            nx, ny = current.x + dx, current.y + dy

            if not (0 <= nx < cols and 0 <= ny < rows):
                continue
            if grid[ny, nx] == 0:
                continue
            if (nx, ny) in closed_set:
                continue

            # 对角线代价为 √2
            move_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
            g = current.g + move_cost
            h = math.sqrt((nx - end_node.x) ** 2 + (ny - end_node.y) ** 2)
            f = g + h

            neighbor = _Node(nx, ny)
            neighbor.g = g
            neighbor.h = h
            neighbor.f = f
            neighbor.parent = current

            # 检查open_list中是否已有更好的路径到达此点
            skip = False
            for i, node in enumerate(open_list):
                if node.x == nx and node.y == ny:
                    if node.f <= f:
                        skip = True
                    else:
                        open_list[i] = neighbor
                        heapq.heapify(open_list)
                        skip = True
                    break

            if not skip:
                heapq.heappush(open_list, neighbor)

    return []  # 无路径


# ─── Pathfinder 主类 ────────────────────────────────────────────────────────

class Pathfinder:
    """
    A* 寻路器

    支持两种后端：
    1. python-pathfinding 库（如已安装）
    2. 内置轻量级A*实现（回退方案）

    网格坐标系与小地图一致：
    - x → 水平方向（左到右）
    - y → 垂直方向（上到下）
    - grid[y][x] = 1 表示可走，0 表示障碍
    """

    def __init__(self, grid_width: int = 160, grid_height: int = 160):
        """
        Args:
            grid_width: 网格宽度（与小地图像素宽一致）
            grid_height: 网格高度
        """
        self._width = grid_width
        self._height = grid_height
        # 默认全部可走
        self._grid_data = np.ones((grid_height, grid_width), dtype=np.int8)
        self._backend = "pathfinding" if _HAS_PATHFINDING_LIB else "builtin"
        logger.info("寻路器初始化: {}x{}, 后端: {}", grid_width, grid_height, self._backend)

    # ─── 地图管理 ──────────────────────────────────────────────────────

    def set_grid(self, grid: np.ndarray) -> None:
        """
        设置可行走区域网格

        Args:
            grid: 二维数组，1=可走，0=障碍物
        """
        self._grid_data = grid.astype(np.int8)
        logger.debug("寻路网格已更新: shape={}", grid.shape)

    def set_obstacle(self, x: int, y: int) -> None:
        """标记一个格子为障碍物"""
        if 0 <= x < self._width and 0 <= y < self._height:
            self._grid_data[y, x] = 0

    def set_walkable(self, x: int, y: int) -> None:
        """标记一个格子为可走"""
        if 0 <= x < self._width and 0 <= y < self._height:
            self._grid_data[y, x] = 1

    def set_obstacles_rect(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """设置矩形区域为障碍物"""
        y1c = max(0, min(y1, self._height))
        y2c = max(0, min(y2, self._height))
        x1c = max(0, min(x1, self._width))
        x2c = max(0, min(x2, self._width))
        self._grid_data[y1c:y2c, x1c:x2c] = 0

    def update_from_minimap(self, minimap_frame: np.ndarray) -> None:
        """
        从小地图截图自动识别障碍物（地形分析）

        通过HSV色彩空间区分可行走区域（浅色/水域）和障碍物（深色/墙壁）

        Args:
            minimap_frame: 小地图RGB图像
        """
        import cv2

        try:
            hsv = cv2.cvtColor(minimap_frame, cv2.COLOR_RGB2HSV)

            # 障碍物通常为深色区域（低亮度）
            # 可行走区域为浅色（高亮度）
            _, _, v_channel = cv2.split(hsv)

            # 二值化：亮度大于阈值 = 可走
            threshold = 80
            walkable_mask = (v_channel > threshold).astype(np.int8)

            # 形态学处理去噪
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            walkable_mask = cv2.morphologyEx(walkable_mask, cv2.MORPH_CLOSE, kernel)

            # 调整尺寸匹配网格
            if walkable_mask.shape != (self._height, self._width):
                walkable_mask = cv2.resize(
                    walkable_mask, (self._width, self._height),
                    interpolation=cv2.INTER_NEAREST
                )

            self._grid_data = walkable_mask
            walkable_pct = np.sum(walkable_mask) / walkable_mask.size * 100
            logger.trace("地形分析完成: {:.1f}% 可走", walkable_pct)

        except Exception as e:
            logger.trace("小地图地形分析失败: {}", e)

    # ─── 寻路接口 ──────────────────────────────────────────────────────

    def find_path(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        allow_diagonal: bool = True,
    ) -> list[Tuple[int, int]]:
        """
        计算从起点到终点的最短路径

        Args:
            start: 起点 (x, y)
            end: 终点 (x, y)
            allow_diagonal: 是否允许对角线移动

        Returns:
            路径坐标列表 [(x, y), ...]，空列表表示无路径
        """
        if self._backend == "pathfinding" and _HAS_PATHFINDING_LIB:
            return self._find_path_lib(start, end, allow_diagonal)
        else:
            return _builtin_astar(self._grid_data, start, end, allow_diagonal)

    def _find_path_lib(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        allow_diagonal: bool = True,
    ) -> list[Tuple[int, int]]:
        """使用 python-pathfinding 库寻路"""
        try:
            matrix = self._grid_data.tolist()
            grid = Grid(matrix=matrix)

            start_node = grid.node(start[0], start[1])
            end_node = grid.node(end[0], end[1])

            movement = DiagonalMovement.always if allow_diagonal else DiagonalMovement.never
            finder = AStarFinder(diagonal_movement=movement)

            path, _ = finder.find_path(start_node, end_node, grid)

            return [(p.x, p.y) for p in path]
        except Exception as e:
            logger.warning("python-pathfinding 寻路失败: {}，回退到内置实现", e)
            return _builtin_astar(self._grid_data, start, end, allow_diagonal)

    def simplify_path(
        self, path: list[Tuple[int, int]], tolerance: float = 3.0
    ) -> list[Tuple[int, int]]:
        """
        简化路径（移除冗余中间点，保留关键拐点）

        使用 Ramer-Douglas-Peucker 算法

        Args:
            path: 原始路径
            tolerance: 简化容差（像素）

        Returns:
            简化后的路径
        """
        if len(path) <= 2:
            return path

        return self._rdp(path, tolerance)

    def _rdp(
        self, points: list[Tuple[int, int]], epsilon: float
    ) -> list[Tuple[int, int]]:
        """Ramer-Douglas-Peucker 路径简化"""
        if len(points) <= 2:
            return points

        # 找到距首尾连线最远的点
        start = np.array(points[0], dtype=float)
        end = np.array(points[-1], dtype=float)
        line_vec = end - start
        line_len = np.linalg.norm(line_vec)

        max_dist = 0.0
        max_idx = 0

        for i in range(1, len(points) - 1):
            pt = np.array(points[i], dtype=float)
            if line_len == 0:
                dist = np.linalg.norm(pt - start)
            else:
                # 点到线段的距离
                t = max(0, min(1, np.dot(pt - start, line_vec) / (line_len ** 2)))
                proj = start + t * line_vec
                dist = np.linalg.norm(pt - proj)

            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > epsilon:
            # 递归简化
            left = self._rdp(points[:max_idx + 1], epsilon)
            right = self._rdp(points[max_idx:], epsilon)
            return left[:-1] + right
        else:
            return [points[0], points[-1]]

    # ─── 辅助接口 ──────────────────────────────────────────────────────

    def is_walkable(self, x: int, y: int) -> bool:
        """检查某个坐标是否可走"""
        if 0 <= x < self._width and 0 <= y < self._height:
            return self._grid_data[y, x] == 1
        return False

    def get_path_length(self, path: list[Tuple[int, int]]) -> float:
        """计算路径总长度"""
        if len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(path)):
            dx = path[i][0] - path[i - 1][0]
            dy = path[i][1] - path[i - 1][1]
            total += math.sqrt(dx * dx + dy * dy)
        return total

    @property
    def grid(self) -> np.ndarray:
        """获取当前网格数据"""
        return self._grid_data.copy()

    @property
    def walkable_ratio(self) -> float:
        """可走区域比例"""
        return float(np.sum(self._grid_data)) / self._grid_data.size