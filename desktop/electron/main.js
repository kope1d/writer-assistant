"use strict";

const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const http = require("http");
const { autoUpdater } = require("electron-updater");

const ROOT = path.resolve(__dirname, "..", "..");
const DEFAULT_PORT = 4567;

// ─── JSONL 桌面日志（对齐 CLI/Studio 的 diagnostic_logging.py）───────────────
const LOG_DIR = path.join(ROOT, ".openwrite", "logs");
const LOG_FILE = path.join(LOG_DIR, "desktop.jsonl");
const LOG_MAX_BYTES = 1024 * 1024; // 1 MB
const LOG_BACKUPS = 3;

function ensureLogDir() {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
  } catch (_) { /* 降级：不阻塞主流程 */ }
}

function rotateLogIfNeeded() {
  try {
    if (fs.existsSync(LOG_FILE)) {
      const stat = fs.statSync(LOG_FILE);
      if (stat.size >= LOG_MAX_BYTES) {
        for (let i = LOG_BACKUPS; i >= 1; i--) {
          const backup = path.join(LOG_DIR, `desktop.${i}.jsonl`);
          const older = i === 1 ? LOG_FILE : path.join(LOG_DIR, `desktop.${i - 1}.jsonl`);
          if (fs.existsSync(older)) {
            if (fs.existsSync(backup)) fs.unlinkSync(backup);
            fs.renameSync(older, backup);
          }
        }
      }
    }
  } catch (_) { /* 降级 */ }
}

function desktopLog(level, message, extra = {}) {
  ensureLogDir();
  rotateLogIfNeeded();
  const entry = {
    ts: new Date().toISOString(),
    level,
    logger: "electron.main",
    message,
    ...extra,
  };
  try {
    fs.appendFileSync(LOG_FILE, JSON.stringify(entry) + "\n", "utf8");
  } catch (_) { /* 降级 */ }
  // 同步输出到控制台便于开发调试
  const label = `[desktop ${level}]`;
  if (level === "ERROR") {
    console.error(label, message, extra);
  } else {
    console.log(label, message);
  }
}

// ─── 全局状态 ───────────────────────────────────────────────────────────────
let backend = null;
let mainWindow = null;
let tray = null;
let isQuitting = false;

// ─── 平台配置 ───────────────────────────────────────────────────────────────
if (process.platform === "win32") {
  app.setAppUserModelId("com.writerassistant.app");
}

// ─── 单实例锁 ───────────────────────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  desktopLog("INFO", "second_instance_detected_quitting");
  app.quit();
} else {
  app.on("second-instance", () => {
    desktopLog("INFO", "second_instance_restoring_window");
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ─── Python 候选列表 ────────────────────────────────────────────────────────
function candidatePythons() {
  const candidates = [];
  const venv = path.join(ROOT, ".venv");
  if (process.platform === "win32") {
    candidates.push(path.join(venv, "Scripts", "python.exe"));
    const runtimeRoot = path.join(ROOT, ".openwrite-runtime");
    if (fs.existsSync(runtimeRoot)) {
      for (const entry of fs.readdirSync(runtimeRoot)) {
        const py = path.join(runtimeRoot, entry, "Scripts", "python.exe");
        if (fs.existsSync(py)) candidates.push(py);
      }
    }
  } else {
    candidates.push(path.join(venv, "bin", "python"));
  }
  candidates.push("python");
  return candidates;
}

function firstExisting(candidates) {
  for (const candidate of candidates) {
    if (candidate === "python" || fs.existsSync(candidate)) return candidate;
  }
  return "python";
}

// ─── 健康检查 ───────────────────────────────────────────────────────────────
function waitForHealth(url, timeoutMs, intervalMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (ok, err) => {
      if (settled) return;
      settled = true;
      if (ok) resolve();
      else reject(err);
    };
    const attempt = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode === 200) finish(true);
        else retry();
      });
      req.on("error", retry);
      req.setTimeout(1500, () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() >= deadline) {
        finish(false, new Error("本地引擎启动超时"));
        return;
      }
      setTimeout(attempt, intervalMs);
    };
    attempt();
  });
}

// ─── 窗口状态持久化 ─────────────────────────────────────────────────────────
function windowStateFile() {
  return path.join(app.getPath("userData"), "window-state.json");
}

function loadWindowState() {
  try {
    const state = JSON.parse(fs.readFileSync(windowStateFile(), "utf8"));
    if (typeof state.width === "number" && typeof state.height === "number") {
      return { width: state.width, height: state.height, x: state.x, y: state.y };
    }
  } catch (_) { /* 首次运行 */ }
  return null;
}

// ─── 后端启动 ───────────────────────────────────────────────────────────────
function startBackend() {
  let command;
  let args;
  if (app.isPackaged) {
    command = path.join(
      process.resourcesPath, "backend", "writer-backend",
      process.platform === "win32" ? "writer-backend.exe" : "writer-backend"
    );
    args = ["studio", "--port", String(DEFAULT_PORT), "--no-open", "--debug"];
  } else {
    command = firstExisting(candidatePythons());
    args = ["-m", "tools.cli", "studio", "--port", String(DEFAULT_PORT), "--no-open", "--debug"];
  }
  desktopLog("INFO", "backend_starting", { command, args });
  const child = spawn(command, args, {
    cwd: ROOT,
    windowsHide: true,
    stdio: "ignore",
    env: {
      ...process.env,
      LITELLM_LOCAL_MODEL_COST_MAP: "True",
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
      OPENWRITE_FASTEMBED_CACHE_DIR: path.join(ROOT, ".fastembed-cache"),
      HF_ENDPOINT: "https://hf-mirror.com",
    },
  });
  child.on("error", (err) => {
    desktopLog("ERROR", "backend_spawn_error", { error: err.message });
  });
  child.on("exit", (code, signal) => {
    desktopLog("INFO", "backend_exited", { code, signal });
    backend = null;
  });
  return child;
}

