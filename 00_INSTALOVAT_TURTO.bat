@echo off
chcp 65001 >nul
title TURTO - prevod existujici verze na GitHub aktualizace
cd /d "%~dp0"
echo TURTO - prevod existujici verze v0.4.0 / v0.5.0 na GitHub verzi v0.5.1
echo Tento prevod nestahuje zadne casti programu z internetu.
echo Zachova vase katalogova data a vytvori zalohu menenych souboru.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 AKTUALIZOVAT_Z_V040.py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python AKTUALIZOVAT_Z_V040.py
    ) else (
        echo CHYBA: Python nebyl nalezen.
        echo Nainstalujte 64bitovy Python pro Windows a zkuste prevod znovu.
        pause
        exit /b 1
    )
)
