# M1A

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的《异世界的城主大人》自动化项目，遵循 [ProjectInterface V2](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.3-ProjectInterfaceV2%E5%8D%8F%E8%AE%AE.md) 协议，可直接被 MXU 等通用客户端加载。

- 控制器：ADB（Android 设备 / 模拟器）
- 运行环境：Windows + Python 3.12（项目自带 `.venv`）
- 流水线坐标按 **1280×720** 标定

## 功能

- **日常任务**：一键每日每周、领取体力、盛宴、七日特惠、限时回馈、Tap 签到、知识问答、特产运输、庄园、联盟、竞技场、召唤、记忆空间、魔法园、个人 Boss、世界 Boss
- **周常任务**：深渊、藏宝洞
- **每日预设**：一条任务链即可完成「开游戏 → 日常 → 关游戏」
- **Boss 可选**：个人 / 世界 Boss 支持 9 档 Boss（lv30 铁甲将军 ~ lv80 卡塔），按模板图识别；lv70 起自动先上滑列表再匹配
- **自定义 Agent**：返回主界面、答题、关闭弹窗、选择战斗对象、物品增量记录等

## 目录结构

```text
M1A/
├── interface.json            # PI V2 入口：控制器 / 资源 / 分组 / 任务导入
├── tasks/                    # 任务定义（每个任务一个 JSON）
│   └── preset/daily.json     # 每日任务预设
├── resource/
│   ├── base/
│   │   ├── pipeline/         # 流水线节点
│   │   │   ├── daily/        # 日常任务节点
│   │   │   ├── weekly/       # 周常任务节点
│   │   │   ├── loop/         # 循环类任务节点
│   │   │   ├── start_game.json
│   │   │   ├── enter_game.json
│   │   │   ├── returen_mainface.json
│   │   │   └── close_game.json
│   │   ├── image/operator/   # 模板图（含 boss/ 下的 boss_N_part.png）
│   │   ├── model/ocr/        # OCR 模型（det.onnx / rec.onnx / keys.txt）
│   │   └── default_pipeline.json
│   ├── question_bank.json    # 答题题库
│   └── announcement/         # 公告缓存
├── agent/                    # Python Agent：自定义识别 / 动作
│   ├── main.py
│   ├── action/
│   ├── reco/
│   ├── utils.py
│   └── loggerControl.py
├── maafw/                    # MaaFramework 运行库（MaaFramework.dll 等）
├── mxu.exe                   # MXU 客户端
├── config/                   # MXU 实例配置（运行时生成）
├── debug/                    # 运行日志（运行时生成）
└── .venv/                    # Agent 运行环境
```

## 快速开始

1. **准备设备**：Android 设备或模拟器开启 ADB 调试，分辨率设为 1280×720。
2. **确认依赖**：
   - `maafw/` 中已放置 MaaFramework 运行库（当前开发环境为 5.14.3，协议版本 8）；
   - `.venv/` 已安装 Agent 依赖（`maa` Python 包、`numpy`、`Pillow`）。
3. **启动客户端**：运行根目录下的 `mxu.exe`，选择 `官服` 资源与 `ADB` 控制器，连接设备。
4. **选择任务**：可直接添加「每日任务」预设一键执行，也可按分组单独勾选任务。
5. **开始运行**：Agent 由 `interface.json` 自动拉起

## 任务

| 分组 | 任务名 | 名称 | 说明 |
| --- | --- | --- | --- |
| — | `start_game` | 启动游戏 | 启动游戏并进入主界面（默认勾选） |
| daily | `daily_claim_all` | 一键每日每周 | 领取每日/每周奖励与奖励找回 |
| daily | `claim_stamina` | 领取体力 | 领取爱心便当体力 |
| daily | `feast` | 盛宴 | 领取盛宴奖励 |
| daily | `seven_day_deals` | 七日特惠 | 完成七日特惠签到 |
| daily | `limited_reward` | 限时回馈 | 领取限时回馈奖励 |
| daily | `tap_checkin` | Tap签到 | TapTap 独家签到并复制兑换码 |
| daily | `answer_question` | 回答问题 | 幻想广场知识问答（含题库自动学习） |
| daily | `specialty` | 特产运输 | 完成特产运输 |
| daily | `manor` | 庄园 | 收取作物并一键种植 |
| daily | `alliance` | 联盟 | 捐献物资并领取礼物 |
| daily | `arena` | 竞技场 | 进入荣耀竞技场并选择战斗对象 |
| daily | `summon` | 召唤 | 英雄 / 圣物 / 魔法使召唤 |
| daily | `memory_space` | 记忆空间 | 进入记忆空间并完成关卡 |
| daily | `magic_garden` | 魔法园 | 进入魔法园并完成战斗 |
| daily | `solo_boss` | 个人Boss | 选择 Boss 后挑战（`solo_boss_select`） |
| daily | `world_boss` | 世界Boss | 选择 Boss 与队伍后挑战（`world_boss_select`、`select_team`） |
| daily | `wasteland` | 荒原 | 进入荒原并开启自动作战 |
| daily | `ruins` | 遗迹 | 进入遗迹 |
| weekly | `abyss` | 深渊 | 进入深渊并一键扫荡 |
| weekly | `treasure_cave` | 藏宝洞 | 开启宝箱、拾取奖励 |
| — | `close_game` | 关闭游戏 | 关闭游戏进程 |

## 已知问题（优化方向）

- `tasks/ruins.json` 与 `tasks/wasteland.json` 引用的 `ruins_点击冒险`、`进入荒原` 节点尚未在流水线中实现。
- `tasks/helpers.json` 使用了 `fields` / `steps` 结构，不符合 PI V2，暂未加入 `interface.json`。
- `interface.json` 的 `welcome` 指向 `asserts/welcome.md`，该文件目前不存在。
- weekly/ 需要手动开启
- 在boss挑战中无法进行其他任务

## 致谢

- [MaaFramework](https://github.com/MaaXYZ/MaaFramework) - 图像识别自动化框架
- [MXU](https://github.com/MistEO/MXU) - PI V2 通用客户端
- [MaaPipelineEditor](https://github.com/kqcoxn/MaaPipelineEditor) - 流水线可视化编辑器

## License

以仓库根目录 [LICENSE](LICENSE) 为准（GNU AGPL-3.0）。

本项目仅供学习与交流使用，请勿用于商业用途。游戏内容与素材版权归原作者所有。
