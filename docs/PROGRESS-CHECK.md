# Writer Assistant 进度检查（PROGRESS-CHECK）

> **用途**：读这一份就能快速掌握项目状态——当前完成度、已验证事项、5 分钟快速检查命令、已知坑、已定迭代方向。不需要翻 git log 或跑探查。
> **维护规则**：每个迭代收尾时必须更新本文件（状态快照 / 完成度 / 检查命令 / 方向勾选），保证"读到即最新"。详见文末。

## 一、状态快照

| 项 | 值 |
|---|---|
| 检查日期 | 2026-08-11 |
| 总体完成度 | **~96%**（P0-2/P0-3/P0-4/P1/P2 全部收尾） |
| 路线图闭环 | **10/10 全部闭环**（含多项目灵感素材板 v2） |
| 当前分支 | `main`，最近提交 `07f3b71`（灵感素材板 v2 跨项目浏览 + 任务 store 竞态修复） |
| 测试基线 | 全套 981 passed / 0 flaky / 31 skipped，~4.7 分钟 |
| 定位标尺 | 单用户、本地优先的个人 AI 长篇创作工作台 |

## 二、完成度明细（2026-08-10 更新）

| 领域 | 评估时 | 现在 | 变化依据 |
|---|---|---|---|
| 写作核心链路 | 90% | 92% | 事实仲裁闭环（正则↔delta 交叉校验 + TOML 结构校验）、multi-write 快照事务 + 回滚、审稿四级锚定加固 |
| 素材库/知识管理 | 82% | 92% | 素材孤岛打通（`data/research` 进索引根、参考 excerpt 2→4 段、采纳落库）、素材板五类聚合、**v2 跨项目浏览**（全部/单项目 chips、跨项目卡片点击切项目打开、流水线噪音过滤、素材目录进文档可访问范围） |
| Skills 系统 | 90% | 90% | 三层解析 + 双格式 + 预算/诊断/规则，本轮未动 |
| UI 功能 | 90% | 95% | +3 视图（`/materials`、`/analytics`、`#projects` 落地页）+ 诊断包按钮 |
| UI 切换流畅度 | 35% | 95% | 主题 FOUC 修复 + 视图 0.18s 淡入 + dialog 动画 + reduced-motion（8de77ba）；**A1 修复**：workspace 0.06s（原 120.8s）+ 探测闸门快速降级 + setView toast + style-vault 路由白名单补齐 → 视图扫描 17/17 PASS；**剩余**：视图切换未收敛单函数、`legacyLibraryViews` 未清（P0-4） |
| 桌面端 | 85% | 95% | **P0-3 托盘**：close-to-tray、右键菜单显示/退出、单击恢复、单实例锁恢复窗口；**主进程日志**：`desktop.jsonl` 对齐 Python JSONL（1MB×4 轮转） |
| CLI | 80% | 95% | **P2 REPL**：`writer repl` 交互会话（msvcrt 行编辑 + 上下键历史 + 管道回退 input() + 单命令错误隔离），`test_cli_repl` 14 测 |
| 测试/工程质量 | 稳健 | 稳健 | 965 passed + `node --check`；truth_manager 从 17 → 23 专用测试（结构校验/delta 交叉校验/回滚路径/别名兼容/首次运行） |

总体 ~96% = 上述领域加权。剩余 4% 集中在：灵感素材板 v2 的后续打磨（素材标签体系/frontmatter 解析等长期设想，路线图内已无强制方向）。

## 三、快速检查清单（照此跑，~6 分钟）

