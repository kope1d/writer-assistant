// 桌面端 E2E 冒烟：窗口创建 → 后端健康 → close-to-tray → 恢复窗口 → 退出释放端口
// 前置：desktop/node_modules 已安装（npm install）；端口 4567 空闲；无其他桌面端实例在跑
// 用法：node tools/studio_assets/dev/verify-desktop.mjs
// playwright 不在本仓库时：设 PLAYWRIGHT_ROOT 指向含 node_modules 的目录
import { createRequire } from "node:module";
import http from "node:http";
import path from "node:path";

let chromium, electron;
try {
  ({ chromium, _electron: electron } = require("playwright"));
} catch {
  const root = process.env.PLAYWRIGHT_ROOT;
  if (root) {
    ({ chromium, _electron: electron } = createRequire(root + "/")("playwright"));
  } else {
    console.error("playwright 未安装：设 PLAYWRIGHT_ROOT=<含 node_modules 的目录> 后重试");
    process.exit(2);
  }
}

const DESKTOP_DIR = path.resolve(import.meta.dirname, "../../../desktop");
const ELECTRON_EXE = path.join(
  DESKTOP_DIR,
  "node_modules",
  "electron",
  "dist",
  process.platform === "win32" ? "electron.exe" : "electron"
);
const BASE = "http://127.0.0.1:4567/";
const results = [];
const ok = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`);

function checkHealth(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(3000, () => { req.destroy(); resolve(false); });
  });
}

// ── 前置：端口空闲 + 无残留实例 ──
const portFree = (await checkHealth(BASE)) === false;
ok("前置：4567 端口空闲", portFree);

// ── 启动 Electron ──
let app;
try {
  app = await electron.launch({
    executablePath: ELECTRON_EXE,
    args: ["."],
    cwd: DESKTOP_DIR,
    env: { ...process.env, ELECTRON_DISABLE_SECURITY_WARNINGS: "true" },
  });
  ok("Electron 启动", true);
} catch (e) {
  ok("Electron 启动", false, e.message.slice(0, 120));
  console.log(results.join("\n"));
  process.exit(1);
}

// ── 窗口创建 + Studio 加载 ──
let win = null;
try {
  win = await app.firstWindow();
  await win.waitForLoadState("domcontentloaded");
} catch (e) {
  ok("窗口创建", false, e.message.slice(0, 120));
}
ok("窗口创建", !!win);

let loaded = false;
if (win) {
  for (let i = 0; i < 45; i++) {
    await win.waitForTimeout(1000);
    loaded = await win
      .evaluate(() => {
        const el = document.querySelector("#dashboard-view");
        return !!el && !el.hidden;
      })
      .catch(() => false);
    if (loaded) break;
  }
}
ok("窗口加载 Studio（dashboard 可见）", loaded);

// ── 后端健康 ──
const healthy = await checkHealth(BASE + "api/health");
ok("后端 4567 健康", healthy);

// ── close-to-tray：关窗口 → 进程存活 + 窗口隐藏 ──
let trayState = { count: 0, visible: null };
if (win) {
  await app.evaluate(({ BrowserWindow }) => {
    BrowserWindow.getAllWindows()[0]?.close();
  });
  await win.waitForTimeout(1500);
  trayState = await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows()[0];
    return { count: BrowserWindow.getAllWindows().length, visible: w ? w.isVisible() : null };
  });
}
ok(
  "close-to-tray 进程存活 + 窗口隐藏",
  trayState.count === 1 && trayState.visible === false,
  `窗口数:${trayState.count} 可见:${trayState.visible}`
);

// ── 恢复窗口（托盘单击路径的等效操作）──
let restored = false;
if (win) {
  await app.evaluate(({ BrowserWindow }) => {
    BrowserWindow.getAllWindows()[0]?.show();
  });
  await win.waitForTimeout(800);
  restored = await app.evaluate(({ BrowserWindow }) => {
    const w = BrowserWindow.getAllWindows()[0];
    return !!w && w.isVisible();
  });
}
ok("恢复窗口可见", restored);

// ── 退出 → 进程结束 + 端口释放 ──
try {
  await app.evaluate(({ app }) => app.quit());
  await app.close(); // 等进程真正退出
} catch (_) { /* 已退出 */ }

let freed = false;
for (let i = 0; i < 15; i++) {
  await new Promise((r) => setTimeout(r, 500));
  if ((await checkHealth(BASE)) === false) { freed = true; break; }
}
ok("退出后端口释放", freed);

// ── 汇总 ──
console.log(results.join("\n"));
const fails = results.filter((r) => r.startsWith("FAIL")).length;
console.log(`\nRESULT: ${results.length - fails} PASS / ${fails} FAIL`);
process.exit(fails ? 1 : 0);
