# Writer Assistant 全面评估与迭代路线图（2026-08-10）

> 基于 2026-08-10 三轮代码深扫（写作链路 / 素材库 / UI+Skills）的整合评估。
> 定位标尺：**单用户、本地优先的个人 AI 长篇创作工作台**。所有改动都应问一句：
> "这对'写长篇不丢设定、持续产出、省心'有贡献吗？"

## 总体结论

**总体完成度 ~85%，生产级可用。** 功能广度惊人（42 个 Agent 工具、14 个视图、双桌面方案、研究桥），但**功能过剩而核心脆弱**——真正定义产品价值的事实一致性链路只投入了 65%。

| 领域 | 完成度 | 一句话结论 |
|------|--------|-----------|
| 写作核心链路 | ~90% | 端到端打通、事务性提交、断点恢复、零占位符 |
| 素材库/知识管理 | ~82% | 世界查询 95% 最成熟；事实一致性 65% 最弱 |
| Skills 系统 | ~90% | 三层解析 + 双格式兼容 + 预算/诊断/规则 |
| UI 功能 | 90% | 14 视图 + ~50 条 API 全部闭环 |
| UI 切换流畅度 | 35% | 视图/弹窗/主题切换全部瞬间显隐 |
| 桌面端 | 85% | 单实例/窗口状态/自动更新/NSIS 齐全；无托盘、无主进程日志 |
| CLI | 80% | 15 个顶层命令，无 REPL |

## 一、改什么（架构与债务）

1. **收敛双桌面方案**：Electron（主，已有全链路）/ pywebview（desktop_app.py）/ launcher 三套并存。删 pywebview 路径或降级兜底说明。
2. **清理遗留代码**（2026-08-10 调查后修正：项目比初评干净）：
   - ~~`dante.py` 遗留 Agent~~ —— **误判**：`dante.py` 是 `writer dante` 主入口（SKILL.md 两个主入口之一），活跃使用，保留
   - WorkflowScheduler 后三段（user_confirm/styling/compression）——历史 Skill 时代阶段，当前管线只驱动到 review；阶段枚举是数据契约（历史 workflow 记录按 STAGE_NAMES 重建），**不删除**，已在代码注释标注遗留语义（workflow_scheduler.py STAGE_NAMES）
   - `cli.py` `agent` 命令已优雅退役（报错指向 writer dante），兼容旧脚本，保留
   - `legacyLibraryViews` 映射、`openDocument` 与 `setView` 重复的视图翻转——保留（兼容旧 hash 链接），重构时随前端结构卫生一并处理
   - `radar.py` 番茄榜单抓取（脆弱外围）；`research_service.py` 桥要么接素材链要么标记 deprecated
3. **写作入口全部收敛到 `NovelApplicationService`**：连续写作/CLI/goethe 各自有写入口，杜绝"第 N 条路径忘了快照回滚"。
4. **multi-write 接入 ChapterRunV2 事务**：当前草稿先落盘再审稿、无快照回滚——最危险的可靠性缺口。

## 二、优化什么（工程与体验）

1. **测试投入与风险对齐**：75 个测试文件严重失衡——world_query 46 个 vs truth_manager **2 个**（65% 完成度 + 核心价值）。优先补事实链路测试。
2. **事实一致性升级到全局仲裁**：
   - 真相文件 TOML front matter 结构校验（格式漂移即报错，而非静默失效）
   - 写章后事实抽取（正则兜底）升级为 LLM delta 校验回路，冲突直接进审稿 issue
3. **素材孤岛打通**：`data/research` 进索引根目录（一行配置）；参考库资产经"采纳"半自动写入索引目录；参考 excerpt 每章 2 段放宽（预算保护已有）。
4. **审稿锚定加固**：复用 `_locate_chunk` 能力按行号辅助定位；anchor 失败降级为"章节范围+关键词"而非直接 `ISSUE_NOT_ANCHORED`。
5. **前端结构卫生**：`node --check` pre-commit hook；视图切换收敛为单一函数（为动画铺路）。

## 三、增什么（缺失能力）

