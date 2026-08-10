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
| UI 切换流畅度 | 35% | 60% | 主题 FOUC 修复 + 视图 0.18s 淡入 + dialog 动画 + reduced-motion（8de77ba）；**剩余**：视图切换未收敛单函数、`legacyLibraryViews` 未清、**审计 A1：首访 workspace 阻塞 ~54s 期间切换被静默拦截（视图本身全过，问题在 workspace 加载）** |
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

## 四·五、功能审计（2026-08-10 全量自检）

> 范围：21 个 GET API 全扫、17 个视图浏览器扫描、vditor 编辑器探测、26 个 CLI 命令冒烟、boot 时序诊断。逐功能"能过一遍就过一遍"，发现见下。

### 审计结论速览

| 功能面 | 结论 |
|---|---|
| GET API（21 个） | **全部正常**；`/api/workspace` 存在 P0 级首访慢（见 A1） |
| 视图（17 个） | **功能全部正常**；扫描"前 9 失败"为 A1 的确定性投影，非视图缺陷 |
| vditor 编辑器 | 正常（约 20-24ms 就绪）；CSP inline-style 噪音仅控制台可见 |
| CLI（26 命令） | 框架正常，status/desk/doctor 实测通过 |
| 搜索/语义检索 | **A1 根因**：embedding 每次请求云端 404 → 每次 ~54s 降级 |
| 项目注册表 | **A2**：`list()` 静默清理 ephemeral 项目并覆盖 registry 文件 |

### A1（P0）首次/每次 workspace 请求阻塞 ~54s，期间所有视图切换静默失败

- **现象**：浏览器打开 Studio 后，前 ~54s 内点击任何导航视图都无效（容器不显示、导航高亮不切换、无报错）。~54s 后一切恢复正常。
- **根因链**（服务端日志 + 前端时序双证实）：
  1. 每次页面加载 → `GET /api/workspace` → 触发 LightRAG 索引 flush（demo 项目 13 chunks × 2 批）；
  2. embedding 运行时解析成**云端 openai**（`/api/workspace` handler 未包 `_model_context` → profile ContextVar 未激活 → `active={}` → provider fallback `"openai"` → base_url 用 LLM 的 `https://api.xiaomimimo.com/v1`）；
  3. xiaomimimo 无 `/embeddings` 端点 → 404 `NotFoundError` → 每批 30s 重试（`Func: 30s, Worker: 60s`）× 2 批 ≈ 54s；
  4. 期间 `state.workspace = NULL` → `setView()` 的 `if (!state.workspace) return`（`application.js:1049`）**静默拦截**全部视图切换；workspace 就绪后剩余视图秒切。
- **复现证据**：视图扫描两次独立运行（workspace 冷/热）结果逐位一致——前 9 视图 × 6s 轮询 = 54s 恰好覆盖阻塞窗口，第 10 个起全 PASS；切换期间服务端零视图数据请求（`loadProjects`/`loadAnalytics` 等从未发出）。
- **配置疑云**：`model-profiles.json` 声明 `embedding_provider: "local"`（FastEmbed/bge-small-zh），`resolve("search")` 实测也返回 local——但运行时走了云端。差异来自 workspace 请求路径未进入 `_model_context`（`studio_http.py:155` 直调 `app.workspace()`，缺 `with self._model_context(profile)`），与 21 处 `_model_context` 包裹的其他 handler 不一致。
- **影响**：用户感知 = "打开 Studio 卡顿约 1 分钟，期间点啥都没反应"。首访+每页面刷新都会重演（日志 21:27/21:28/21:39 三次完整重试链）。
- **修法建议**（任选，按性价比排序）：
  1. **workspace() 包 `_model_context`**（对齐其他 handler，一行级改动）→ embedding 走配置的 local FastEmbed，索引构建本地化；
  2. embedding 失败**快速降级**（不逐批 30s 重试，失败即回退精确文本搜索）——即便云端配置，也只慢一次而非每次；
  3. `setView` guard 失败时**给用户可见提示**（toast"工作区载入中"），而非静默丢弃——这是防呆底线，无论如何该做。

### A2（P1）项目注册表静默清空 ephemeral 项目

- **现象**：`ProjectRegistry.list()` 在默认 `allow_ephemeral=False` 下把 temp/临时目录项目过滤掉，并把 registry 文件**覆盖回写**为 `projects: []`（`tools/project_registry.py` 的 `_save(available[:REGISTRY_LIMIT])`）。
- **影响**：浏览器验证期间 registry.json 被静默清空（已手工恢复 alpha/beta 记录）；用户在非标准目录（Temp、`/tmp` 类路径）打开过项目时，注册表会被悄悄抹掉。
- **修法建议**：清理逻辑只作用于内存视图，`_save` 时保留原始记录（或 `allow_ephemeral` 参数语义文档化），加单测断言"过滤不清空文件"。

### A3（P2）前端路由结构卫生（与既有 P0 方向一致）

- `routeFromLocation` 是唯一 popstate 监听（`application.js:6834`），视图切换另有一处 `setView` 直调——双入口已列方向，确认无第四入口。
- `setView` 的 `window.confirm` 未保存离开拦截与 toast 提示并存，行为已验证正常。

### 审计方法记录（可复跑）

- 浏览器脚本（playwright）：`E:\Claude Code code\shots\` 与审计临时目录中的 `audit-views2.mjs`（视图扫描）、`audit-boot2.mjs`（boot 时序）、`audit-hash-events.mjs`（路由事件打点）。
- 服务端日志：启动命令输出中的 `[search-b9abddf0eaca1a9e]` 重试链 + `GET /api/workspace` 500/200 时间戳。
- 未发现：无 500 业务错误、无未捕获 pageerror、vditor after 回调正常触发、CLI 无崩溃。

## 五、已定方向（2026-08-10 审计后重排，按执行顺序）

> **执行顺序已确认**：先修审计发现（A1→A2，代价小收益大、用户每次用得上）→ 再回到旧 P0（桌面端→结构卫生）→ P1/P2 排队。

### P0-1 workspace 阻塞修复（审计 A1，本轮第一个做）
- [ ] `/api/workspace` handler 包 `_model_context`（对齐其他 21 处），embedding 走配置的 local FastEmbed
- [ ] embedding 失败快速降级（不逐批 30s 重试），首访失败不再每次重演
- [ ] `setView` guard 失败给用户可见提示（toast），不静默丢弃
- 验收：`curl /api/workspace` 冷启动 < 5s；浏览器打开 Studio 后视图立即可切换；复跑 `audit-views2.mjs` 17/17 全 PASS

### P0-2 项目注册表保护（审计 A2，小改动防数据丢失）
- [ ] `ProjectRegistry.list()` 过滤逻辑不覆盖回写 registry 文件（`_save` 只写显式变更）
- [ ] 加单测：`list()` 过滤 ephemeral 后文件仍保留原始记录
- 验收：过滤后 registry.json 内容不变；单测覆盖该路径

### P0-3 桌面端收尾（旧 P0，85% → ~95%）
- [ ] Electron 主进程加**托盘**（退出/恢复窗口、最小化到托盘）
- [ ] **主进程日志**落盘（对齐 CLI/Studio 的 JSONL 统一日志）
- 验收：托盘图标可恢复窗口/彻底退出；主进程异常有日志可查

### P0-4 前端结构卫生（动效铺路，顺带闭环审计 A3）
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
