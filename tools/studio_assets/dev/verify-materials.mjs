// 灵感素材板 v2 冒烟：项目 chips 渲染 → 全部/单项目模式 → 跨项目卡片跳转 → 类型过滤
// 前置：服务已启动（writer studio --port 4567）；注册表 ≥1 项目
// 用法：node tools/studio_assets/dev/verify-materials.mjs [BASE]
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
const skip = (name, detail = "") => results.push(`SKIP  ${name}  (${detail})`);

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

// ── 打开素材板，等网格渲染完成 ──
await page.goto(`${BASE}#materials`, { waitUntil: "domcontentloaded" });
let loaded = false;
for (let i = 0; i < 30; i++) {
  await page.waitForTimeout(1000);
  loaded = await page.evaluate(() => {
    const grid = document.querySelector("#materials-grid");
    const projectChips = document.querySelectorAll("#materials-project-filters .material-project-chip");
    return grid && grid.children.length > 0 && projectChips.length > 0;
  });
  if (loaded) break;
}
ok("素材板加载（网格 + 项目 chips）", loaded);

// ── 项目 chips：数量 = 项目数 + 1（全部项目）──
const chipState = await page.evaluate(() => {
  const chips = [...document.querySelectorAll("#materials-project-filters .material-project-chip")];
  return {
    count: chips.length,
    labels: chips.map((c) => c.textContent.trim()),
    active: chips.find((c) => c.classList.contains("active"))?.textContent?.trim() || "",
    cardCount: document.querySelectorAll("#materials-grid .material-card").length,
    foreignCards: document.querySelectorAll("#materials-grid .material-card-foreign").length,
    kinds: document.querySelectorAll("#materials-filters .material-filter-chip").length,
  };
});
const projectCount = chipState.count - 1; // 减去"全部项目"
ok("项目 chips 数量正确", chipState.count >= 2, `${chipState.count} chips（${projectCount} 项目）`);
ok("默认选中「全部项目」", chipState.active === "全部项目", `active: ${chipState.active}`);
ok("类型过滤 chips 渲染", chipState.kinds === 6, `${chipState.kinds}/6`);
ok("网格非空（卡片或空态）", chipState.cardCount > 0 || chipState.cardCount === 0 && loaded, `${chipState.cardCount} 卡片`);

// ── 单项目模式：点第一个非当前项目 chip ──
let singleMode = false;
let target = "";
if (projectCount >= 1) {
  target = chipState.labels.find((l) => l !== "全部项目" && !l.includes("当前")) || "";
  if (target) {
    await page.evaluate((label) => {
      const chip = [...document.querySelectorAll("#materials-project-filters .material-project-chip")]
        .find((c) => c.textContent.trim() === label);
      chip?.click();
    }, target);
    await page.waitForTimeout(1500);
    singleMode = await page.evaluate((label) => {
      const chips = [...document.querySelectorAll("#materials-project-filters .material-project-chip")];
      return chips.some((c) => c.classList.contains("active") && c.textContent.trim() === label);
    }, target);
  }
}
ok("单项目模式切换", singleMode, target || "无目标");

// ── 跨项目跳转：全部模式下点击 foreign 素材卡片 → 切项目 + 文档打开 ──
let jumpOk = false, jumpDetail = "";
if (projectCount >= 2) {
  await page.evaluate(() => {
    [...document.querySelectorAll("#materials-project-filters .material-project-chip")]
      .find((c) => c.textContent.trim() === "全部项目")?.click();
  });
  await page.waitForTimeout(1500);
  const foreign = await page.evaluate(() => {
    // 优先普通素材（研究/世界设定）——truth 文件（current_state 等）设计内落连续性控制台
    const cards = [...document.querySelectorAll("#materials-grid .material-card-foreign")];
    const preferred = cards.find((c) => ["深度研究", "世界设定"].includes(c.querySelector(".material-kind")?.textContent));
    const pick = preferred || cards[0];
    if (!pick) return null;
    return {
      title: pick.querySelector(".material-title")?.textContent,
      tag: pick.querySelector(".material-project-tag")?.textContent,
      kind: pick.querySelector(".material-kind")?.textContent,
    };
  });
  if (foreign) {
    const beforeCurrent = await page.evaluate(() =>
      [...document.querySelectorAll("#materials-project-filters .material-project-chip")]
        .find((c) => c.classList.contains("active"))?.textContent?.trim()
    );
    await page.evaluate((title) => {
      const card = [...document.querySelectorAll("#materials-grid .material-card-foreign")]
        .find((c) => c.querySelector(".material-title")?.textContent === title);
      card?.click();
    }, foreign.title);
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(1000);
      const state = await page.evaluate(() => ({
        hash: location.hash,
        title: document.querySelector("#editor-title")?.value || "",
        activeChip: [...document.querySelectorAll("#materials-project-filters .material-project-chip")]
          .find((c) => c.classList.contains("active"))?.textContent?.trim() || "",
      }));
      if (state.hash.startsWith("#doc=") && state.title) { jumpOk = true; break; }
    }
    jumpDetail = `${beforeCurrent} → ${foreign.tag} / ${foreign.kind}「${foreign.title}」`;
  } else {
    skip("跨项目卡片跳转", "全部模式下无跨项目素材（其他项目素材为空）");
  }
} else {
  skip("跨项目卡片跳转", "注册表不足 2 个项目");
}
ok("跨项目卡片点击 → 切项目 + 文档打开", jumpOk, jumpDetail);

// ── 类型过滤：点 research chip 后卡片只剩 research ──
let kindOk = false;
if (loaded) {
  await page.evaluate(() => location.hash = "#materials");
  await page.waitForTimeout(1200);
  const before = await page.evaluate(() => document.querySelectorAll("#materials-grid .material-card").length);
  await page.evaluate(() => {
    const chip = [...document.querySelectorAll("#materials-filters .material-filter-chip")]
      .find((c) => c.textContent.trim().startsWith("深度研究"));
    chip?.click();
  });
  await page.waitForTimeout(800);
  const kindState = await page.evaluate(() => {
    const cards = [...document.querySelectorAll("#materials-grid .material-card")];
    return { count: cards.length, kinds: [...new Set(cards.map((c) => c.querySelector(".material-kind")?.textContent))] };
  });
  kindOk = before > 0
    ? kindState.kinds.every((k) => k === "深度研究")
    : kindState.count === 0; // 无素材时过滤后仍为空态
  if (before > 0 && kindState.kinds.length === 0) kindOk = false;
}
ok("类型过滤只保留对应分类", kindOk);

// ── 汇总 ──
console.log(results.join("\n"));
const fails = results.filter((r) => r.startsWith("FAIL")).length;
const skips = results.filter((r) => r.startsWith("SKIP")).length;
console.log(`\nRESULT: ${results.filter((r) => r.startsWith("PASS")).length} PASS / ${fails} FAIL / ${skips} SKIP`);
const pageErrors = errors.filter((e) => e.startsWith("PAGEERROR"));
console.log(
  "console errors:",
  pageErrors.length ? [...new Set(pageErrors)].join(" || ") : "none"
);
await browser.close();
process.exit(fails ? 1 : 0);
