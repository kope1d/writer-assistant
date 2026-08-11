// 前端视图冒烟测试：17 视图切换 + 旧 hash 兼容 + 编辑器打开/保存状态
// 前置：服务已启动（writer studio --port 4567）；playwright 可解析
// 用法：node tools/studio_assets/dev/verify-views.mjs [BASE]
// playwright 不在本仓库时：设 PLAYWRIGHT_ROOT 指向含 node_modules 的目录
import { createRequire } from "node:module";
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch {
  const root = process.env.PLAYWRIGHT_ROOT;
  if (root) {
    ({ chromium } = createRequire(root + "/")("playwright"));
  } else {
    console.error("playwright 未安装：设 PLAYWRIGHT_ROOT=<含 node_modules 的目录> 后重试");
    process.exit(2);
  }
}

const BASE = process.argv[2] || "http://127.0.0.1:4567/";
const results = [];
const ok = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`);

// 注册表与 audit-views5.mjs 保持一致；editor 容器代表文档/资料库视图
const VIEWS = [
  ["dashboard", "#dashboard-view"],
  ["projects", "#projects-view"],
  ["analytics", "#analytics-view"],
  ["outline", "#outline-view"],
  ["chapters", "#editor-view"],
  ["review", "#review-workspace-view"],
  ["core", "#editor-view"],
  ["style-vault", "#style-vault-view"],
  ["agents", "#agents-view"],
  ["continuity", "#continuity-view"],
  ["materials", "#materials-view"],
  ["research", "#research-view"],
  ["search", "#search-view"],
  ["transfer", "#transfer-view"],
  ["deconstruct", "#deconstruct-view"],
  ["skills", "#skills-view"],
  ["tools", "#tools-view"],
];
const LEGACY = [["story", "core"], ["world", "settings"], ["assets", "characters"]];

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(() => {
  try { localStorage.setItem("writer-product-tour-v2", "seen"); } catch (_) {}
});
const page = await context.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 120)); });
page.on("pageerror", (e) => errors.push("PAGEERROR: " + e.message.slice(0, 120)));
page.on("dialog", (d) => d.accept());

// 等 workspace bootstrap（LightRAG 探测闸门 12s 封顶；此处放宽到 30s）
await page.goto(`${BASE}#dashboard`, { waitUntil: "domcontentloaded" });
let booted = false;
for (let i = 0; i < 30; i++) {
  await page.waitForTimeout(1000);
  booted = await page.evaluate(() => {
    const el = document.querySelector("#dashboard-view");
    return el && !el.hidden;
  });
  if (booted) break;
}
ok("boot dashboard 可见", booted);

// ── 17 视图切换 ──
let viewPass = 0;
for (const [view, sel] of VIEWS) {
  await page.evaluate((v) => { location.hash = "#" + v; }, view);
  let vis = false, st = null;
  for (let i = 0; i < 12; i++) {
    await page.waitForTimeout(500);
    st = await page.evaluate((s) => {
      const el = document.querySelector(s);
      return el ? { vis: el.offsetParent !== null, hidden: el.hidden } : { missing: true };
    }, sel);
    if (st.vis) { vis = true; break; }
  }
  const nav = await page.evaluate(() =>
    document.querySelector(".nav-item.active")?.textContent?.trim()
  );
  if (vis) viewPass++;
  ok(`#${view} 容器可见 + 导航`, vis && !!nav, `容器:${st.missing ? "缺失" : st.vis ? "可见" : "隐藏"} 导航:${nav}`);
}
ok("视图切换 17/17", viewPass === 17, `${viewPass}/17`);

// ── 旧 hash 兼容（normalizeView 映射）──
let legacyPass = 0;
for (const [oldHash, expected] of LEGACY) {
  await page.evaluate((v) => { location.hash = "#" + v; }, oldHash);
  let vis = false;
  for (let i = 0; i < 12; i++) {
    await page.waitForTimeout(500);
    vis = await page.evaluate(() => {
      const el = document.querySelector("#editor-view");
      return el && el.offsetParent !== null;
    });
    if (vis) break;
  }
  if (vis) legacyPass++;
  ok(`#${oldHash} → ${expected} 编辑器容器可见`, vis);
}
ok("旧 hash 兼容 3/3", legacyPass === 3, `${legacyPass}/3`);

// ── 编辑器打开 + 保存状态 ──
let editorOk = false;
try {
  await page.evaluate(() => { location.hash = "#chapters"; });
  await page.waitForTimeout(2000);
  const editorState = await page.evaluate(() => {
    const title = document.querySelector("#editor-title");
    const wordCount = document.querySelector("#editor-word-count");
    const vditor = document.querySelector("#editor-view .vditor");
    const saveState = document.querySelector("#editor-autosave-state")?.textContent || "";
    return {
      hasTitle: !!title && !!title.value,
      hasVditor: !!vditor,
      wordCount: wordCount?.textContent?.trim() || "",
      title: title?.value?.slice(0, 40),
      saveState,
    };
  });
  editorOk = editorState.hasTitle && editorState.hasVditor;
  ok(
    "编辑器加载文档（标题 + vditor + 字数）",
    editorOk,
    `${editorState.title} | 字数:${editorState.wordCount} | 保存态:${editorState.saveState}`
  );
} catch (e) {
  ok("编辑器加载文档（标题 + vditor + 字数）", false, e.message.slice(0, 80));
}

// ── 汇总 ──
console.log(results.join("\n"));
console.log(`\nRESULT: ${results.filter((r) => r.startsWith("PASS")).length} PASS / ${results.filter((r) => r.startsWith("FAIL")).length} FAIL`);
const pageErrors = errors.filter((e) => e.startsWith("PAGEERROR"));
console.log(
  "console errors:",
  pageErrors.length
    ? [...new Set(pageErrors)].join(" || ")
    : "none"
);
await browser.close();
process.exit(results.some((r) => r.startsWith("FAIL")) ? 1 : 0);
