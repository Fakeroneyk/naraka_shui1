# 🎮 永劫无间 - 征神之路「净水流深·噩梦」自动化脚本

基于 Python + AI 视觉的 PVE 自动刷图脚本，专为宁红夜·百化冰爆流设计。

## 📋 功能特性

- **AI目标检测**：YOLOv8 实时识别敌人、宝箱、钥匙、Boss门
- **智能战斗**：自动连招（化气→蓄力冰爆→闪避取消）、自动瞄准
- **路径导航**：小地图解析定位 + 预设路径点自动导航
- **全自动流程**：出生→清怪→拾取钥匙→开Boss门→击败Boss→通关

## 🧩 技术架构

```
感知层 (BetterCam + YOLOv8 + OpenCV)
  ↓
决策层 (行为树 + 状态机)
  ↓
执行层 (pydirectinput)
```

## ⚡ 快速开始

### 1. 环境要求
- Windows 10/11
- Python 3.10+
- NVIDIA GPU（推荐，加速AI推理）
- 游戏窗口化 1920×1080

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. （可选）准备YOLO模型
脚本可以在没有YOLO模型时运行（降级为纯模板匹配模式），但完整功能需要训练模型：

```bash
# 1. 采集游戏截图
python tools/capture_screenshots.py --interval 2

# 2. 使用 Roboflow 或 CVAT 标注数据

# 3. 训练模型（参考 ultralytics 文档）
# yolo train data=your_dataset.yaml model=yolov8n.pt epochs=50

# 4. 将 best.pt 复制到 models/yolov8n_naraka.pt
```

### 4. 运行脚本
```bash
# 先启动游戏，进入征神之路「净水流深·噩梦」
# 然后运行脚本
python -m src.main
```

### 5. 路径点校准（重要！首次使用必做）
```bash
# 启动游戏并进入净水流深地图，然后运行录制工具
python tools/record_waypoints.py

# 操作：
#   R  - 开始自动录制轨迹（每秒记录一次小地图坐标）
#   M  - 手动标记关键点（怪物点/宝箱/Boss门等），并选择类型
#   P  - 查看已录制的坐标数据
#   S  - 保存为 recorded_waypoints_YYYYMMDD.yaml
#   Q  - 退出

# 录制完成后，将 generated_config 段落内容
# 复制到 config/navigation_config.yaml 替换路径点坐标
```

### 6. 调试工具
```bash
# 测试键鼠模拟
python tools/test_input.py

# 实时可视化调试（查看检测结果+小地图定位）
python tools/debug_visualizer.py

# 采集训练数据截图
python tools/capture_screenshots.py
```

## 📁 项目结构

```
naraka_shui/
├── config/                    # 配置文件
│   ├── game_config.yaml       # 游戏配置（按键、分辨率、YOLO参数）
│   ├── navigation_config.yaml # 导航路径点
│   └── combat_config.yaml     # 战斗连招配置
├── src/
│   ├── main.py                # 主入口
│   ├── vision/                # 感知层
│   │   ├── screen_capture.py  # DXGI高速截图
│   │   ├── yolo_detector.py   # YOLOv8目标检测
│   │   ├── template_matcher.py# 模板匹配（UI识别）
│   │   ├── minimap_reader.py  # 小地图解析
│   │   └── ui_reader.py       # UI状态读取
│   ├── brain/                 # 决策层
│   │   ├── behavior_tree.py   # 行为树框架
│   │   ├── game_state.py      # 游戏状态管理
│   │   ├── bot_brain.py       # 主控制器
│   │   ├── navigator.py       # 导航决策
│   │   └── combat_ai.py       # 战斗AI
│   ├── action/                # 执行层
│   │   ├── input_controller.py# 键鼠模拟
│   │   ├── movement.py        # 移动控制
│   │   ├── combat_actions.py  # 战斗连招
│   │   └── interaction.py     # 拾取/开箱/开门
│   ├── navigation/            # 导航系统
│   │   ├── waypoint_manager.py# 路径点管理
│   │   └── stuck_detector.py  # 卡住检测与脱困
│   └── utils/                 # 工具模块
│       ├── window_manager.py  # 窗口管理
│       ├── logger.py          # 日志系统
│       ├── timer.py           # 计时器
│       └── humanize.py        # 拟人化延迟
├── tools/                     # 辅助工具
│   ├── capture_screenshots.py # 截图采集
│   ├── test_input.py          # 输入测试
│   └── debug_visualizer.py    # 调试可视化
├── models/                    # 模型文件
│   └── templates/             # 模板匹配图片
├── plans/                     # 技术方案文档
│   └── technical-plan.md
├── data/                      # 数据目录
├── logs/                      # 运行日志
├── requirements.txt
└── README.md
```

## ⚙️ 配置说明

### 按键映射（config/game_config.yaml）
根据你的游戏内按键设置修改：
```yaml
keys:
  interact: "e"     # 交互/拾取
  hook: "q"         # 钩索
  skill: "f"        # 技能（化气）
  ultimate: "v"     # 奥义
```

### 路径点校准（config/navigation_config.yaml）
首次使用需要校准小地图坐标，使用调试工具查看实际位置后修改路径点数据。

### 战斗连招（config/combat_config.yaml）
可调整蓄力时间、闪避方向等连招参数。

## ⚠️ 注意事项

1. **仅供学习研究**：本脚本仅用于个人技术学习，请勿用于商业目的
2. **封号风险**：使用自动化脚本可能违反游戏服务条款，存在封号风险
3. **建议使用小号测试**：避免影响主账号
4. **首次使用**：建议先用 `tools/test_input.py` 验证输入模拟是否有效
5. **参数校准**：小地图坐标、UI区域可能需要根据实际分辨率微调