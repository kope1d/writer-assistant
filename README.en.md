<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/logo-light.svg">
    <img src="assets/logo-light.svg" width="380" alt="Writer Assistant">
  </picture>
</p>

<h1 align="center">Writer Assistant<br><sub>A personal AI novel-writing workbench</sub></h1>

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

## What is Writer Assistant

Writer Assistant is a **personal** AI long-form novel writing workbench,
adapted from [OpenWrite](https://github.com/LiPu-jpg/Openwrite) 5.8.0,
built for **single-user, local-first** creative workflows.

It solves one core problem: when a novel grows past dozens or hundreds of chapters,
how does the AI stop losing the author's intent and the story's facts?
Writer Assistant keeps author intent, character & world state, a rolling outline,
chapter memory, drafting, review, and revision in one continuous creative pipeline.

```text
Ideas & material
    ↓
Goethe: planning, characters, setting, outline
    ↓  confirmed writable assets
Dante: assemble context → draft → review → revise → settle state
    ↓
Markdown / TXT / EPUB
```

## Key Features

### ✍️ Long-form memory: fact arbitration loop

At novel scale, models lose track of established facts. Writer Assistant guards
against fact drift with **three layers**:

1. **Truth Files**: three runtime-truth documents — `current_state.md`, `ledger.md`,
   `relationships.md` — stored uniformly as "TOML front matter + Markdown body".
   Humans and agents read the same documents.
2. **Regex ↔ delta cross-validation**: after each chapter, facts extracted by regex
   are cross-checked against the structured delta returned by the LLM. Missing,
   contradictory, or structurally drifted facts are explicitly flagged — never silently passed.
3. **Snapshot transactions & rollback**: a state snapshot is created before each
   chapter is written; multi-write goes through atomic replacement + snapshot rollback,
   so any failed step restores a known-good previous state.

### 🎭 Two agents, a clear handoff

- **Goethe** — the long-running *planning* agent: turns ideas into writable assets
  (characters, settings, outline), then explicitly hands off.
- **Dante** — the long-running *writing* agent: pre-check, drafting, review, revision,
  and state settlement.

Production asset writes require a previewed diff and author confirmation.
**"Done" comes from tool results and file state — never from the model's word.**

### 🔍 Semantic search with instant fallback

Project material, manuscripts, and reference library are indexed with LightRAG.
When embeddings are unavailable, a **probe gate degrades to exact text search in
seconds** (with a 1800s failure cache — no more blind waits). The writing pipeline
never blocks on retrieval.

### 🎨 Style Archive

Import a work and extract reusable writing signals (diction, sentence patterns,
rhythm, dialogue, narrative distance) while isolating work-specific content
(names, worldbuilding, catchphrases). Save it as a named, selectable style profile;
pick it at writing time without re-tuning prompts.

### 🖥️ Multiple entry points, one kernel

- **Studio** (web workbench, 17 views, the default entry)
- **Electron desktop client** (standalone window + tray + auto-update)
- **Built-in WebView desktop window** (Node-free lightweight option)
- **CLI** (26 commands, for scripting and debugging)

All entries share one novel application service and one action surface —
chapter IDs, project locks, transactional rollback, review storage, and BookState
settlement are a single contract.

### 🧪 Engineering quality

- **965 automated tests** covering fact arbitration, snapshot rollback, project
  registry, desktop launcher, runtime diagnostics, and more;
- **Unified JSONL logging**: CLI / Studio / desktop main process all write to
  `.openwrite/logs/` structured logs; one-click diagnostic bundle export;
- **Transactional file writes**: tempfile + fsync + atomic rename — an interrupted
  write never leaves a corrupted file behind.

## Privacy & Security Statement

- **Local-first**: Studio binds to `127.0.0.1` only — never exposed to your LAN.
- **No telemetry**: no usage data is collected, no external analytics calls.
- **Your models, your choice**: Ollama / LM Studio / any OpenAI-compatible endpoint /
  local FastEmbed semantic indexing.
- **Your data stays yours**: all novel files are plain Markdown / YAML / JSON,
  stored in project directories you choose.

## Quick Start

Double-click the launcher in the repo root (opens a **native desktop window** via
WebView, no browser tab needed):

- Windows: `启动 Writer Assistant.bat`
- macOS: `启动 Writer Assistant.command`

For the **Electron desktop client** (Codex-style standalone app window), install once:

```bash
cd desktop
npm install
```

If Electron is not installed, the launcher automatically falls back to the built-in
WebView window.

### Installed build (Windows)

Download `Writer Assistant Setup 0.1.0.exe` from GitHub Releases and install:
a Writer Assistant shortcut appears on your desktop — no Python or Node required.

The desktop client checks GitHub Releases for updates on each launch and auto-updates.
For a **private** repo, set a `GH_TOKEN` environment variable (with `repo` scope);
public repos need no configuration.

Run from source:

```bash
git clone <your-repo-url>
cd writer-assistant
python3.10 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -e .
writer studio
```

Studio binds to `127.0.0.1` by default. The first-run onboarding walks you through
model configuration, creating a novel, building story assets, and starting to write.

## The Studio Workbench

```bash
writer studio
```

**Studio is the recommended daily entry point** — book creation, planning, material
maintenance, drafting, review/revision, and export all happen here. The CLI exists
for scripting and debugging.

Workspaces include: overview, writing dashboard, outline, library, manuscript,
creative assistant, review, AI collaboration (Goethe / Dante), project search &
continuity, inspiration board, reference library, Skills, tools & settings.

**Author-facing guide: [`docs/AUTHOR-MANUAL.md`](docs/AUTHOR-MANUAL.md)** — starting
a book, the goethe→dante daily loop, style library, writing intervention, model
config — all in plain language.

**Status & roadmap: [`docs/PROGRESS-CHECK.md`](docs/PROGRESS-CHECK.md)** — completion
score, quick check commands, known pitfalls, decided directions.

## How It Works

### One novel kernel, shared by every entry

Studio, Goethe, Dante, and CLI do not each maintain their own drafting logic.
They share one novel application service and action surface. Chapter IDs, project
locks, transactional rollback, review storage, and BookState settlement are a single
contract. Completion comes from tool results and file state — never from the model's
verbal claim.

### Single source of truth vs. runtime state

```text
data/novels/{novel_id}/
├── src/                         # confirmed source of truth, human + AI readable
│   ├── outline.md
│   ├── story/author_intent.md
│   ├── story/current_focus.md
│   ├── characters/*.md
│   └── world/*.md
└── data/                        # runtime state, manuscripts, caches, snapshots
    ├── manuscript/
    ├── memory/chapters/
    ├── reviews/
    └── workflows/
```

`src/outline.md` is the single outline source of truth; `src/story/author_intent.md`
holds the book-long commitments; `src/story/current_focus.md` holds the current phase
goals; `data/` holds manuscripts, sessions, chapter memory, reviews, state, and workflows.

## CLI & Automation (optional)

Daily writing needs no commands; the CLI serves headless servers, scripted batch
processing, and precise debugging:

```bash
writer studio
writer desktop
writer status
writer write ch_005
writer review ch_005
writer goethe
writer dante
```

All top-level commands accept `--project <novel-directory>`.

## Development & Testing

```bash
python -m pip install -e ".[dev]"
pytest
```

Note: on Windows, if pytest hits a basetemp PermissionError, pass `--basetemp`
with an alternate temp directory.

## License & Acknowledgments

Writer Assistant is adapted from [OpenWrite](https://github.com/LiPu-jpg/Openwrite)
(Apache-2.0). The original LICENSE and third-party attribution notices are retained.
Thanks to the authors and contributors of OpenWrite, and to the Linux DO community
for discussions on AI writing, long context, and open-source practice.
