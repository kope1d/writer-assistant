@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "%~dp0desktop\node_modules\electron\dist\electron.exe" (
  echo [Writer Assistant] 未找到 Electron 桌面客户端。
  echo 请先进入 desktop 目录运行：npm install
  pause
  exit /b 1
)

start "" "%~dp0desktop\node_modules\electron\dist\electron.exe" "%~dp0desktop"
exit /b 0
