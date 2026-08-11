<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/logo-light.svg">
    <img src="assets/logo-light.svg" width="380" alt="Writer Assistant">
  </picture>
</p>

<h1 align="center">Writer Assistant<br><sub>个人 AI 长篇小说创作工作台</sub></h1>

<p align="center">
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/version-0.1.0-2563eb" alt="Version 0.1.0"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-%E2%89%A53.10-22c55e?logo=python&logoColor=white" alt="Python >= 3.10"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-0f766e" alt="Apache-2.0 License"></a>
  <a href="tests/"><img src="https://img.shields.io/badge/tests-965%20passed-22c55e" alt="965 tests passing"></a>
</p>

<p align="center">
  <a href="README.md">简体中文</a> · <a href="README.en.md">English</a>
</p>

---

## Writer Assistant 是什么

Writer Assistant 是一个**个人版** AI 长篇小说创作工作台，基于
[OpenWrite](https://github.com/LiPu-jpg/Openwrite) 5.8.0 改造而来，
面向**单用户、本地优先**的创作场景。

它解决的核心问题是：长篇小说写到几十、几百章之后，AI 如何不丢失作者意图和故事事实。
Writer Assistant 把作者意图、人物与世界状态、滚动大纲、章节记忆、写作、审稿和修订放进同一条可持续的创作流程。

```text
灵感与素材
    ↓
Goethe：规划、人物、设定、大纲
    ↓  确认可写资产
Dante：组装上下文 → 写章 → 审稿 → 修订 → 状态结算
    ↓
Markdown / TXT / EPUB
```

## 核心特性

### ✍️ 长文不失忆：事实仲裁闭环

几十万字的创作里，模型最容易"翻旧账"。Writer Assistant 用**三层防护**保证事实不漂移：

1. **真相文件（Truth Files）**：`current_state.md` / `ledger.md` / `relationships.md` 三份运行态真相，
   以「TOML front matter + Markdown 正文」统一存储，人和 AI 读的是同一份文档；
2. **正则 ↔ delta 交叉校验**：写章后，正则抽取的事实与 LLM 返回的结构化 delta 互相印证，
   漏掉的、矛盾的、格式漂移的都会被显式标记，绝不静默放过；
3. **快照事务与回滚**：每章写作前创建状态快照，multi-write 走原子替换 + 快照回滚，
   任何一步失败都能恢复到可用的前一状态。

### 🎭 Goethe / Dante 双 Agent 分工

- **Goethe**：长期会话规划 Agent，把灵感整理成人物、设定、大纲等可写资产，成熟时显式交接；
- **Dante**：长期会话写作 Agent，负责预检、写章、审稿、修订和状态结算。

两者通过明确 handoff 衔接；正式资产写入必须先预览 diff，等作者确认后才能应用。
**"完成"来自工具结果与文件状态，不依赖模型口头宣称。**

### 🔍 语义搜索 + 快速降级

项目内素材、正文、参考库全部进入 LightRAG 语义索引；embedding 不可用时
**探测闸门秒级降级**为精确文本搜索（1800s 失败缓存，不再白等），写作链永不因检索阻塞。

### 🎨 风格档案馆

导入一部作品，一键提炼可复用写作信号（用词、句式、节奏、对话、叙述距离），
把作品专属内容（人名、世界观、口癖）隔离出去，生成可命名、可选择的风格档案。
写作时选中即可注入上下文，不需要反复调整提示词。

### 🖥️ 多种入口，一套内核

- **Studio**（Web 工作台，17 个视图，默认入口）
- **Electron 桌面客户端**（独立窗口 + 托盘 + 自动更新）
- **内置 WebView 桌面窗口**（无需 Node 的轻量方案）
- **CLI**（26 个命令，脚本化与调试）

所有入口共用同一个小说应用服务与 action surface——章节 ID、项目锁、事务回滚、
审稿存储和 BookState 结算只有一份契约。

### 🧪 工程质量

- **965 个自动化测试**：覆盖事实仲裁、快照回滚、项目注册表、桌面启动器、运行时诊断等关键路径；
- **统一 JSONL 日志**：CLI / Studio / 桌面主进程全部落 `.openwrite/logs/` 结构化日志，
  诊断包一键导出；
- **事务性文件写入**：tempfile + fsync + 原子替换，写一半断电也不会留坏文件。

## 隐私与安全声明

- **本地优先**：Studio 默认只绑定 `127.0.0.1`，不开放局域网；
- **无遥测**：不收集任何使用数据，无任何外部统计调用；
- **模型自选**：支持 Ollama / LM Studio / 任意 OpenAI 兼容端点 / 本地 FastEmbed 语义索引；
- **数据归属**：所有作品文件都是普通 Markdown / YAML / JSON，存放在你自己选择的项目目录。

## 快速开始

推荐直接双击根目录启动文件（会打开**独立桌面窗口**，使用系统原生 WebView，无需浏览器标签页）：

- Windows：`启动 Writer Assistant.bat`
- macOS：`启动 Writer Assistant.command`

全新克隆后，如果想使用 **Electron 桌面客户端**，先执行一次：

```bash
cd desktop
npm install
```

未安装 Electron 客户端时，双击启动器会自动退回内置桌面窗口，不会中断。

### 安装版（Windows）

也可以直接从 GitHub Releases 下载 `Writer Assistant Setup 0.1.0.exe` 安装：
安装后桌面上会出现 Writer Assistant 快捷方式，双击即可打开独立桌面应用，
不需要安装 Python 或 Node。

桌面客户端每次启动会检查 GitHub Releases 是否有新版本并自动更新；
如果你的仓库是私有的，需要在系统环境变量中配置 `GH_TOKEN`（具有 repo 权限），
公开仓库则无需配置。

从源码运行：

```bash
git clone <你的仓库地址>
cd writer-assistant
python3.10 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -e .
writer studio
```

Studio 默认只绑定 `127.0.0.1`。首次打开会引导配置模型、创建作品、完善故事资产并开始写作。

## Studio 工作台

```bash
writer studio
```

**Studio 是 Writer Assistant 首推的日常入口。** 建书、规划、资料维护、正文写作、审稿修订和成书导出都可以在这里完成；CLI 只是同一套能力面向脚本化与调试场景的补充。

主要工作区：总览、写作仪表盘、大纲、资料库、正文、创作助手、审稿、AI 协作（Goethe / Dante）、项目搜索与连续性、灵感素材板、参考库、Skills、工具与设置。

**作者向操作指南见 [`docs/AUTHOR-MANUAL.md`](docs/AUTHOR-MANUAL.md)**：开新书、goethe→dante 日常循环、风格库、写作干预、模型配置，全程零代码术语。

**进度与方向见 [`docs/PROGRESS-CHECK.md`](docs/PROGRESS-CHECK.md)**：完成度、快速检查清单、已知坑、已定迭代方向——读一份即可快速掌握项目状态。

## 工作原理

### 一个小说内核，多入口共用

Studio、Goethe、Dante 和 CLI 不各自维护一套写章逻辑，而是共用同一个小说应用服务与 action surface。
章节 ID、项目锁、事务回滚、审稿存储和 BookState 结算只有一份契约；完成态来自工具结果与文件状态，不依赖模型口头宣称。

### 单一真源与运行态分离

```text
data/novels/{novel_id}/
├── src/                         # 人和 AI 共读的确认版真源
│   ├── outline.md
│   ├── story/author_intent.md
│   ├── story/current_focus.md
│   ├── characters/*.md
│   └── world/*.md
└── data/                        # 运行态、正文、缓存与快照
    ├── manuscript/
    ├── memory/chapters/
    ├── reviews/
    └── workflows/
```

`src/outline.md` 是唯一大纲真源；`src/story/author_intent.md` 保存全书长期承诺；
`src/story/current_focus.md` 保存当前阶段目标；`data/` 保存正文、会话、章节记忆、审稿、状态与 workflow。

### Goethe / Dante 双 Agent

- **Goethe**：长期会话规划 Agent，把灵感整理成人物、设定、大纲等可写资产，并在资产成熟时显式交接给 Dante。
- **Dante**：长期会话写作 Agent，负责预检、写章、审稿、修订和状态结算。

两者通过明确 handoff 衔接；正式资产写入必须先预览 diff，等用户本轮确认后才能应用。

## CLI 与自动化（可选）

日常创作不需要记命令；CLI 保留给无界面服务器、脚本化批处理和精确调试：

```bash
writer studio
writer desktop
writer status
writer write ch_005
writer review ch_005
writer goethe
writer dante
```

所有顶层命令均支持 `--project <作品目录>`。交互式会话用 `writer repl`：逐条输入任意命令，`help` 查看命令表，`exit` 退出；Windows 下自带行编辑与上下键历史，管道/脚本喂命令同样可用，单条命令失败不会中断会话。

## 开发与测试

```bash
python -m pip install -e ".[dev]"
pytest
```

注意：Windows 上如遇 pytest basetemp PermissionError，请用 `--basetemp` 指定临时目录。

## 许可证与致谢

Writer Assistant 基于 [OpenWrite](https://github.com/LiPu-jpg/Openwrite)（Apache-2.0）改造，
保留原项目 LICENSE 与第三方组件的署名声明。感谢 OpenWrite 的作者与贡献者，
以及 Linux DO 社区关于 AI 写作、长上下文与开源实践的讨论。
