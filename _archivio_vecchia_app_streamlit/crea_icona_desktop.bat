@echo off
title Creazione Icona Ufficiale Desktop - Futures Cereali
chcp 65001 > nul

echo ===============================================================
echo   CREAZIONE ICONA UFFICIALE SU DESKTOP WINDOWS
echo   Futures Grano - Quotazioni Giornaliere
echo ===============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crea_shortcut.ps1"

echo.
echo Operazione completata.
pause
