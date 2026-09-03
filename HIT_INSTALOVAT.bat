@echo off
chcp 65001 >nul
setlocal
set "TARGET=%LOCALAPPDATA%\TURTO\HIT"
if not exist "%TARGET%" mkdir "%TARGET%"

echo TURTO HIT - instalace v0.1.0
echo Cil: %TARGET%
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo Chybi Python launcher "py". Nejprve nainstalujte 64bitovy Python pro Windows.
  pause
  exit /b 1
)

echo Kontroluji knihovnu pdfplumber...
py -m pip install "pdfplumber>=0.11" >nul
if errorlevel 1 (
  echo Nepodarilo se pripravit pdfplumber.
  pause
  exit /b 1
)

echo Stahuji program...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest 'https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/hit/hit_design.pyw' -OutFile '%TARGET%\hit_design.pyw'"
if errorlevel 1 (
  echo Stazeni programu se nezdarilo.
  pause
  exit /b 1
)

>"%TARGET%\Spustit_TURTO_HIT.vbs" echo Set sh = CreateObject("WScript.Shell")
>>"%TARGET%\Spustit_TURTO_HIT.vbs" echo sh.Run "pyw ""%TARGET%\hit_design.pyw""", 0, False

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\TURTO HIT.lnk'); $sc.TargetPath='wscript.exe'; $sc.Arguments='""%TARGET%\Spustit_TURTO_HIT.vbs""'; $sc.WorkingDirectory='%TARGET%'; $sc.Save()"

echo.
echo HOTOVO. Pri prvnim spusteni vyberte soubor CONF-DOP_HIT-HP_SP_07-23-E.pdf.
start "" wscript "%TARGET%\Spustit_TURTO_HIT.vbs"
endlocal