```bash
cd /e/codex内文件/writer-assistant   # Windows 实际路径 E:\codex内文件\writer-assistant

# 1. 快速回归（Studio 全部 65 测，~40s）
./.venv/Scripts/python.exe -m pytest tests/test_studio.py -q \
  --basetemp "C:/Users/MECHREVO/AppData/Local/Temp/wa-pytest-quick"

# 2. 全套测试（~5 分钟；任务 store 原子替换已加重试，无已知 flaky）
./.venv/Scripts/python.exe -m pytest tests/ -q \
  --basetemp "C:/Users/MECHREVO/AppData/Local/Temp/wa-pytest-full"

# 3. 前端 JS 语法校验（已进测试集，单独跑也行）
node --check tools/studio_assets/js/application.js

# 4. 启动服务（默认 :4569）
./.venv/Scripts/python.exe -m tools.cli studio

# 4b. REPL 冒烟（管道喂命令，验证会话存活）
printf '%s\n' '--version' 'help' 'q' | ./.venv/Scripts/python.exe -m tools.cli repl

# 5. 浏览器验证（需服务已启动；动效脚本同理）
# playwright 不在本仓库时设 PLAYWRIGHT_ROOT 指向含 node_modules 的目录
PLAYWRIGHT_ROOT="E:/Claude Code code" node tools/studio_assets/dev/verify-projects.mjs   # 项目落地页：PASS/FAIL 逐项输出
PLAYWRIGHT_ROOT="E:/Claude Code code" node tools/studio_assets/dev/verify-views.mjs      # 视图冒烟：17 视图 + 旧 hash + 编辑器
PLAYWRIGHT_ROOT="E:/Claude Code code" node tools/studio_assets/dev/verify-materials.mjs  # 素材板 v2：项目 chips/跨项目跳转/类型过滤（需注册表 ≥1 项目）
PLAYWRIGHT_ROOT="E:/Claude Code code" node tools/studio_assets/dev/verify-desktop.mjs     # 桌面 E2E：窗口/后端/托盘/退出（需 desktop/node_modules + 4567 空闲）
node tools/studio_assets/dev/verify-ui-motion.mjs                                        # UI 动效 + 主题 FOUC
```

**通过标准**：① 全套 953 passed（2 个任务测试隔离重跑即过即可）② `verify-projects.mjs` 输出 `RESULT: PASS` ③ 服务正常响应 `curl http://127.0.0.1:4569/api/projects`。

## 四、已知坑（排查时先看这里）

1. **pytest basetemp PermissionError**：默认 `Temp\pytest-of-MECHREVO` 有残留进程锁，**必须 `--basetemp` 指定别处**（上述命令已带）。
2. **任务 store 文件竞态（已修复根因，读写两侧）**：Windows 上高频轮询读 + 原子替换的两个竞态——① 写侧 `_atomic_text_write` 的 `os.replace` 撞读句柄抛 `PermissionError（WinError 5）`（任务转 failed 后测试盲等 30s）；② 读侧 `load` 的 `is_file` 检查后、open 前文件被 replace 换名 → `FileNotFoundError` 被吞成 "Task not found"。修复：replace 失败重试 4 次（20/40/60/80ms 退避）+ `load` 读取失败重试 3 次 + 两个测试 `_wait` 遇终态失败立即报错附 store error（并兜底 Task not found 继续轮询）。3 文件组合（test_studio+test_studio_tasks+test_task_runner）连跑 3 遍 77 passed。
2b. **注册表边界测试依赖 basetemp 位置**：`is_ephemeral_project_path` 只认系统 temp（`tempfile.gettempdir()`）——若 `--basetemp` 落在非 temp 盘符（如 `E:/`），`test_project_boundaries.py` 的两个 ephemeral 测试会红（项目不被过滤）。已加固：测试显式把项目建在 OS temp 下（`wa-ephemeral-{uuid}`），任何 basetemp 都过。
3. **LightRAG 挂起**：云 embedding 端点不可达时内部无限等待，`tools/project_search.py::_run_async` 硬超时 60s + `thread.join` 到点放弃，降级精确文本搜索；测试环境靠 `tests/conftest.py` 环境隔离避免打真实云端。**A1 修复后**：进 LightRAG 前有探测闸门（失败秒级降级 + 1800s 缓存窗口），不再每次白等 60s。
4. **本地 FastEmbed 模型需预下载**：`embedding_provider: "local"` 默认 `local_files_only=True`——模型未缓存时语义检索直接降级精确文本搜索（快速失败，不阻塞）。要启用语义检索：预先把 `BAAI/bge-small-zh-v1.5` 下到缓存，或设 `OPENWRITE_FASTEMBED_ALLOW_DOWNLOAD=true`（网络可用时自动下载，不可达时 connect 重试链会拖慢首次请求）。
5. **CSP 控制台噪音**：vditor `icons/ant.js` 注入 inline style 被 `style-src 'self'` 拦下（`studio_http.py:518`）；实测渲染盒 0×0 零影响，纯噪音，可留待结构卫生时处理。
6. **服务端口**：CLI `studio` 默认 `:4567`（PROGRESS-CHECK 原记 4569 是审计时手动传参）；`verify-ui-motion.mjs` 默认 `:8799`（桌面后端），跑浏览器脚本前确认服务端口。
7. **REPL 输入实现**：Windows 下 `msvcrt.getwch()` 只读控制台缓冲区，**stdin 非 TTY（管道/重定向）时必须回退 `input()`**（已实现）；测试/脚本化用管道喂命令即可，交互式终端才有行编辑与历史。

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

