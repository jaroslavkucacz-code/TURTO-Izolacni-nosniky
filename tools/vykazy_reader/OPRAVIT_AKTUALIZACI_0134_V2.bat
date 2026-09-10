@echo off
chcp 65001 >nul
setlocal
set "RECOVERY=%TEMP%\turto_vykazy_recovery_0134_v2_%RANDOM%.py"
set "URL=https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/02e93cd626fec8f0104f411056da99909761e868/tools/vykazy_reader/recovery/recovery_0134_v2.py?cb=0134v2"

echo TURTO - oprava online aktualizace 0.13.4 v2
echo.
echo Stahuji opravny krok...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Headers @{'Cache-Control'='no-cache, no-store, max-age=0';'Pragma'='no-cache'} '%URL%' -OutFile '%RECOVERY%'"
if errorlevel 1 (
  echo.
  echo Opravny online aktualizator se nepodarilo stahnout.
  pause
  exit /b 1
)

where py >nul 2>&1
if not errorlevel 1 (
  py "%RECOVERY%"
  set "RC=%ERRORLEVEL%"
  del "%RECOVERY%" >nul 2>&1
  if not "%RC%"=="0" (
    echo.
    echo Oprava skoncila chybou. Pokud vznikl soubor TURTO_AKTUALIZACE_DIAGNOSTIKA.txt,
    echo poslete jej prosim do chatu.
    pause
  )
  exit /b %RC%
)

where python >nul 2>&1
if not errorlevel 1 (
  python "%RECOVERY%"
  set "RC=%ERRORLEVEL%"
  del "%RECOVERY%" >nul 2>&1
  if not "%RC%"=="0" (
    echo.
    echo Oprava skoncila chybou. Pokud vznikl soubor TURTO_AKTUALIZACE_DIAGNOSTIKA.txt,
    echo poslete jej prosim do chatu.
    pause
  )
  exit /b %RC%
)

echo.
echo Python nebyl nalezen.
pause
exit /b 1
