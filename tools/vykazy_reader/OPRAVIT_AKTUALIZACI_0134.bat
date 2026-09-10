@echo off
chcp 65001 >nul
setlocal
set "RECOVERY=%TEMP%\turto_vykazy_recovery_0134_%RANDOM%.py"
set "URL=https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/45a49882c8eb1b5fe95255bf89b444b839fccb1a/tools/vykazy_reader/recovery/recovery_0134.py"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Headers @{'Cache-Control'='no-cache';'Pragma'='no-cache'} '%URL%' -OutFile '%RECOVERY%'"
if errorlevel 1 (
  echo.
  echo Opravny online aktualizator se nepodarilo stahnout.
  pause
  exit /b 1
)

where pyw >nul 2>&1
if not errorlevel 1 (
  start "" /wait pyw "%RECOVERY%"
  del "%RECOVERY%" >nul 2>&1
  exit /b 0
)
where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" /wait pythonw "%RECOVERY%"
  del "%RECOVERY%" >nul 2>&1
  exit /b 0
)
where py >nul 2>&1
if not errorlevel 1 (
  py "%RECOVERY%"
  set "RC=%ERRORLEVEL%"
  del "%RECOVERY%" >nul 2>&1
  exit /b %RC%
)
where python >nul 2>&1
if not errorlevel 1 (
  python "%RECOVERY%"
  set "RC=%ERRORLEVEL%"
  del "%RECOVERY%" >nul 2>&1
  exit /b %RC%
)

echo.
echo Python nebyl nalezen.
pause
exit /b 1
