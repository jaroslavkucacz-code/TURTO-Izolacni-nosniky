@echo off
chcp 65001 >nul
setlocal
set "BOOTSTRAP=%TEMP%\turto_vykazy_online_update_%RANDOM%.py"
set "URL=https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/tools/vykazy_reader/bootstrap.py"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing '%URL%' -OutFile '%BOOTSTRAP%'"
if errorlevel 1 (
  echo.
  echo Online aktualizator se nepodarilo stahnout.
  pause
  exit /b 1
)

where pyw >nul 2>&1
if not errorlevel 1 (
  start "" /wait pyw "%BOOTSTRAP%" "%~dp0"
  del "%BOOTSTRAP%" >nul 2>&1
  exit /b 0
)
where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" /wait pythonw "%BOOTSTRAP%" "%~dp0"
  del "%BOOTSTRAP%" >nul 2>&1
  exit /b 0
)
where py >nul 2>&1
if not errorlevel 1 (
  py "%BOOTSTRAP%" "%~dp0"
  set "RC=%ERRORLEVEL%"
  del "%BOOTSTRAP%" >nul 2>&1
  exit /b %RC%
)
where python >nul 2>&1
if not errorlevel 1 (
  python "%BOOTSTRAP%" "%~dp0"
  set "RC=%ERRORLEVEL%"
  del "%BOOTSTRAP%" >nul 2>&1
  exit /b %RC%
)

echo.
echo Python nebyl nalezen.
pause
exit /b 1
