@echo off
title Futures Cereali - Avvio Locale Web App PWA
chcp 65001 > nul

echo ===============================================================
echo   FUTURES CEREALI (GRANO DURO + TENERO PDT / PMG)
echo   Avvio Web App PWA con Sincronizzazione Intelligente
echo ===============================================================
echo.

cd /d "%~dp0"

:: Cerca Python per l'esecuzione
set "PY_CMD=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    )
)

set PORT=8088

:: Fase 1: Verifica preliminare e allineamento quotazioni odierne
%PY_CMD% execution\boot_sync.py

echo.
echo [INFO] Avvio Micro Web Server locale sulla porta %PORT%...
echo [INFO] Apertura automatica del browser all'indirizzo: http://localhost:%PORT%
echo.
echo NOTA: Per arrestare il server, chiudi questa finestra.
echo ===============================================================
echo.

:: Fase 2: Apertura automatica del browser predefinito
start http://localhost:%PORT%

:: Fase 3: Avvio server con API di sincronizzazione live (/api/sync)
%PY_CMD% local_server.py %PORT%

pause
