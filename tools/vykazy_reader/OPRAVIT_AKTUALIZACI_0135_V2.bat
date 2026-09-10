@echo off
chcp 65001 >nul
setlocal
set "PATCH=%TEMP%\turto_vykazy_update_0135_v2_%RANDOM%.py"
set "URL=https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/8b51352ce6589e77ebe04d83d2857a1374fac717/tools/vykazy_reader/updates/0.13.5/update_0_13_3_to_0_13_5_exact.py"
set "SHA=4f32c2f8024b80b7214d3d3fb1e8c75cd93c71c1baa1d77bd8b137037810052d"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Headers @{'Cache-Control'='no-cache';'Pragma'='no-cache'} '%URL%?v=2' -OutFile '%PATCH%'; if ((Get-FileHash -Algorithm SHA256 '%PATCH%').Hash.ToLower() -ne '%SHA%') { exit 9 }"
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