// ─── 托盘 ───────────────────────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(ROOT, "assets", "icon.png");
  let trayIcon;
  try {
    trayIcon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } catch (_) {
    desktopLog("WARNING", "tray_icon_load_failed", { iconPath });
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip("Writer Assistant");

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "显示 Writer Assistant",
      click: () => {
        desktopLog("INFO", "tray_menu_show");
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    { type: "separator" },
    {
      label: "退出",
      click: () => {
        desktopLog("INFO", "tray_menu_quit");
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);

  // 单击托盘图标 → 切换窗口可见性
  tray.on("click", () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.focus();
      } else {
        mainWindow.show();
        mainWindow.focus();
        desktopLog("INFO", "tray_click_restore_window");
      }
    }
  });
}

// ─── 应用启动 ───────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  desktopLog("INFO", "app_ready", { version: app.getVersion(), platform: process.platform });

  backend = startBackend();
  const url = `http://127.0.0.1:${DEFAULT_PORT}/`;
  try {
    await waitForHealth(url, 60_000, 500);
    desktopLog("INFO", "backend_healthy");
  } catch (err) {
    desktopLog("ERROR", "backend_healthcheck_failed", { error: err.message });
    dialog.showErrorBox("Writer Assistant", `无法启动本地引擎：${err.message}`);
    app.quit();
    return;
  }

  // 托盘（在窗口创建之前初始化，确保窗口隐藏时托盘已存在）
  createTray();

  const saved = loadWindowState();
  const win = new BrowserWindow({
    width: saved?.width ?? 1440,
    height: saved?.height ?? 900,
    x: saved?.x,
    y: saved?.y,
    minWidth: 1100,
    minHeight: 700,
    title: "Writer Assistant",
    frame: false,
    autoHideMenuBar: true,
    backgroundColor: "#0f172a",
    icon: path.join(ROOT, "assets", "icon.png"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });
  mainWindow = win;
  desktopLog("INFO", "window_created", { width: win.getBounds().width, height: win.getBounds().height });

  win.once("ready-to-show", () => {
    win.show();
    win.focus();
    desktopLog("INFO", "window_ready_to_show");
  });
  win.loadURL(url);
  win.webContents.setWindowOpenHandler(({ url: target }) => {
    shell.openExternal(target);
    return { action: "deny" };
  });

  // IPC: 窗口控件
  win.on("maximize", () => win.webContents.send("window-maximized-changed", true));
  win.on("unmaximize", () => win.webContents.send("window-maximized-changed", false));
  win.on("focus", () => win.webContents.send("window-focus-changed", true));
  win.on("blur", () => win.webContents.send("window-focus-changed", false));

  // 关闭窗口 → 隐藏到托盘（除非正在退出）
  win.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      win.hide();
      desktopLog("INFO", "window_hidden_to_tray");
    } else {
      // 真正退出：保存窗口状态
      if (!win.isMaximized() && !win.isFullScreen()) {
        try {
          fs.writeFileSync(windowStateFile(), JSON.stringify(win.getBounds()));
        } catch (_) { /* Best-effort */ }
      }
      desktopLog("INFO", "window_closed_permanently");
    }
  });

  // 自动更新（仅打包版本）
  if (app.isPackaged) {
    autoUpdater.autoDownload = true;
    autoUpdater.autoInstallOnAppQuit = true;
    autoUpdater.checkForUpdatesAndNotify().catch((err) => {
      desktopLog("WARNING", "auto_updater_check_failed", { error: err.message });
    });
    autoUpdater.on("update-available", () => desktopLog("INFO", "auto_updater_update_available"));
    autoUpdater.on("update-downloaded", () => desktopLog("INFO", "auto_updater_update_downloaded"));
    autoUpdater.on("error", (err) => desktopLog("ERROR", "auto_updater_error", { error: err.message }));
  }
});

// ─── IPC 处理 ───────────────────────────────────────────────────────────────
ipcMain.on("window-minimize", (event) => {
  BrowserWindow.fromWebContents(event.sender)?.minimize();
});

ipcMain.on("window-maximize-toggle", (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win) return;
  if (win.isMaximized()) win.unmaximize();
  else win.maximize();
});

ipcMain.on("window-close", (event) => {
  BrowserWindow.fromWebContents(event.sender)?.close();
});

// ─── 应用生命周期 ───────────────────────────────────────────────────────────
// 托盘存活时不退出（覆盖默认 window-all-closed → quit）
app.on("window-all-closed", () => {
  // 不 quit —— 托盘保持活跃
  desktopLog("INFO", "all_windows_closed_tray_active");
});

app.on("before-quit", () => {
  isQuitting = true;
  desktopLog("INFO", "app_before_quit");
  if (backend && !backend.killed) {
    backend.kill();
    desktopLog("INFO", "backend_killed");
  }
  if (tray) {
    tray.destroy();
    tray = null;
  }
});

app.on("quit", () => {
  desktopLog("INFO", "app_quit");
});

// ─── 全局异常捕获 ───────────────────────────────────────────────────────────
process.on("uncaughtException", (error) => {
  desktopLog("ERROR", "uncaught_exception", { error: error.message, stack: error.stack });
});

process.on("unhandledRejection", (reason) => {
  desktopLog("ERROR", "unhandled_rejection", { reason: String(reason) });
});
