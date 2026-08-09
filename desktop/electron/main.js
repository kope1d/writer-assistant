"use strict";

const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const http = require("http");
const { autoUpdater } = require("electron-updater");

const ROOT = path.resolve(__dirname, "..", "..");
const DEFAULT_PORT = 4567;

if (process.platform === "win32") {
  app.setAppUserModelId("com.writerassistant.app");
}

function candidatePythons() {
  const candidates = [];
  const venv = path.join(ROOT, ".venv");
  if (process.platform === "win32") {
    candidates.push(path.join(venv, "Scripts", "python.exe"));
    const runtimeRoot = path.join(ROOT, ".openwrite-runtime");
    if (fs.existsSync(runtimeRoot)) {
      for (const entry of fs.readdirSync(runtimeRoot)) {
        const py = path.join(runtimeRoot, entry, "Scripts", "python.exe");
        if (fs.existsSync(py)) {
          candidates.push(py);
        }
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
    if (candidate === "python" || fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return "python";
}

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
        if (res.statusCode === 200) {
          finish(true);
        } else {
          retry();
        }
      });
      req.on("error", retry);
      req.setTimeout(1500, () => {
        req.destroy();
        retry();
      });
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

let backend = null;

function startBackend() {
  let command;
  let args;
  if (app.isPackaged) {
    command = path.join(
      process.resourcesPath,
      "backend",
      "writer-backend",
      process.platform === "win32" ? "writer-backend.exe" : "writer-backend"
    );
    args = ["studio", "--port", String(DEFAULT_PORT), "--no-open"];
  } else {
    command = firstExisting(candidatePythons());
    args = ["-m", "tools.cli", "studio", "--port", String(DEFAULT_PORT), "--no-open"];
  }
  const child = spawn(command, args, {
    cwd: ROOT,
    windowsHide: true,
    stdio: "ignore",
    env: { ...process.env, LITELLM_LOCAL_MODEL_COST_MAP: "True" },
  });
  child.on("error", (err) => {
    console.error("[writer-assistant] backend error:", err);
  });
  return child;
}

app.whenReady().then(async () => {
  backend = startBackend();
  const url = `http://127.0.0.1:${DEFAULT_PORT}/`;
  try {
    await waitForHealth(url, 60_000, 500);
  } catch (err) {
    dialog.showErrorBox("Writer Assistant", `无法启动本地引擎：${err.message}`);
    app.quit();
    return;
  }

  const win = new BrowserWindow({
    width: 1440,
    height: 900,
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

  win.once("ready-to-show", () => {
    win.show();
    win.focus();
  });
  win.loadURL(url);
  win.webContents.setWindowOpenHandler(({ url: target }) => {
    shell.openExternal(target);
    return { action: "deny" };
  });
  win.on("maximize", () => win.webContents.send("window-maximized-changed", true));
  win.on("unmaximize", () => win.webContents.send("window-maximized-changed", false));

  if (app.isPackaged) {
    autoUpdater.autoDownload = true;
    autoUpdater.autoInstallOnAppQuit = true;
    autoUpdater.checkForUpdatesAndNotify().catch(() => {});
  }
});

ipcMain.on("window-minimize", (event) => {
  BrowserWindow.fromWebContents(event.sender)?.minimize();
});

ipcMain.on("window-maximize-toggle", (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win) return;
  if (win.isMaximized()) {
    win.unmaximize();
  } else {
    win.maximize();
  }
});

ipcMain.on("window-close", (event) => {
  BrowserWindow.fromWebContents(event.sender)?.close();
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  if (backend && !backend.killed) {
    backend.kill();
  }
});
