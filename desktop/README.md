# Writer Assistant 桌面客户端

基于 Electron 的独立桌面窗口。启动时会自动拉起本仓库的 Python 引擎，
然后在原生应用窗口中打开 Writer Assistant 工作台。

## 运行

```bash
npm install
npm start
```

Windows 下也可以直接双击仓库根目录的 `启动 Writer Assistant.bat`，
检测到桌面客户端后会自动优先使用它。

## 说明

- 引擎端口默认 `4567`，仅绑定本机回环地址。
- 关闭窗口后，Electron 会自动结束它启动的 Python 引擎进程。

## 打包与发布

```bash
# 1) 先用 PyInstaller 打包 Python 引擎（见 packaging/README.md）
# 2) 构建 Windows 安装包
npm run dist
# 3) 发布到 GitHub Releases（自动更新渠道）
gh release create v0.1.0 \
  "release/Writer Assistant Setup 0.1.0.exe" \
  "release/latest.yml" \
  --title "Writer Assistant 0.1.0"
```
