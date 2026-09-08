@echo off
chcp 65001 >nul
setlocal
title TURTO - nouzova oprava spusteni 2.1.2

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0OPRAVIT_TURTO.ps1" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo Oprava TURTO skoncila chybou. Kod: %RC%
    echo Podrobnosti jsou zobrazeny v dialogu a pripadne v recovery_2_1_2.log.
    pause
)

exit /b %RC%
