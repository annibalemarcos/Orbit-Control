@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Orbit Control - Instalacao

call :find_python
if errorlevel 1 exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :fail
)

echo Instalando os componentes do Orbit Control...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Instalacao concluida. Abrindo o aplicativo desktop...
start "Orbit Control" ".venv\Scripts\pythonw.exe" app.py
exit /b 0

:find_python
where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    exit /b 0
)
where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)
echo.
echo [ERRO] Python 3.10 ou mais recente nao foi encontrado.
echo Baixe em https://www.python.org/downloads/
pause
exit /b 1

:fail
echo.
echo [ERRO] A instalacao nao foi concluida.
pause
exit /b 1
