@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem Electron 桌面客户端优先：无需本地 Python 探测
if exist "%~dp0desktop\node_modules\electron\dist\electron.exe" (
  start "" "%~dp0desktop\node_modules\electron\dist\electron.exe" "%~dp0desktop"
  exit /b 0
)

rem 回退：内置桌面窗口（Python 探测全程静默）
set "WA_PYTHON="
set "WA_PY_VERSION="

if exist "%~dp0.venv\Scripts\python.exe" call :try_exe "%~dp0.venv\Scripts\python.exe"
if defined WA_PYTHON goto :launch
if exist "%~dp0.venv312\Scripts\python.exe" call :try_exe "%~dp0.venv312\Scripts\python.exe"
if defined WA_PYTHON goto :launch
if exist "%~dp0..\..\Scripts\python.exe" call :try_exe "%~dp0..\..\Scripts\python.exe"
if defined WA_PYTHON goto :launch
if exist "%~dp0Scripts\python.exe" call :try_exe "%~dp0Scripts\python.exe"
if defined WA_PYTHON goto :launch

where python >nul 2>nul
if not errorlevel 1 call :try_exe python
if defined WA_PYTHON goto :launch

where py >nul 2>nul
if not errorlevel 1 (
  for %%V in (-3.13 -3.12 -3.11 -3.10) do (
    if not defined WA_PYTHON call :try_py %%V
  )
)
if defined WA_PYTHON goto :launch

echo [Writer Assistant] 未找到 Python 3.10 或更高版本。
echo 请先从 https://www.python.org/downloads/windows/ 安装 Python，
echo 安装时勾选 "Add Python to PATH"，然后再次双击此文件。
echo.
pause
exit /b 2

:try_exe
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "WA_PYTHON=%~1"
exit /b 0

:try_py
py %1 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "WA_PYTHON=py"
  set "WA_PY_VERSION=%1"
)
exit /b 0

:launch
if "%WA_PYTHON%"=="py" (
  if exist "%~dp0tools\desktop_launcher.py" (
    py %WA_PY_VERSION% -u "%~dp0tools\desktop_launcher.py" --desktop %*
  ) else (
    py %WA_PY_VERSION% -u -m tools.desktop_launcher --desktop %*
  )
) else (
  if exist "%~dp0tools\desktop_launcher.py" (
    "%WA_PYTHON%" -u "%~dp0tools\desktop_launcher.py" --desktop %*
  ) else (
    "%WA_PYTHON%" -u -m tools.desktop_launcher --desktop %*
  )
)
set "WA_STATUS=%ERRORLEVEL%"
if not "%WA_STATUS%"=="0" (
  echo.
  echo 启动未完成。
  pause
)
exit /b %WA_STATUS%