### A1（P0）首次/每次 workspace 请求阻塞 ~54s，期间所有视图切换静默失败 —— 已修复 ✅

- **现象**：浏览器打开 Studio 后，前 ~54s 内点击任何导航视图都无效（容器不显示、导航高亮不切换、无报错）。~54s 后一切恢复正常。
- **根因链**（服务端日志 + 前端时序 + 分步计时三证实）：
  1. 每次页面加载 → `GET /api/workspace` → 链上 `operation_status → runtime_diagnostics → _context_findings → build_generation_context → ProjectSearchIndex.search()`（`context_builder.py:307`）触发 LightRAG flush（demo 项目 13 chunks × 2 批）；
  2. `/api/workspace` handler（`studio_http.py:155`）缺 `_model_context` 包裹（与 21 处 handler 不一致）→ search profile ContextVar 未激活 → embedding fallback `"openai"` → base_url 用 LLM 的 `https://api.xiaomimimo.com/v1`；
  3. xiaomimimo 无 `/embeddings` → 404 → 每批 30s 重试 × 2 批 ≈ 60s，且 `runtime_diagnostics` 的 `_get_semantic_references` 对 chapters+sources 两 scope 各搜一次 → **120s**；
  4. 期间 `state.workspace = NULL` → `setView()` 的 `if (!state.workspace) return`（`application.js:1049`）**静默拦截**全部视图切换。
  5. 次要慢点：`model_profiles → surface → model_preset_catalog → import litellm` 拉远端 model cost map，离线 connect 超时 ~9.5s × workspace 链 3 次。
- **修复**（三管齐下 + 一处根治）：
  1. `workspace()` 包 `_model_context(None)`（`studio_application.py:554`）——embedding 走配置的 local FastEmbed；
  2. **探测闸门** `_ensure_embedding_ready`（`project_search.py`）：进 LightRAG 前先 `EmbeddingRuntime.probe()`（12s 封顶），失败立即抛错走精确文本降级，失败状态 1800s 窗口缓存（窗口内秒回，窗口后自动重试）；同时 `embedding_runtime.py` 默认 `local_files_only=True`（模型未缓存即秒级失败，不再每次触发 HF 下载重试链；设 `OPENWRITE_FASTEMBED_ALLOW_DOWNLOAD=true` 恢复自动下载）；
  3. litellm 禁远端拉取：`LITELLM_LOCAL_MODEL_COST_MAP=true`（`model_catalog.py:307` 与 `llm/client.py:299` import 前 setdefault）；
  4. `setView` guard 失败 toast 提示（限流 4s）。
- **验收**：服务器端 `curl /api/workspace` **0.06s**（修复前 120.8s）；视图扫描 **17/17 PASS**；相关测试 92 passed。
- **残余**：首次直调 10.1s 为 litellm import 一次性成本（进程生命周期只付一次）；语义检索在 embedding 不可用期间降级精确文本搜索（设计内行为）。

### A2（P1）项目注册表静默清空 ephemeral 项目

- **现象**：`ProjectRegistry.list()` 在默认 `allow_ephemeral=False` 下把 temp/临时目录项目过滤掉，并把 registry 文件**覆盖回写**为 `projects: []`（`tools/project_registry.py` 的 `_save(available[:REGISTRY_LIMIT])`）。
- **影响**：浏览器验证期间 registry.json 被静默清空（已手工恢复 alpha/beta 记录）；用户在非标准目录（Temp、`/tmp` 类路径）打开过项目时，注册表会被悄悄抹掉。
- **修法建议**：清理逻辑只作用于内存视图，`_save` 时保留原始记录（或 `allow_ephemeral` 参数语义文档化），加单测断言"过滤不清空文件"。

