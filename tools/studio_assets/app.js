// 主题在首帧绘制前同步应用：ES module（defer）执行先于浏览器首次绘制，
// 这里设置 data-theme 可避免深色用户刷新时闪现浅色。
// CSP default-src 'self' 禁止内联脚本，只能在模块顶层用原生 localStorage；
// start() 里的 applyTheme 会再执行一遍（幂等）。
try {
  const stored = localStorage.getItem("writer-theme");
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = stored || (systemDark ? "dark" : "light");
} catch (_) {
  document.documentElement.dataset.theme = "light";
}

import "/js/application.js?v=startup-recovery-1";
