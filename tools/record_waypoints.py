"""
路径点录制工具
用途：在游戏中手动走一遍路线，实时录制小地图坐标，生成路径点数据

使用方法:
    python tools/record_waypoints.py

操作说明:
    - 启动后切换到游戏窗口，正常游玩
    - 按 'R' 开始/暂停录制（自动每秒记录一次坐标）
    - 按 'M' 手动标记一个关键路径点（怪物点位/宝箱/Boss门等）
    - 按 'P' 打印当前已录制的所有坐标
    - 按 'S' 保存录制数据到 YAML 文件
    - 按 'Q' 退出

输出: 生成 recorded_waypoints_YYYYMMDD_HHMMSS.yaml
"""
import os
import sys
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import yaml
    import cv2
    import numpy as np
    import keyboard  # pip install keyboard
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请安装: pip install pyyaml opencv-python numpy keyboard")
    sys.exit(1)

from src.vision.screen_capture import ScreenCapture
from src.vision.minimap_reader import MinimapReader
from src.utils.window_manager import WindowManager


class WaypointRecorder:
    """路径点录制器"""

    def __init__(self, game_config_path: str = "config/game_config.yaml",
                 nav_config_path: str = "config/navigation_config.yaml"):
        # 加载配置
        with open(game_config_path, encoding="utf-8") as f:
            self._game_cfg = yaml.safe_load(f)
        with open(nav_config_path, encoding="utf-8") as f:
            self._nav_cfg = yaml.safe_load(f)

        # 模块
        self._wm: WindowManager = None
        self._capture: ScreenCapture = None
        self._minimap: MinimapReader = None

        # 录制状态
        self._is_recording = False
        self._auto_record_interval = 1.0  # 自动记录间隔（秒）
        self._last_auto_record_time = 0.0

        # 录制数据
        self._auto_points: list[dict] = []      # 自动录制的轨迹点
        self._marked_points: list[dict] = []    # 手动标记的关键点
        self._mark_counter = 0

    def initialize(self) -> bool:
        """初始化"""
        self._wm = WindowManager(self._game_cfg["game"]["window_title"])
        if not self._wm.find_window():
            print("❌ 未找到游戏窗口，请先启动游戏")
            return False

        self._capture = ScreenCapture(region=self._wm.get_capture_region())
        if not self._capture.initialize():
            print("❌ 截图初始化失败")
            return False

        minimap_size = self._nav_cfg["map"]["minimap_size"]
        self._minimap = MinimapReader(minimap_size=tuple(minimap_size))

        print("✅ 初始化完成")
        return True

    def run(self) -> None:
        """主循环"""
        print("\n" + "=" * 50)
        print("🗺️  路径点录制工具")
        print("=" * 50)
        print("操作指南:")
        print("  R  - 开始/暂停自动录制")
        print("  M  - 手动标记关键点（怪物点/宝箱/Boss门等）")
        print("  P  - 打印已录制坐标")
        print("  S  - 保存到YAML文件")
        print("  Q  - 退出")
        print("=" * 50)

        regions = self._game_cfg["screen_regions"]
        show_preview = True

        while True:
            # ─── 键盘监听 ─────────────────────────────────────
            if keyboard.is_pressed('q'):
                print("\n退出录制工具")
                break

            if keyboard.is_pressed('r'):
                self._is_recording = not self._is_recording
                state = "▶ 开始" if self._is_recording else "⏸ 暂停"
                print(f"\n{state}自动录制")
                time.sleep(0.3)  # 防连按

            if keyboard.is_pressed('m'):
                self._manual_mark()
                time.sleep(0.3)

            if keyboard.is_pressed('p'):
                self._print_recorded()
                time.sleep(0.3)

            if keyboard.is_pressed('s'):
                self._save_to_yaml()
                time.sleep(0.3)

            # ─── 截图+定位 ─────────────────────────────────────
            minimap_frame = self._capture.grab_region("minimap", regions)
            if minimap_frame is None:
                time.sleep(0.05)
                continue

            pos = self._minimap.read_player_position(minimap_frame)
            angle = self._minimap.read_player_angle(minimap_frame)

            # ─── 自动录制 ──────────────────────────────────────
            now = time.time()
            if self._is_recording and pos is not None:
                if now - self._last_auto_record_time >= self._auto_record_interval:
                    self._auto_points.append({
                        "time": round(now, 2),
                        "pos": list(pos),
                        "angle": round(angle, 1),
                    })
                    self._last_auto_record_time = now
                    count = len(self._auto_points)
                    print(f"\r  📍 自动录制 #{count}: pos={pos}, angle={angle:.1f}°   ", end="", flush=True)

            # ─── 小地图预览 ────────────────────────────────────
            if show_preview:
                minimap_bgr = cv2.cvtColor(minimap_frame, cv2.COLOR_RGB2BGR)
                vis = self._draw_preview(minimap_bgr, pos, angle)
                # 放大3倍显示
                vis_large = cv2.resize(vis, (vis.shape[1] * 3, vis.shape[0] * 3),
                                       interpolation=cv2.INTER_NEAREST)
                cv2.imshow("Minimap - Waypoint Recorder", vis_large)

                key = cv2.waitKey(30) & 0xFF
                if key == ord('q'):
                    break

            time.sleep(0.03)

        cv2.destroyAllWindows()
        self._capture.release()

    def _manual_mark(self) -> None:
        """手动标记一个关键路径点"""
        pos = self._minimap.last_position
        angle = self._minimap.last_angle

        if pos is None:
            print("\n⚠️ 无法获取当前位置，标记失败")
            return

        self._mark_counter += 1
        point_type = self._ask_point_type()

        mark = {
            "id": f"mark_{self._mark_counter:02d}",
            "type": point_type,
            "pos": list(pos),
            "angle": round(angle, 1),
            "time": round(time.time(), 2),
        }
        self._marked_points.append(mark)
        print(f"\n  📌 标记 #{self._mark_counter}: type={point_type}, pos={pos}, angle={angle:.1f}°")

    @staticmethod
    def _ask_point_type() -> str:
        """快速选择标记类型"""
        print("\n  选择标记类型:")
        print("    1 = 怪物点位  2 = 宝箱  3 = Boss门  4 = 路径拐点  5 = 出生点  6 = 其他")
        type_map = {
            '1': "monster_spot",
            '2': "chest",
            '3': "boss_door",
            '4': "waypoint",
            '5': "spawn",
            '6': "other",
        }
        # 等待按键选择
        while True:
            for key, val in type_map.items():
                if keyboard.is_pressed(key):
                    time.sleep(0.2)
                    return val
            time.sleep(0.05)

    def _print_recorded(self) -> None:
        """打印已录制数据"""
        print("\n" + "=" * 40)
        print(f"📊 录制数据统计:")
        print(f"   自动轨迹点: {len(self._auto_points)} 个")
        print(f"   手动标记点: {len(self._marked_points)} 个")

        if self._marked_points:
            print("\n  📌 手动标记点:")
            for m in self._marked_points:
                print(f"    {m['id']}: type={m['type']}, pos={m['pos']}, angle={m['angle']}°")

        if self._auto_points:
            print(f"\n  📍 轨迹点（最近5个）:")
            for p in self._auto_points[-5:]:
                print(f"    pos={p['pos']}, angle={p['angle']}°")

        print("=" * 40)

    def _save_to_yaml(self) -> None:
        """保存录制数据到YAML文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recorded_waypoints_{timestamp}.yaml"

        # 构建输出数据
        output = {
            "recording_info": {
                "timestamp": timestamp,
                "auto_points_count": len(self._auto_points),
                "marked_points_count": len(self._marked_points),
            },
            "marked_points": self._marked_points,
            "auto_trajectory": self._auto_points,
            # 生成可直接复制到 navigation_config.yaml 的格式
            "generated_config": self._generate_nav_config(),
        }

        with open(filename, "w", encoding="utf-8") as f:
            yaml.dump(output, f, default_flow_style=False, allow_unicode=True)

        print(f"\n💾 数据已保存: {filename}")
        print(f"   包含 {len(self._auto_points)} 个轨迹点 + {len(self._marked_points)} 个标记点")

    def _generate_nav_config(self) -> dict:
        """将标记点转换为 navigation_config.yaml 兼容格式"""
        monster_spots = []
        boss_door = None
        spawn = None
        priority = 1

        for m in self._marked_points:
            if m["type"] == "monster_spot":
                # 找到此标记点之前的轨迹点作为路线
                route = self._extract_route_to_point(m["pos"])
                monster_spots.append({
                    "id": f"spot_{chr(64 + priority)}",
                    "name": f"点位{chr(64 + priority)}（录制标记）",
                    "minimap_pos": m["pos"],
                    "priority": priority,
                    "route_waypoints": route,
                    "approach_key": "walk",
                    "note": f"录制时间: {m.get('time', '')}",
                })
                priority += 1

            elif m["type"] == "boss_door":
                route = self._extract_route_to_point(m["pos"])
                boss_door = {
                    "id": "boss_door",
                    "name": "Boss门（录制标记）",
                    "minimap_pos": m["pos"],
                    "route_waypoints": route,
                    "approach_key": "walk",
                }

            elif m["type"] == "spawn":
                spawn = {
                    "minimap_pos": m["pos"],
                    "description": "出生点（录制标记）",
                }

        result = {}
        if spawn:
            result["spawn"] = spawn
        if monster_spots:
            result["monster_spots"] = monster_spots
        if boss_door:
            result["boss_door"] = boss_door

        return result

    def _extract_route_to_point(self, target_pos: list, max_points: int = 5) -> list:
        """
        从自动轨迹中提取到目标点的路线（均匀采样关键点）

        Args:
            target_pos: 目标坐标
            max_points: 最多提取几个路径点

        Returns:
            路径点列表 [[x,y], ...]
        """
        if not self._auto_points:
            return [target_pos]

        # 找到最接近target_pos的轨迹点索引
        min_dist = float('inf')
        target_idx = len(self._auto_points) - 1
        for i, p in enumerate(self._auto_points):
            dist = ((p["pos"][0] - target_pos[0]) ** 2 +
                    (p["pos"][1] - target_pos[1]) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                target_idx = i

        # 向前取一段轨迹
        start_idx = max(0, target_idx - 20)
        segment = self._auto_points[start_idx:target_idx + 1]

        if not segment:
            return [target_pos]

        # 均匀采样
        step = max(1, len(segment) // max_points)
        route = [segment[i]["pos"] for i in range(0, len(segment), step)]

        # 确保最后一个点是目标
        if route[-1] != target_pos:
            route.append(target_pos)

        return route[-max_points:]

    def _draw_preview(self, minimap_bgr: np.ndarray,
                      player_pos: tuple, angle: float) -> np.ndarray:
        """绘制小地图预览（带轨迹和标记）"""
        vis = minimap_bgr.copy()

        # 绘制自动轨迹（绿色线）
        if len(self._auto_points) >= 2:
            for i in range(1, len(self._auto_points)):
                pt1 = tuple(self._auto_points[i - 1]["pos"])
                pt2 = tuple(self._auto_points[i]["pos"])
                cv2.line(vis, pt1, pt2, (0, 200, 0), 1)

        # 绘制手动标记点
        color_map = {
            "monster_spot": (0, 0, 255),    # 红
            "chest": (0, 255, 255),         # 黄
            "boss_door": (255, 0, 255),     # 紫
            "waypoint": (255, 200, 0),      # 蓝
            "spawn": (0, 255, 0),           # 绿
            "other": (200, 200, 200),       # 灰
        }
        for m in self._marked_points:
            color = color_map.get(m["type"], (200, 200, 200))
            pt = tuple(m["pos"])
            cv2.circle(vis, pt, 4, color, -1)
            cv2.circle(vis, pt, 6, color, 1)
            # 标签
            cv2.putText(vis, m["id"], (pt[0] + 5, pt[1] - 3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.25, color, 1)

        # 绘制玩家位置
        if player_pos:
            px, py = player_pos
            cv2.circle(vis, (px, py), 3, (255, 255, 255), -1)
            # 朝向箭头
            import math
            rad = math.radians(angle)
            ex = int(px + 10 * math.sin(rad))
            ey = int(py - 10 * math.cos(rad))
            cv2.arrowedLine(vis, (px, py), (ex, ey), (255, 255, 255), 1, tipLength=0.4)

        # 录制状态指示器
        if self._is_recording:
            cv2.circle(vis, (8, 8), 5, (0, 0, 255), -1)  # 红色圆点=录制中
            cv2.putText(vis, "REC", (16, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)

        return vis


def main():
    recorder = WaypointRecorder()
    if recorder.initialize():
        recorder.run()


if __name__ == "__main__":
    main()
