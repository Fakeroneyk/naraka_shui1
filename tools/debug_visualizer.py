"""
调试可视化工具
实时显示YOLO检测结果、小地图位置、游戏状态
方便调试和校准参数

使用方法:
    python tools/debug_visualizer.py
按 'q' 退出
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import cv2
    import numpy as np
    import yaml
except ImportError:
    print("请安装: pip install opencv-python numpy pyyaml")
    sys.exit(1)

from src.vision.screen_capture import ScreenCapture
from src.vision.yolo_detector import YoloDetector, DetectionResult
from src.vision.minimap_reader import MinimapReader
from src.utils.window_manager import WindowManager
from src.utils.timer import FPSCounter


# 检测类别颜色映射（BGR）
CLASS_COLORS = {
    "enemy_normal":   (0, 0, 255),    # 红
    "enemy_elite":    (0, 128, 255),  # 橙
    "enemy_boss":     (0, 0, 180),    # 深红
    "chest_locked":   (128, 128, 0),  # 青
    "chest_unlocked": (0, 255, 0),    # 绿
    "key_item":       (255, 255, 0),  # 黄
    "door_boss":      (255, 0, 255),  # 紫
    "loot_drop":      (0, 255, 255),  # 黄绿
}


def draw_detections(frame_bgr: np.ndarray, detections: DetectionResult) -> np.ndarray:
    """在画面上绘制检测结果"""
    vis = frame_bgr.copy()
    for det in detections.raw:
        color = CLASS_COLORS.get(det.class_name, (200, 200, 200))
        # 绘制边框
        cv2.rectangle(vis, (det.x1, det.y1), (det.x2, det.y2), color, 2)
        # 绘制标签
        label = f"{det.class_name} {det.confidence:.2f}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(vis, (det.x1, det.y1 - lh - 6), (det.x1 + lw, det.y1), color, -1)
        cv2.putText(vis, label, (det.x1, det.y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        # 绘制中心点
        cx, cy = det.center
        cv2.circle(vis, (cx, cy), 3, color, -1)

    return vis


def draw_minimap_info(minimap_bgr: np.ndarray,
                      player_pos: tuple, angle: float) -> np.ndarray:
    """在小地图上绘制玩家位置"""
    vis = minimap_bgr.copy()
    if player_pos:
        px, py = player_pos
        cv2.circle(vis, (px, py), 5, (0, 255, 0), -1)
        # 绘制朝向箭头
        import math
        rad = math.radians(angle)
        ex = int(px + 12 * math.sin(rad))
        ey = int(py - 12 * math.cos(rad))
        cv2.arrowedLine(vis, (px, py), (ex, ey), (0, 255, 0), 2, tipLength=0.4)
        cv2.putText(vis, f"{angle:.0f}°", (2, 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    return vis


def draw_hud(frame_bgr: np.ndarray, fps: float, status: dict) -> np.ndarray:
    """绘制HUD信息"""
    vis = frame_bgr.copy()
    lines = [
        f"FPS: {fps:.1f}",
        f"Enemies: {status.get('enemies', 0)}",
        f"Keys: {status.get('keys', 0)}/3",
        f"Skill F: {'READY' if status.get('skill_ready') else 'CD'}",
    ]
    y = 30
    for line in lines:
        cv2.putText(vis, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 255, 0), 2)
        y += 25
    return vis


def main():
    # 加载配置
    with open("config/game_config.yaml", encoding="utf-8") as f:
        game_cfg = yaml.safe_load(f)

    # 初始化
    wm = WindowManager(game_cfg["game"]["window_title"])
    if not wm.find_window():
        print("未找到游戏窗口")
        sys.exit(1)

    capture = ScreenCapture(region=wm.get_capture_region())
    if not capture.initialize():
        print("截图初始化失败")
        sys.exit(1)

    # 可选：加载YOLO模型
    yolo = None
    yolo_cfg = game_cfg["yolo"]
    if os.path.exists(yolo_cfg["model_path"]):
        yolo = YoloDetector(
            model_path=yolo_cfg["model_path"],
            conf_threshold=yolo_cfg["confidence_threshold"],
        )
        yolo.load()
        print(f"YOLO模型已加载: {yolo_cfg['model_path']}")
    else:
        print(f"YOLO模型不存在: {yolo_cfg['model_path']}，仅显示原始画面")

    minimap_reader = MinimapReader()
    fps_counter = FPSCounter()
    regions = game_cfg["screen_regions"]

    print("=" * 40)
    print("调试可视化工具已启动")
    print("按 'q' 退出 | 按 's' 保存当前帧")
    print("=" * 40)

    save_count = 0

    while True:
        # 截图
        full_frame = capture.grab()
        if full_frame is None:
            time.sleep(0.01)
            continue

        # 转BGR用于显示
        frame_bgr = cv2.cvtColor(full_frame, cv2.COLOR_RGB2BGR)

        # YOLO检测
        detections = None
        enemy_count = 0
        if yolo and yolo.is_loaded:
            detections = yolo.detect(full_frame)
            enemy_count = len(detections.all_enemies)
            frame_bgr = draw_detections(frame_bgr, detections)

        # 小地图
        minimap_frame = capture.grab_region("minimap", regions)
        player_pos = None
        player_angle = 0.0
        if minimap_frame is not None:
            player_pos = minimap_reader.read_player_position(minimap_frame)
            player_angle = minimap_reader.read_player_angle(minimap_frame)
            minimap_bgr = cv2.cvtColor(minimap_frame, cv2.COLOR_RGB2BGR)
            minimap_vis = draw_minimap_info(minimap_bgr, player_pos, player_angle)
            # 叠加小地图到右上角
            mh, mw = minimap_vis.shape[:2]
            frame_bgr[10:10+mh*2, frame_bgr.shape[1]-mw*2-10:frame_bgr.shape[1]-10] = \
                cv2.resize(minimap_vis, (mw*2, mh*2))

        # HUD信息
        fps_counter.tick()
        status = {
            "enemies": enemy_count,
            "keys": 0,
            "skill_ready": True,
        }
        frame_bgr = draw_hud(frame_bgr, fps_counter.fps, status)

        # 缩小显示（1920x1080太大）
        display = cv2.resize(frame_bgr, (1280, 720))
        cv2.imshow("Naraka Bot - Debug", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            filename = f"debug_frame_{save_count:04d}.png"
            cv2.imwrite(filename, frame_bgr)
            print(f"保存帧: {filename}")
            save_count += 1

    cv2.destroyAllWindows()
    capture.release()
    print("调试工具已退出")


if __name__ == "__main__":
    main()
