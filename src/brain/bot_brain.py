"""
机器人大脑 - 主控制器
整合所有模块，驱动完整的游戏流程自动化
"""
import time
import yaml
from typing import Optional
from loguru import logger

# 感知层
from src.vision.screen_capture import ScreenCapture
from src.vision.yolo_detector import YoloDetector
from src.vision.template_matcher import TemplateMatcher
from src.vision.minimap_reader import MinimapReader
from src.vision.ui_reader import UIReader

# 执行层
from src.action.input_controller import InputController
from src.action.movement import MovementController
from src.action.combat_actions import CombatActions
from src.action.interaction import InteractionController

# 导航系统
from src.navigation.waypoint_manager import WaypointManager
from src.navigation.stuck_detector import StuckDetector
from src.navigation.pathfinder import Pathfinder

# 决策层
from src.brain.game_state import GameState, GamePhase
from src.brain.navigator import Navigator
from src.brain.combat_ai import CombatAI

# 工具
from src.utils.window_manager import WindowManager
from src.utils.timer import FPSCounter, Timer
from src.utils.logger import setup_logger


class NarakaBot:
    """
    永劫无间「净水流深·噩梦」自动化机器人

    架构：感知 → 决策 → 执行 主循环 @ 30FPS
    """

    def __init__(self, config_dir: str = "config"):
        self._config_dir = config_dir
        self._running = False

        # 配置
        self._game_cfg: dict = {}
        self._nav_cfg: dict = {}
        self._combat_cfg: dict = {}

        # 模块实例
        self._window_mgr: Optional[WindowManager] = None
        self._capture: Optional[ScreenCapture] = None
        self._yolo: Optional[YoloDetector] = None
        self._template: Optional[TemplateMatcher] = None
        self._minimap: Optional[MinimapReader] = None
        self._ui_reader: Optional[UIReader] = None

        self._input: Optional[InputController] = None
        self._movement: Optional[MovementController] = None
        self._combat_actions: Optional[CombatActions] = None
        self._interaction: Optional[InteractionController] = None

        self._waypoints: Optional[WaypointManager] = None
        self._stuck: Optional[StuckDetector] = None
        self._pathfinder: Optional[Pathfinder] = None
        self._navigator: Optional[Navigator] = None
        self._combat_ai: Optional[CombatAI] = None

        # 状态与性能
        self._state = GameState()
        self._fps_counter = FPSCounter()

    # ─── 初始化 ────────────────────────────────────────────────────────

    def initialize(self) -> bool:
        """初始化所有模块"""
        setup_logger("INFO")
        logger.info("=" * 50)
        logger.info("永劫无间 净水流深·噩梦 自动化脚本 启动")
        logger.info("=" * 50)

        # 1. 加载配置
        if not self._load_configs():
            return False

        # 2. 窗口管理
        self._window_mgr = WindowManager(
            self._game_cfg["game"]["window_title"]
        )
        if not self._window_mgr.find_window():
            logger.error("未找到游戏窗口，请先启动游戏")
            return False

        # 3. 屏幕采集
        capture_region = self._window_mgr.get_capture_region()
        self._capture = ScreenCapture(region=capture_region)
        if not self._capture.initialize():
            logger.error("截图初始化失败")
            return False

        # 4. YOLO检测器
        yolo_cfg = self._game_cfg["yolo"]
        self._yolo = YoloDetector(
            model_path=yolo_cfg["model_path"],
            conf_threshold=yolo_cfg["confidence_threshold"],
            imgsz=yolo_cfg["inference_size"],
            device=yolo_cfg["device"],
        )
        self._yolo.load()  # 失败时仍可运行（降级为纯模板匹配）

        # 5. 模板匹配器
        tm_cfg = self._game_cfg["template_matching"]
        self._template = TemplateMatcher(
            templates_dir=tm_cfg["templates_dir"],
            threshold=tm_cfg["threshold"],
        )
        self._template.load_templates(tm_cfg["templates"])

        # 6. 小地图读取器
        minimap_size = self._nav_cfg["map"]["minimap_size"]
        self._minimap = MinimapReader(minimap_size=tuple(minimap_size))

        # 7. UI读取器
        self._ui_reader = UIReader(self._template, self._game_cfg["screen_regions"])

        # 8. 输入控制器
        mouse_cfg = self._game_cfg["mouse"]
        self._input = InputController(mouse_sensitivity=mouse_cfg["sensitivity"])

        # 9. 移动控制器
        self._movement = MovementController(self._input, self._game_cfg["keys"])

        # 10. 战斗动作
        self._combat_actions = CombatActions(
            self._input, self._movement,
            self._game_cfg["keys"], self._combat_cfg
        )

        # 11. 交互控制器
        self._interaction = InteractionController(self._input, self._game_cfg["keys"])

        # 12. 路径点管理器
        self._waypoints = WaypointManager(self._nav_cfg)

        # 13. 卡住检测器
        self._stuck = StuckDetector(self._movement, self._input, self._nav_cfg)

        # 14. A* 寻路器
        minimap_size = self._nav_cfg.get("map", {}).get("minimap_size", [160, 160])
        self._pathfinder = Pathfinder(
            grid_width=minimap_size[0],
            grid_height=minimap_size[1],
        )

        # 15. 导航器（集成 Pathfinder）
        self._navigator = Navigator(
            self._movement, self._waypoints, self._stuck, self._nav_cfg,
            pathfinder=self._pathfinder,
        )

        # 16. 战斗AI
        self._combat_ai = CombatAI(
            self._combat_actions, self._movement,
            self._interaction, self._combat_cfg
        )

        logger.info("✅ 所有模块初始化完成")
        return True

    def _load_configs(self) -> bool:
        """加载所有配置文件"""
        try:
            with open(f"{self._config_dir}/game_config.yaml", encoding="utf-8") as f:
                self._game_cfg = yaml.safe_load(f)
            with open(f"{self._config_dir}/navigation_config.yaml", encoding="utf-8") as f:
                self._nav_cfg = yaml.safe_load(f)
            with open(f"{self._config_dir}/combat_config.yaml", encoding="utf-8") as f:
                self._combat_cfg = yaml.safe_load(f)
            logger.info("配置文件加载成功")
            return True
        except Exception as e:
            logger.error("配置文件加载失败: {}", e)
            return False

    # ─── 主循环 ────────────────────────────────────────────────────────

    def run(self) -> None:
        """启动主控制循环"""
        self._running = True
        self._state.change_phase(GamePhase.SPAWNED)
        logger.info("主循环启动，目标FPS: {}", self._game_cfg["game"]["target_fps"])

        target_frame_time = 1.0 / self._game_cfg["game"]["target_fps"]

        try:
            while self._running:
                frame_start = time.perf_counter()

                # ── 感知 ──────────────────────────────────────────────
                self._perception_step()

                # ── 决策+执行 ────────────────────────────────────────
                self._decision_step()

                # ── 帧率控制 ─────────────────────────────────────────
                elapsed = time.perf_counter() - frame_start
                sleep_time = target_frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

                fps = 1.0 / (time.perf_counter() - frame_start)
                self._fps_counter.tick()

        except KeyboardInterrupt:
            logger.info("收到中断信号，停止运行")
        finally:
            self._cleanup()

    def _perception_step(self) -> None:
        """感知步骤：截图 → AI检测 → UI读取 → 状态更新"""
        regions = self._game_cfg["screen_regions"]

        # 1. 全屏截图（战斗视野）
        full_frame = self._capture.grab()
        if full_frame is None:
            return

        # 2. YOLO目标检测
        if self._yolo and self._yolo.is_loaded:
            detection = self._yolo.detect(full_frame)
            self._state.update_from_detection(detection)

        # 3. 小地图解析（裁取小地图区域）
        minimap_frame = self._capture.grab_region("minimap", regions)
        if minimap_frame is not None:
            pos = self._minimap.read_player_position(minimap_frame)
            angle = self._minimap.read_player_angle(minimap_frame)
            self._state.update_position(pos, angle)

        # 4. UI状态读取
        frames = {
            "skill_bar": self._capture.grab_region("skill_bar", regions),
            "interact_prompt": self._capture.grab_region("interact_prompt", regions),
            "item_bar": self._capture.grab_region("item_bar", regions),
            "health_bar": self._capture.grab_region("health_bar", regions),
        }
        ui_data = self._ui_reader.read_all(frames)
        self._state.update_from_ui(ui_data)

    def _decision_step(self) -> None:
        """决策步骤：根据游戏阶段执行对应逻辑"""
        phase = self._state.phase

        if phase == GamePhase.SPAWNED:
            self._handle_spawned()

        elif phase == GamePhase.NAVIGATING:
            self._handle_navigating()

        elif phase == GamePhase.EXPLORING_SPOT:
            self._handle_exploring()

        elif phase == GamePhase.COMBAT:
            self._handle_combat()

        elif phase == GamePhase.LOOTING:
            self._handle_looting()

        elif phase == GamePhase.NAVIGATE_TO_BOSS:
            self._handle_navigate_to_boss()

        elif phase == GamePhase.OPEN_DOOR:
            self._handle_open_door()

        elif phase == GamePhase.BOSS_FIGHT:
            self._handle_boss_fight()

        elif phase == GamePhase.VICTORY:
            self._handle_victory()

    # ─── 各阶段处理逻辑 ────────────────────────────────────────────────

    def _handle_spawned(self) -> None:
        """刚出生：激活游戏窗口，选择第一个目标点位"""
        self._window_mgr.activate()
        time.sleep(0.5)

        # 选择第一个（最近的）未探索点位
        spot = self._waypoints.get_nearest_undone_spot(
            self._state.player_minimap_pos or (80, 140)
        )
        if spot:
            self._navigator.set_target_spot(spot)
            self._state.current_target_spot_id = spot.id
            self._state.change_phase(GamePhase.NAVIGATING, timeout=120.0)
            logger.info("出生，前往第一个点位: {}", spot.name)

    def _handle_navigating(self) -> None:
        """导航阶段：向目标点位移动"""
        # 超时保护
        if self._state.is_phase_timed_out():
            logger.warning("导航超时，跳到下一个点位")
            self._skip_to_next_spot()
            return

        # 导航中如果发现敌人，立即进入战斗
        if self._state.enemy_count > 0:
            self._movement.stop_movement()
            self._state.change_phase(GamePhase.COMBAT, timeout=90.0)
            spot_id = self._state.current_target_spot_id
            if spot_id:
                self._waypoints.mark_spot_active(spot_id)
            logger.info("导航中发现敌人({})，切换至战斗模式", self._state.enemy_count)
            return

        # 执行导航步骤
        arrived = self._navigator.navigate_step(self._state)

        if arrived:
            self._state.change_phase(GamePhase.EXPLORING_SPOT, timeout=10.0)
            logger.info("到达目标点位，开始探索")

    def _handle_exploring(self) -> None:
        """探索点位：检测是否有怪物"""
        # 短暂等待后判断
        if self._state.phase_elapsed() < 2.0:
            return

        spot_id = self._state.current_target_spot_id

        if self._state.enemy_count > 0:
            # 有怪物
            if spot_id:
                self._waypoints.mark_spot_active(spot_id)
            self._state.change_phase(GamePhase.COMBAT, timeout=90.0)
            logger.info("探索点位有怪物({})，进入战斗", self._state.enemy_count)
        else:
            # 无怪物，标记为空点
            if spot_id:
                self._waypoints.mark_spot_empty(spot_id)
                self._state.explored_spot_ids.add(spot_id)
            self._skip_to_next_spot()
            logger.info("探索点位无怪物，跳至下一个点位")

    def _handle_combat(self) -> None:
        """战斗阶段：执行战斗AI直到清怪"""
        # 超时保护
        if self._state.is_phase_timed_out():
            logger.warning("战斗超时，强制结束")
            self._after_combat()
            return

        if self._combat_ai.is_combat_finished(self._state):
            logger.info("战斗结束，切换至拾取阶段")
            self._after_combat()
            return

        # 执行战斗AI
        action = self._combat_ai.execute_combat_tick(self._state)
        logger.trace("战斗动作: {}", action)

    def _after_combat(self) -> None:
        """清怪后处理"""
        spot_id = self._state.current_target_spot_id
        if spot_id:
            self._waypoints.mark_spot_cleared(spot_id)
            self._state.cleared_spot_count += 1

        time.sleep(1.5)  # 等待掉落物生成
        self._state.change_phase(GamePhase.LOOTING, timeout=20.0)

    def _handle_looting(self) -> None:
        """拾取阶段：开箱、拾取钥匙等道具"""
        if self._state.is_phase_timed_out():
            logger.info("拾取超时，继续下一步")
            self._after_looting()
            return

        # 检测到宝箱交互提示
        if self._state.chest_prompt_visible:
            self._interaction.open_chest()
            logger.info("开箱")
            return

        # 检测到E交互提示（钥匙或道具）
        if self._state.interact_prompt_visible:
            self._interaction.interact()
            logger.info("拾取道具")
            return

        # YOLO检测到宝箱（已解锁）
        if self._state.detection and self._state.detection.chests_unlocked:
            # 走向宝箱
            chest = self._state.detection.chests_unlocked[0]
            self._movement.aim_at_target(chest.center[0], chest.center[1])
            self._movement.move_forward(300)
            return

        # YOLO检测到地面掉落物
        if self._state.detection and self._state.detection.loot_drops:
            loot = self._state.detection.loot_drops[0]
            self._movement.aim_at_target(loot.center[0], loot.center[1])
            self._movement.move_forward(200)
            self._interaction.pickup_loot()
            return

        # 区域扫荡拾取
        self._interaction.loot_area_sweep()
        time.sleep(0.5)
        self._after_looting()

    def _after_looting(self) -> None:
        """拾取完成后，决定下一步"""
        logger.info("拾取完成，钥匙: {}/3，已清怪: {}个",
                    self._state.key_count, self._state.cleared_spot_count)

        if self._state.has_all_keys:
            logger.info("🔑 集齐3把钥匙！前往Boss门")
            self._state.change_phase(GamePhase.NAVIGATE_TO_BOSS, timeout=120.0)
            boss_door = self._waypoints.boss_door
            if boss_door:
                self._navigator.set_target_waypoint(boss_door)
        else:
            self._skip_to_next_spot()

    def _handle_navigate_to_boss(self) -> None:
        """前往Boss门"""
        if self._state.is_phase_timed_out():
            logger.warning("前往Boss门超时")
            return

        arrived = self._navigator.navigate_step(self._state)
        if arrived:
            self._state.change_phase(GamePhase.OPEN_DOOR, timeout=15.0)
            logger.info("到达Boss门，准备开门")

    def _handle_open_door(self) -> None:
        """开Boss门"""
        if self._state.interact_prompt_visible or self._state.phase_elapsed() > 2.0:
            self._interaction.open_boss_door()
            # 进入Boss房后导航到Boss战位置
            boss_arena = self._waypoints.boss_arena
            if boss_arena:
                self._navigator.set_target_waypoint(boss_arena)
            self._state.change_phase(GamePhase.BOSS_FIGHT, timeout=300.0)
            logger.info("🚪 Boss门已开启，进入Boss房")

    def _handle_boss_fight(self) -> None:
        """Boss战斗"""
        if self._state.is_phase_timed_out():
            logger.warning("Boss战超时，脚本可能需要调整")
            return

        # Boss被击败（无检测到Boss）
        if self._state.detection and not self._state.detection.enemies_boss:
            if self._state.phase_elapsed() > 10.0:
                logger.info("🎉 Boss已击败！")
                self._state.change_phase(GamePhase.VICTORY)
                return

        # 执行Boss战策略
        action = self._combat_ai.execute_boss_strategy(self._state)
        logger.trace("Boss战动作: {}", action)

    def _handle_victory(self) -> None:
        """通关"""
        logger.info("=" * 40)
        logger.info("🏆 通关成功！净水流深·噩梦")
        logger.info("=" * 40)
        self._running = False

    # ─── 辅助方法 ──────────────────────────────────────────────────────

    def _skip_to_next_spot(self) -> None:
        """跳转到下一个未完成的点位"""
        player_pos = self._state.player_minimap_pos or (80, 140)
        next_spot = self._waypoints.get_nearest_undone_spot(player_pos)

        if next_spot is None:
            # 所有点位探索完毕，但钥匙不足
            if not self._state.has_all_keys:
                logger.warning("所有点位已探索，但钥匙不足3把！cleared={}", self._state.cleared_spot_count)
                # 重新探索已清怪点位（可能有遗漏的掉落物）
                self._state.change_phase(GamePhase.LOOTING, timeout=15.0)
            return

        self._navigator.set_target_spot(next_spot)
        self._state.current_target_spot_id = next_spot.id
        self._state.change_phase(GamePhase.NAVIGATING, timeout=120.0)
        logger.info("切换目标点位: {}", next_spot.name)

    def _cleanup(self) -> None:
        """清理资源，释放所有按键"""
        logger.info("清理资源...")
        if self._input:
            self._input.release_all_keys()
        if self._movement:
            self._movement.stop_movement()
        if self._capture:
            self._capture.release()
        logger.info("资源清理完成")

    def stop(self) -> None:
        """外部停止脚本"""
        self._running = False
        logger.info("接收到停止指令")