# Writer Assistant 进度检查（PROGRESS-CHECK）

> **用途**：读这一份就能快速掌握项目状态——当前完成度、已验证事项、5 分钟快速检查命令、已知坑、已定迭代方向。不需要翻 git log 或跑探查。
> **维护规则**：每个迭代收尾时必须更新本文件（状态快照 / 完成度 / 检查命令 / 方向勾选），保证"读到即最新"。详见文末。

## 一、状态快照

| 项 | 值 |
|---|---|
| 检查日期 | 2026-08-10 |
| 总体完成度 | **~88%**（生产级可用；评估基线见 `ASSESSMENT-2026-08.md`） |
| 路线图闭环 | **8/8 全部闭环**（2026-08-10 迭代） |
| 当前分支 | `main`，最近提交 `30381a1`（项目落地页，三.3 闭环） |
| 测试基线 | 全套 953 passed / 2 flaky（负载下）/ 31 skipped，~5.5 分钟 |
| 定位标尺 | 单用户、本地优先的个人 AI 长篇创作工作台 |

## 二、完成度明细（2026-08-10 更新）

| 领域 | 评估时 | 现在 | 变化依据 |
|---|---|---|---|
| 写作核心链路 | 90% | 92% | 事实仲裁闭环（正则↔delta 交叉校验 + TOML 结构校验）、multi-write 快照事务 + 回滚、审稿四级锚定加固 |
| 素材库/知识管理 | 82% | 86% | 素材孤岛打通（`data/research` 进索引根、参考 excerpt 2→4 段、采纳落库）、素材板五类聚合 |
| Skills 系统 | 90% | 90% | 三层解析 + 双格式 + 预算/诊断/规则，本轮未动 |
| UI 功能 | 90% | 95% | +3 视图（`/materials`、`/analytics`、`#projects` 落地页）+ 诊断包按钮 |
| UI 切换流畅度 | 35% | 60% | 主题 FOUC 修复 + 视图 0.18s 淡入 + dialog 动画 + reduced-motion（8de77ba）；**剩余**：视图切换未收敛单函数、`legacyLibraryViews` 未清 |
| 桌面端 | 85% | 85% | **缺口**：无托盘、无主进程日志（下一迭代 P0） |
| CLI | 80% | 80% | **缺口**：15 个顶层命令无 REPL（P2） |
| 测试/工程质量 | 失调 | 稳健 | 953 通过 + `node --check` 进测试集；**剩余**：truth_manager 专用测试仅 ~2 个（P1） |

总体 ~88% = 上述领域加权（写作链路权重最高）。剩余 12% 集中在：桌面端托盘/日志、前端结构卫生、事实链路测试覆盖、CLI REPL。

## 三、快速检查清单（照此跑，~6 分钟）

```bash
cd /e/codex内文件/writer-assistant   # Windows 实际路径 E:\codex内文件\writer-assistant

# 1. 快速回归（Studio 全部 65 测，~40s）
./.venv/Scripts/python.exe -m pytest tests/test_studio.py -q \
  --basetemp "C:/Users/MECHREVO/AppData/Local/Temp/wa-pytest-quick"

# 2. 全套测试（~5.5 分钟；2 个任务测试负载下偶发超时属已知 flaky，见下）
./.venv/Scripts/python.exe -m pytest tests/ -q \
  --basetemp "C:/Users/MECHREVO/AppData/Local/Temp/wa-pytest-full"

# 3. 前端 JS 语法校验（已进测试集，单独跑也行）
node --check tools/studio_assets/js/application.js

# 4. 启动服务（默认 :4569）
./.venv/Scripts/python.exe -m tools.cli studio

# 5. 浏览器验证（需服务已启动；动效脚本同理）
# playwright 不在本仓库时设 PLAYWRIGHT_ROOT 指向含 node_modules 的目录
PLAYWRIGHT_ROOT="E:/Claude Code code" node tools/studio_assets/dev/verify-projects.mjs   # 项目落地页：PASS/FAIL 逐项输出
node tools/studio_assets/dev/verify-ui-motion.mjs                                        # UI 动效 + 主题 FOUC
```

**通过标准**：① 全套 953 passed（2 个任务测试隔离重跑即过即可）② `verify-projects.mjs` 输出 `RESULT: PASS` ③ 服务正常响应 `curl http://127.0.0.1:4569/api/projects`。

## 四、已知坑（排查时先看这里）

1. **pytest basetemp PermissionError**：默认 `Temp\pytest-of-MECHREVO` 有残留进程锁，**必须 `--basetemp` 指定别处**（上述命令已带）。
2. **任务测试负载下 flaky**：`test_studio_tasks.py` 的 `_wait` 超时 30s 在批跑负载下偶发不够（ecec795 已从 15s 放宽）；隔离重跑即过，不是回归。
3. **LightRAG 挂起**：云 embedding 端点不可达时内部无限等待，`tools/project_search.py::_run_async` 硬超时 60s + `thread.join` 到点放弃，降级精确文本搜索；测试环境靠 `tests/conftest.py` 环境隔离避免打真实云端。
4. **CSP 控制台噪音**：vditor `icons/ant.js` 注入 inline style 被 `style-src 'self'` 拦下（`studio_http.py:518`）；实测渲染盒 0×0 零影响，纯噪音，可留待结构卫生时处理。
5. **服务端口**：Studio 默认 `:4569`；`verify-ui-motion.mjs` 默认 `:8799`（桌面后端），跑浏览器脚本前确认服务端口。

## 五、已定方向（下一迭代，按优先级）

### P0 桌面端收尾（85% → ~95%）
- [ ] Electron 主进程加**托盘**（退出/恢复窗口、最小化到托盘）
- [ ] **主进程日志**落盘（对齐 CLI/Studio 的 JSONL 统一日志）
- 验收：托盘图标可恢复窗口/彻底退出；主进程异常有日志可查

### P0 前端结构卫生（动效铺路）
- [ ] 视图切换收敛为**单一函数**（现 `setView`/`routeFromLocation` 双入口）
- [ ] 清理 `legacyLibraryViews` 映射（2 处）与 `openDocument`/`setView` 重复翻转——保留旧 hash 链接兼容
- [ ] 顺手清 CSP 噪音（vditor ant.js sprite 隐藏样式挪进 styles.css）
- 验收：`grep -c legacyLibraryViews` = 0；旧 hash 链接（如 `#library`）仍能打开对应视图

### P1 事实链路测试补强（核心价值保障）
- [ ] `truth_manager` 专用测试：当前 ~2 个 → 目标 10+（结构校验、delta 交叉校验、回滚路径）
- 验收：truth 链路测试覆盖主要失败路径；全套无新增 flaky

### P2 可选
- [ ] CLI REPL（15 个顶层命令已齐，REPL 提升脚本化体验）
- [ ] 多项目 v2：灵感素材板 v2（落地页基础已铺，素材链已打通）

## 六、维护规则

- 每个迭代收尾：更新**状态快照**（日期/完成度/最新提交/测试基线）→ 勾选或调整**方向清单**（done 项移到完成度表的"变化依据"）→ 新增坑写入**已知坑**。
- 新增验证脚本同步登记到**快速检查清单**；服务端口/启动方式变了必须同步更新。
- 本文件与 `ASSESSMENT-2026-08.md`（基线+路线图）互补：评估文档讲"为什么"，本文件讲"现在是什么、怎么查、下一步去哪"。
