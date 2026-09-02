@echo off
chcp 65001 >nul
title TURTO - instalace
cd /d "%~dp0"
echo TURTO - instalace
echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 INSTALL_TURTO_FIXED.py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python INSTALL_TURTO_FIXED.py
    ) else (
        echo CHYBA: Python nebyl nalezen.
        echo Nainstalujte 64bitovy Python pro Windows a zkuste instalaci znovu.
        pause
        exit /b 1
    )
)
