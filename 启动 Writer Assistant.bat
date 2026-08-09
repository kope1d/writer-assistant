@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Electron desktop client takes priority; no Python probing needed here
if exist "%~dp0desktop\node_modules\electron\dist\electron.exe" (
  start "" "%~dp0desktop\node_modules\electron\dist\electron.exe" "%~dp0desktop"
  exit /b 0
)

rem Fallback: built-in desktop window (silent Python probing)
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

echo [Writer Assistant] Python 3.10+ was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo and tick "Add Python to PATH", then run this file again.
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
  echo Launch failed.
  pause
)
exit /b %WA_STATUS%
