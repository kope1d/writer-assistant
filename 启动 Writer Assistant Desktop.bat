@echo off
cd /d "%~dp0"

if not exist "%~dp0desktop\node_modules\electron\dist\electron.exe" (
  echo [Writer Assistant] Electron client not found.
  echo Run "npm install" inside the desktop folder first.
  pause
  exit /b 1
)

start "" "%~dp0desktop\node_modules\electron\dist\electron.exe" "%~dp0desktop"
exit /b 0
