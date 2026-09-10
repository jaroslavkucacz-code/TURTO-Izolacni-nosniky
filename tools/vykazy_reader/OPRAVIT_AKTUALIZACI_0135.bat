@echo off
chcp 65001 >nul
setlocal
set "PATCH=%TEMP%\turto_vykazy_update_0135_%RANDOM%.py"
set "URL=https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/e66674e774111a6a1623f050748c6eed3809be0e/tools/vykazy_reader/updates/0.13.5/update_0_13_3_to_0_13_5.py"
set "SHA=e7090305ea2591705177a6aa7f3514cd76b2368f2426a14e4284434a68b2981e"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Headers @{'Cache-Control'='no-cache';'Pragma'='no-cache'} '%URL%' -OutFile '%PATCH%'; if ((Get-FileHash -Algorithm SHA256 '%PATCH%').Hash.ToLower() -ne '%SHA%') { exit 9 }"
if errorlevel 1 (
  echo.
  echo Aktualizacni soubor se nepodarilo stahnout nebo overit.
  pause
  exit /b 1
)

where pyw >nul 2>&1
if not errorlevel 1 (
  start "" /wait pyw "%PATCH%"
  set "RC=%ERRORLEVEL%"
  del "%PATCH%" >nul 2>&1
  exit /b %RC%
)
where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" /wait pythonw "%PATCH%"
  set "RC=%ERRORLEVEL%"
  del "%PATCH%" >nul 2>&1
  exit /b %RC%
)
where py >nul 2>&1
if not errorlevel 1 (
  py "%PATCH%"
  set "RC=%ERRORLEVEL%"
  del "%PATCH%" >nul 2>&1
  exit /b %RC%
)
where python >nul 2>&1
if not errorlevel 1 (
  python "%PATCH%"
  set "RC=%ERRORLEVEL%"
  del "%PATCH%" >nul 2>&1
  exit /b %RC%
)

echo.
echo Python nebyl nalezen.
pause
exit /b 1
