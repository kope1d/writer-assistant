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
</p>

## Writer Assistant 是什么

Writer Assistant 是一个**个人版** AI 长篇小说创作工作台，基于
[OpenWrite](https://github.com/LiPu-jpg/Openwrite) 5.8.0 改造而来。

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

## 与原版的差异

- 品牌与命名改为 Writer Assistant，CLI 命令为 `writer`
- 移除了深度研究（DeepResearch）集成，聚焦写作本身
- v1 已实现两个个人功能：
  - **本地模型一键预设**：支持 Ollama / LM Studio，不联网也能写作
  - **风格档案馆**：导入一部作品，一键提炼文风并保存为档案，写作时直接选择，无需反复调整提示词
- 灵感素材板规划在 v2

## 快速开始

推荐直接双击根目录启动文件（会打开**独立桌面窗口**，使用系统原生 WebView，无需浏览器标签页）：

- Windows：`启动 Writer Assistant.bat`
- macOS：`启动 Writer Assistant.command`

全新克隆后，如果想使用 **Electron 桌面客户端**（Codex 式独立应用窗口），先执行一次：

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

主要工作区：总览、大纲、资料库、正文、创作助手、审稿、AI 协作（Goethe / Dante）、项目搜索与连续性、参考库、Skills、工具与设置。

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

### 风格档案馆（开发中）

从你提供的文本中提炼可复用写作信号（用词、句式、节奏、对话、叙述距离等），
把作品专属内容（人名、世界观、口癖）隔离出去，生成一份可命名、可选择的风格档案。
写作时选中即可注入上下文，不需要重新调 AI。

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

所有顶层命令均支持 `--project <作品目录>`。

## 开发与测试

```bash
python -m pip install -e ".[dev]"
pytest
```

## 许可证与致谢

Writer Assistant 基于 [OpenWrite](https://github.com/LiPu-jpg/Openwrite)（Apache-2.0）改造，
保留原项目 LICENSE 与第三方组件的署名声明。感谢 OpenWrite 的作者与贡献者，
以及 Linux DO 社区关于 AI 写作、长上下文与开源实践的讨论。