### A3（P2）前端路由结构卫生（与既有 P0 方向一致）

- `routeFromLocation` 是唯一 popstate 监听（`application.js:6834`），视图切换另有一处 `setView` 直调——双入口已列方向，确认无第四入口。
- `setView` 的 `window.confirm` 未保存离开拦截与 toast 提示并存，行为已验证正常。
- **已顺手修复**：`routeFromLocation` 白名单缺 `style-vault` → `#style-vault` 深链/刷新落回 dashboard（`application.js` 白名单已补；审计 v3 发现，真实缺陷非脚本假阴性）。

### 审计方法记录（可复跑）

- 浏览器脚本（playwright）：`E:\Claude Code code\shots\` 与审计临时目录中的 `audit-views2.mjs`（视图扫描）、`audit-boot2.mjs`（boot 时序）、`audit-hash-events.mjs`（路由事件打点）。
- 服务端日志：启动命令输出中的 `[search-b9abddf0eaca1a9e]` 重试链 + `GET /api/workspace` 500/200 时间戳。
- 未发现：无 500 业务错误、无未捕获 pageerror、vditor after 回调正常触发、CLI 无崩溃。

## 五、已定方向（2026-08-10 审计后重排，按执行顺序）

> **执行顺序已确认**：先修审计发现（A1→A2，代价小收益大、用户每次用得上）→ 再回到旧 P0（桌面端→结构卫生）→ P1/P2 排队。

### P0-1 workspace 阻塞修复（审计 A1，本轮已完成 ✅）
- [x] `/api/workspace` handler 包 `_model_context`（`studio_application.py` workspace→`_workspace_impl` 包裹），embedding 走配置的 local FastEmbed
- [x] embedding 失败快速降级（探测闸门 `_ensure_embedding_ready`：进 LightRAG 前先 probe，失败立即抛错降级 + 1800s 失败缓存窗口；`local_files_only` 默认纯本地加载，模型未缓存秒级失败；litellm `LITELLM_LOCAL_MODEL_COST_MAP` 禁远端拉取）
- [x] `setView` guard 失败给用户可见提示（toast"工作区载入中"限流 4s），不静默丢弃
- 顺带修复：`routeFromLocation` 白名单缺 `style-vault` → `#style-vault` 深链/刷新落回 dashboard（审计 v3 发现，已修）
- **验收结果**：`curl /api/workspace` 服务器端 **0.06s/0.06s**（修复前 120.8s）；直调脚本冷启动 10.1s（含一次性 litellm import）/ 热 0.6s；视图扫描 **17/17 PASS**（`audit-views5.mjs`，真实容器名）；`test_studio`+`test_project_search`+`test_model_profiles` 92 passed
- **根因细化**（分步计时实证）：workspace 链慢点不在文档加载，而在 `operation_status → runtime_diagnostics → _context_findings → build_generation_context → ProjectSearchIndex.search()`（每次 60s 硬超时 × 2 scope = 120s）＋ `model_profiles → surface → model_preset_catalog → import litellm`（远端 model cost map connect 超时 ~9.5s，×workspace 链 3 次调用）

### P0-2 项目注册表保护（审计 A2，小改动防数据丢失）—— 已完成 ✅
- [x] `ProjectRegistry.list()` 过滤逻辑不覆盖回写 registry 文件（移除 `list()` 内 `_save` 调用）
- [x] 加单测：`list()` 过滤 ephemeral 后文件仍保留原始记录（`test_project_registry_prunes_framework_and_ephemeral_history` 断言改为验证文件未被清空）
- 验收：22/22 test_project_boundaries 通过；65/65 test_studio 通过

### P0-3 桌面端收尾（旧 P0，85% → ~95%）—— 已完成 ✅
- [x] Electron 主进程加**托盘**（close-to-tray、右键菜单显示/退出、单击恢复窗口）
- [x] **主进程日志**落盘（`desktop.jsonl` 写入 `.openwrite/logs/`，1MB×4 轮转，对齐 Python `diagnostic_logging.py` 格式；覆盖启动/后端/窗口/托盘/自动更新/全局异常）
- 验收：`node --check` 语法通过；托盘 close-to-tray + 右键退出双路径；日志覆盖 7 类事件

