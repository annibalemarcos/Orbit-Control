@echo off
setlocal
cd /d "%~dp0"
title Orbit Control

if not exist ".venv\Scripts\pythonw.exe" (
    call INSTALAR_E_ABRIR.bat
    exit /b %errorlevel%
)

start "Orbit Control" ".venv\Scripts\pythonw.exe" app.py
endlocal
