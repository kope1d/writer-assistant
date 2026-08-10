// 项目落地页验证脚本：卡片渲染 + 当前标记 + 打开切换 + 截图
// 前置：服务已启动（writer studio，默认 :4569）；playwright 可解析
// 用法：node tools/studio_assets/dev/verify-projects.mjs [BASE] [截图目录]
// playwright 不在本仓库时：设 PLAYWRIGHT_ROOT 指向含 node_modules 的目录，
// 或把脚本放到含 playwright 的工作目录（如 E:\Claude Code code）下运行。
import { createRequire } from "node:module";
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch {
  const root = process.env.PLAYWRIGHT_ROOT;
  if (root) {
    ({ chromium } = createRequire(root + "/")( "playwright"));
  } else {
    console.error("playwright 未安装：设 PLAYWRIGHT_ROOT=<含 node_modules 的目录> 后重试");
    process.exit(2);
  }
}

const BASE = process.argv[2] || "http://127.0.0.1:4569/";
const shotDir = process.argv[3] || ".";
const results = [];
const ok = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`);

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
// 预置产品导览已看完标记，避免 first-run tour 遮罩盖住视图
await context.addInitScript(() => {
  try { localStorage.setItem("writer-product-tour-v2", "seen"); } catch (_) {}
});
const page = await context.newPage();
page.on("pageerror", (err) => console.log("[pageerror]", err.message));

// 直接开 #projects：/api/projects 秒回，不受 workspace bootstrap 拖累
await page.goto(`${BASE}#projects`, { waitUntil: "domcontentloaded" });
// start() 先 await loadWorkspace（LightRAG bootstrap ~12s）再 routeFromLocation
const busy = () => page.evaluate(() => document.querySelector("#app")?.getAttribute("aria-busy"));
for (let i = 0; i < 24; i++) {
  await page.waitForTimeout(3000);
  if ((await busy()) !== "true") break;
}

const state = await page.evaluate(() => {
  const text = (sel) => (document.querySelector(sel) || { textContent: "" }).textContent.trim().slice(0, 60);
  const cards = [...document.querySelectorAll(".project-card")];
  return {
    viewHidden: document.querySelector("#projects-view")?.hidden ?? "MISSING",
    navActive: text(".nav-item.active"),
    cardCount: cards.length,
    titles: cards.map((c) => c.querySelector(".project-card-title")?.textContent.trim()),
    currentBadges: document.querySelectorAll(".project-current-badge").length,
    badgeOnFirst: cards[0]?.querySelector(".project-current-badge") ? true : false,
    openButtons: [...document.querySelectorAll(".project-open-btn")].map((b) => b.textContent.trim()),
  };
});
ok("projects-view 可见", state.viewHidden === false, String(state.viewHidden));
ok("导航激活项为 项目", state.navActive === "项目", state.navActive);
ok("卡片数量 ≥ 2", state.cardCount >= 2, `${state.cardCount} 张: ${state.titles.join("/")}`);
ok("当前标记唯一且落在首卡", state.currentBadges === 1 && state.badgeOnFirst, `${state.currentBadges} 个`);
ok(
  "首卡为当前态按钮、次卡为打开按钮",
  state.openButtons[0]?.includes("已在当前") && state.openButtons[1] === "打开作品",
  state.openButtons.join(" / ")
);

// 点击第二张卡（B）打开 → 应跳 dashboard
await page.evaluate(() => {
  const cards = document.querySelectorAll(".project-card");
  cards[1].querySelector(".project-open-btn").click();
});
// 轮询 dashboard 出现（切换后重新 bootstrap 可能 60s+）
let switched = false;
for (let i = 0; i < 45; i++) {
  await page.waitForTimeout(2000);
  const s = await page.evaluate(() => ({
    dashHidden: document.querySelector("#dashboard-view").hidden,
    nav: document.querySelector(".nav-item.active")?.textContent?.trim(),
  }));
  if (!s.dashHidden && s.nav === "总览") { switched = true; break; }
}
const after = await page.evaluate(() => ({
  viewHidden: document.querySelector("#dashboard-view").hidden,
  navActive: document.querySelector(".nav-item.active")?.textContent?.trim(),
  toast: document.querySelector(".toast")?.textContent?.trim().slice(0, 40),
}));
ok("切换后 dashboard 可见 + 导航回总览", after.viewHidden === false && after.navActive === "总览", `${after.navActive}`);
ok("切换 toast 提示", (after.toast || "").includes("已打开"), after.toast);

console.log(results.join("\n"));
console.log(results.some((r) => r.startsWith("FAIL")) ? "RESULT: FAIL" : "RESULT: PASS");
await page.screenshot({ path: `${shotDir}/projects_switched.png` });
await browser.close();
process.exit(results.some((r) => r.startsWith("FAIL")) ? 1 : 0);