### P0-4 前端结构卫生（动效铺路，顺带闭环审计 A3）—— 已完成 ✅
- [x] 视图切换收敛为**单一函数**：新增 `VIEW_PANES` 视图注册表（view 名 → 容器 selector），`setView`/`activateStructuredAssetEditor` 统一走 `showViewPanes()`；`routeFromLocation` 白名单改为 `ROUTABLE_VIEWS` 集合生成
- [x] 清理 `legacyLibraryViews` 映射（内联进 `normalizeView`）与 `openDocument`/`setView` 重复翻转——旧 hash 链接兼容保留
- [x] CSP 噪音：`style-src` 加 `'unsafe-inline'`（vditor ant.js sprite）
- 验收：**17/17 视图扫描 PASS**（`audit-views5.mjs`）；旧 hash `#story/#world/#assets` 全部映射正确；`legacyLibraryViews` grep = 0；无 `projectsView is not defined` 类 pageerror

### P1 事实链路测试补强（核心价值保障）—— 已完成 ✅
- [x] `truth_manager` 专用测试：从 17 → 23 个，覆盖结构校验/delta 交叉校验/回滚路径/别名兼容/默认元数据/摘要提取/空快照列表/损坏文件跳过/POV 过滤章摘要路径/首次运行无目录
- 验收：33/33 truth_manager + fact_arbitration 通过；全套 965/965 passed

### P2 CLI REPL（15 个顶层命令已齐，REPL 提升交互体验）—— 已完成 ✅
- [x] `writer repl [--prompt]`：逐条执行任意 CLI 命令，`exit/quit/q` 退出，`help/?` 列出命令
- [x] Windows 原生行编辑（msvcrt）：左右键移动光标、Home/End、Backspace、上下键历史浏览；stdin 非 TTY（管道/重定向）自动回退 `input()`，脚本化可用
- [x] 单命令失败不退出会话（argparse SystemExit / 命令异常均捕获继续）；项目内提示当前项目名
- [x] `_build_parser()` 提取：REPL 与 `main()` 共用同一 parser，无重复定义
- 验收：`test_cli_repl` 14 测 + 既有 CLI 子集 50 passed；管道冒烟 `--version`→`bogus-xyz`→`help`→`q` 全部符合预期

### P2 多项目灵感素材板 v2（落地页基础已铺，素材链已打通）—— 已完成 ✅
- [x] **跨项目只读浏览**：`/api/materials?project=<path>`（URL 编码）聚合任意合法项目五类素材，不切换激活状态；未初始化（无当前项目）也能冷启动浏览；素材条目带 `project_path`/`project_title` 归属字段
- [x] **项目 chips**：素材板顶部「全部项目 + 各项目（当前标（当前））」，全部模式并行聚合注册表全部项目（单项目失败不拖垮整体），合并后按最近更新排序
- [x] **跨项目卡片跳转**：点击他项目素材 → 切项目 + 打开文档（`switchProject` 从 openProject 提取复用，注册表同步刷新）
- [x] **流水线噪音过滤**：`extraction/`、`batch_results/`、`logs/` 目录与 `progress.json`、`runtime_state.json` 不进素材板
- [x] **顺带修复（素材板 1.0 潜在缺陷）**：`_resolve_document` 可访问范围只有 src/manuscript，素材五类目录点开全报 403 → 范围扩展 research/sources/world/foreshadowing/style；结构化资产（YAML/JSON）点击给友好提示不尝试打开
- 验收：`test_studio_materials_supports_cross_project_query` + `test_studio_materials_filters_pipeline_noise` 新增 2 测（+65 全套 67 过）；`verify-materials.mjs` 8/8 PASS（双项目真实环境：项目 chips/单项目切换/跨项目跳转/类型过滤）

## 六、维护规则

- 每个迭代收尾：更新**状态快照**（日期/完成度/最新提交/测试基线）→ 勾选或调整**方向清单**（done 项移到完成度表的"变化依据"）→ 新增坑写入**已知坑**。
- 新增验证脚本同步登记到**快速检查清单**；服务端口/启动方式变了必须同步更新。
- 本文件与 `ASSESSMENT-2026-08.md`（基线+路线图）互补：评估文档讲"为什么"，本文件讲"现在是什么、怎么查、下一步去哪"。
