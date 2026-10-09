@echo off
title Futures Cereali - Avvio Locale Web App PWA
chcp 65001 > nul

echo ===============================================================
echo   FUTURES CEREALI (GRANO DURO + TENERO PDT / PMG)
echo   Avvio Web App PWA Ultra-Veloce (Zero Streamlit)
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

:: Trova una porta libera (8088 o 8080)
set PORT=8088

echo [INFO] Avvio Web Server locale sulla porta %PORT%...
echo [INFO] Apertura automatica del browser all'indirizzo: http://localhost:%PORT%
echo.
echo NOTA: Per arrestare il server, chiudi questa finestra.
echo ===============================================================
echo.

:: Avvia il browser predefinito
start http://localhost:%PORT%

:: Avvia micro-server Python
%PY_CMD% -m http.server %PORT%

pause