1. **主题 FOUC 修复 + 页面过渡**（快赢，30 分钟）：深色刷新闪浅色（CSP 禁内联+延迟应用）；加 150ms 视图淡入 + dialog `[open]` 动画（reduced-motion 已就绪）。
2. **统一日志 + 一键诊断导出**：所有通道落统一 JSONL + "导出诊断包"按钮（日志+配置脱敏+版本），提 issue 拖包即诊。
3. **多项目体验**：项目列表落地页（卡片+最近项目），v2 灵感素材板的基础。
4. **用户手册**：SKILL.md 给 AI、README 给开发者，缺"给小说作者"的 3 页手册（goethe→dante 流程、风格库、连续写作干预、模型配置）。投入产出比最高的"功能"。

## 四、迭代什么（功能路线）

**短期（下一迭代）**：UI 动效+主题 FOUC → 遗留清理 → 素材孤岛打通
**中期（核心价值）**：事实仲裁闭环 → multi-write 事务对齐+审稿锚定 → 统一诊断包
**长期（v2）**：灵感素材板（前提：素材链已打通）→ 写作仪表盘（narrative_forecast/visualization 素材已有一半）

## 执行状态（跟踪）

- [x] 2026-08-10：本评估文档
- [x] 短期：UI 动效 + 主题 FOUC（盘点确认：8de77ba 已落地——app.js 模块顶层 pre-paint 修 FOUC、.workspace-view 0.18s 淡入、dialog[open] 0.16s 动画、reduced-motion 兜底，含 dev/verify-ui-motion.mjs）
- [x] 短期：遗留代码清理（盘点确认：dante/WorkflowScheduler 后三段/agent 命令均为保留项；legacyLibraryViews 随前端结构卫生处理；desktop_app 已有 pywebview→浏览器降级兜底；research_service 产出已由素材孤岛打通闭环——本轮补雷达脆弱性标注 + 研究桥素材链标注）
- [x] 短期：素材孤岛打通（盘点确认：`data/research` 已进索引根且 scope_for_path 映射到 sources（此前迭代顺带完成）；采纳产出 recipe/fingerprint/候选文档已全部落 data/style|sources 索引内；本轮放宽 sources 每章 2→4 段，保留 900 字符 excerpt 预算）
- [x] 中期：事实仲裁闭环（正则↔delta 交叉校验 + 结构校验 + multi-write memory）
- [x] 中期：multi-write 事务对齐（快照 + 回滚 + 3 个回归测试）
- [x] 中期：审稿锚定加固（四级锚定：显式 anchor → 精确引文 → 空白归一模糊匹配 + 前后文消歧 → 词项行定位；全失败降级整章范围 + 定位提示，不再 ISSUE_NOT_ANCHORED）
- [x] 中期：统一诊断包（JSONL 日志 .openwrite/logs/ + `writer diagnose --export` + Studio 诊断包按钮；脱敏配置/环境/版本/manifest + 复用运行时诊断报告）
- [x] 长期 v2：灵感素材板（新视图 `/materials` + `/api/materials` 聚合五类素材：研究/参考/世界/伏笔/风格；最近更新优先 + 类型过滤 chips + 卡片摘要；点击卡片 openDocument 复用编辑链路；素材链前置打通后实现）
- [x] 长期 v2：写作仪表盘（新视图 `/analytics` + `/api/dashboard` 聚合：① 章节字数柱状图（list_chapters + count_writing_units，末章高亮）② 审稿分数折线（ReviewStore，及格线 60 + 待刷新红点 + 通过绿点）③ 叙事预测列表（NarrativeForecastService 聚合，分支 chips + 锚点章节 + 状态映射）；纯内联 SVG 图表无外部库；hash 路由 + 刷新按钮 + 移动端单列）
- [x] 三.4 用户手册（`docs/AUTHOR-MANUAL.md`：作者向 3 页零代码手册——工作台运转模型、开新书流程、goethe→dante 日常循环、连续写作干预、风格库、素材保鲜、模型配置、版本恢复；README 挂载入口）
- [x] 三.3 多项目体验（项目落地页：`/api/projects` 注册表接口秒回（只读、不触达项目内部）+ `#projects` 卡片视图（最近打开置顶 + 当前项目标记 + "打开作品/已在当前"双态按钮 + 删除入口）；Playwright 浏览器验证（卡片/徽章/切换回 dashboard 全绿）+ `test_studio_serves_project_landing_and_switches` 回归测试（打开 B 后 current 切换 + 最近置顶））
