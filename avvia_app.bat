@echo off
title Futures Cereali - App PWA
chcp 65001 > nul

echo ===============================================================
echo   FUTURES CEREALI (GRANO DURO + TENERO PDT / PMG)
echo   Avvio Web App PWA Ultra-Veloce
echo ===============================================================
echo.

cd /d "%~dp0"

:: Cerca Python per avviare il micro-server HTTP locale
set "PY_CMD=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    )
)

set PORT=8088

echo [INFO] Avvio Web Server locale sulla porta %PORT%...
echo [INFO] Apertura automatica del browser all'indirizzo: http://localhost:%PORT%
echo.
echo NOTA: Per arrestare il server, chiudi questa finestra.
echo ===============================================================
echo.

start http://localhost:%PORT%
%PY_CMD% -m http.server %PORT%

pause
