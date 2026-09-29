@echo off
title App Futures Cereali - Grano Duro e Tenero
chcp 65001 > nul

echo ===============================================================
echo   QUOTAZIONI FUTURES CEREALI (DURO PDT + TENERO PDT / PMG)
echo   Avvio Applicazione Streamlit Mobile-First...
echo ===============================================================
echo.

cd /d "%~dp0"

:: Verifica ambiente python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRORE] Python non e' stato trovato nel PATH di sistema!
    echo Installa Python o verifica che sia presente nelle variabili d'ambiente.
    echo.
    pause
    exit /b 1
)

:: Chiusura di eventuali istanze rimaste aperte sulla porta 8503
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8503 ^| findstr LISTENING 2^>nul') do (
    taskkill /f /pid %%p >nul 2>&1
)

echo Avvio del server Streamlit in corso...
echo Apertura automatica di una scheda del browser all'indirizzo http://localhost:8503...
echo.
echo NOTA: Mantieni aperta questa finestra mentre consulti l'applicazione.
echo Per arrestarla, chiudi questa finestra.
echo ===============================================================
echo.

:: Avvio di Streamlit (gestisce autonomamente l'apertura di un'unica scheda nel browser)
python -m streamlit run app.py --server.port=8503

if %errorlevel% neq 0 (
    echo.
    echo [ERRORE] Si e' verificato un problema durante l'esecuzione dell'app.
    echo.
    pause
)
