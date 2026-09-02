@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo TURTO - instalace
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py INSTALL_TURTO.py
  goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
  python INSTALL_TURTO.py
  goto :eof
)
echo CHYBA: Nebyl nalezen Python.
echo Nainstalujte 64bitovy Python pro Windows a zkuste instalaci znovu.
pause
