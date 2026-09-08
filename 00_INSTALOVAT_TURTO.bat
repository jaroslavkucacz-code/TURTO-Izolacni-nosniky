@echo off
chcp 65001 >nul
setlocal
title TURTO - historicky prevod v0.4.0 / v0.5.0 na 0.5.1
cd /d "%~dp0"

echo TURTO - historicky prevod na GitHub zaklad 0.5.1
echo Pro soucasne instalace TURTO 2.x tento nastroj nepouzivejte.
echo.

set "SCRIPT=%~dp0legacy\migration_v051\AKTUALIZOVAT_Z_V040.py"
if not exist "%SCRIPT%" (
    echo CHYBA: Chybi historicky migracni modul:
    echo %SCRIPT%
    pause
    exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%SCRIPT%"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python "%SCRIPT%"
    ) else (
        echo CHYBA: Python nebyl nalezen.
        pause
        exit /b 1
    )
)
endlocal
