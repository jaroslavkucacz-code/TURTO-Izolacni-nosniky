@echo off
chcp 65001 >nul
setlocal
title TURTO - nouzova oprava spusteni

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0OPRAVIT_TURTO.ps1" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo Oprava TURTO skoncila chybou. Kod: %RC%
    echo Podrobnosti jsou zobrazeny v dialogu a pripadne v Logy\recovery.log.
    pause
)

exit /b %RC%
