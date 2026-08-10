// UI 动效 + 主题 FOUC 验证脚本
import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8799/";
const results = [];
const ok = (name, pass, detail = "") =>
  results.push(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`);

const browser = await chromium.launch();

// 等待应用真正就绪：dashboard 初始静态可见，须等 workspace 加载完成
//（否则 setView 在 `if (!state.workspace) return` 处静默返回）
async function waitAppReady(page) {
  await page.evaluate(async () => {
    const core = await import("/js/core.js");
    const s = core.state;
    const t0 = Date.now();
    while (!s.workspace && Date.now() - t0 < 15000) {
      await new Promise((r) => setTimeout(r, 100));
    }
  });
}

// ---- 1. 深色 FOUC：预置 localStorage，首次导航后首帧即深色 ----
{
  const ctx = await browser.newContext();
  // 先写入 localStorage 再加载页面
  await ctx.addInitScript(() => {
    try { localStorage.setItem("writer-theme", "dark"); } catch (_) {}
  });
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  // 首帧：在 app.js 模块执行后、任何用户交互前检查
  const themeAtLoad = await page.evaluate(() => document.documentElement.dataset.theme);
  const bodyBg = await page.evaluate(() =>
    getComputedStyle(document.body).backgroundColor
  );
  ok("深色主题首帧预应用", themeAtLoad === "dark", `data-theme=${themeAtLoad}, body=${bodyBg}`);
  // 页面整体是否深色（无浅色闪烁 = body 背景非浅色 #f4f4f1）
  ok("深色首帧背景", !/^rgb\(244, 244, 241\)$/.test(bodyBg), `body=${bodyBg}`);
  await ctx.close();
}

// ---- 2. 视图切换动画 ----
{
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#dashboard-view:not([hidden])", { timeout: 15000 });
  await waitAppReady(page);
  // 隐藏产品引导（会拦截点击）
  await page.evaluate(() => { const t = document.querySelector("#product-tour"); if (t) t.hidden = true; });
  // 切到 outline（通过导航点击，setView 是模块作用域不暴露在 window）
  await page.click('.nav-item[data-view="outline"]');
  const anim = await page.evaluate(() => {
    const el = document.querySelector("#outline-view");
    const cs = getComputedStyle(el);
    return { name: cs.animationName, dur: cs.animationDuration };
  });
  ok("视图切换动画", anim.name === "view-in", `animation=${anim.name} ${anim.dur}`);
  // 等动画结束后确认可见
  await page.waitForTimeout(400);
  const visible = await page.evaluate(() => !document.querySelector("#outline-view").hidden);
  ok("视图切换后可见", visible);
  await page.evaluate(() => { const t = document.querySelector("#product-tour"); if (t) t.hidden = true; });
  // 切回 dashboard 再确认
  await page.click('.nav-item[data-view="dashboard"]');
  const anim2 = await page.evaluate(() => {
    const el = document.querySelector("#dashboard-view");
    return getComputedStyle(el).animationName;
  });
  ok("返回 dashboard 动画", anim2 === "view-in", `animation=${anim2}`);
  await page.close();
}

// ---- 3. dialog 打开动画 ----
{
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#dashboard-view:not([hidden])", { timeout: 15000 });
  await waitAppReady(page);
  // backdrop 是 top-layer 元素，动画事件不冒泡到 document；
  // 用 document.getAnimations() 枚举所有动画（含 backdrop 伪元素动画）
  const backdropAnim = await page.evaluate(async () => {
    const d = document.querySelector("#write-dialog");
    const found = [];
    const observer = () => {
      for (const a of document.getAnimations()) {
        if (a.animationName && !found.includes(a.animationName)) found.push(a.animationName);
      }
    };
    const timer = setInterval(observer, 30);
    if (typeof d.showModal === "function") d.showModal();
    await new Promise((r) => setTimeout(r, 400));
    clearInterval(timer);
    return found;
  });
  ok("backdrop 淡入动画", backdropAnim.includes("dialog-backdrop-in"), `animations=${JSON.stringify(backdropAnim)}`);
  const dAnim = await page.evaluate(() => {
    const d = document.querySelector("#write-dialog");
    const cs = getComputedStyle(d);
    return { dialog: cs.animationName, dur: cs.animationDuration };
  });
  ok("dialog 打开动画", dAnim.dialog === "dialog-in", `animation=${dAnim.dialog} ${dAnim.dur}`);
  await page.close();
}

// ---- 4. 截图留档（深色 outline 视图）----
{
  const ctx = await browser.newContext();
  await ctx.addInitScript(() => {
    try { localStorage.setItem("writer-theme", "dark"); } catch (_) {}
  });
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#dashboard-view:not([hidden])", { timeout: 15000 });
  await waitAppReady(page);
  await page.evaluate(() => { const t = document.querySelector("#product-tour"); if (t) t.hidden = true; });
  await page.click('.nav-item[data-view="outline"]');
  await page.waitForTimeout(500);
  await page.screenshot({ path: process.argv[2] || "studio-outline-dark.png", fullPage: false });
  await ctx.close();
}

await browser.close();
console.log(results.join("\n"));
const fails = results.filter((r) => r.startsWith("FAIL")).length;
process.exit(fails ? 1 : 0);
