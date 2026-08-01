@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Orbit Control - Gerar EXE

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python 3.10 ou mais recente nao foi encontrado.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

if not exist ".build-venv\Scripts\python.exe" (
    echo Criando ambiente de compilacao...
    %PYTHON_CMD% -m venv .build-venv
    if errorlevel 1 goto :fail
)

echo Instalando o empacotador e as dependencias...
".build-venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".build-venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :fail

echo Gerando OrbitControl.exe...
".build-venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm OrbitControl.spec
if errorlevel 1 goto :fail

echo.
echo PRONTO: dist\OrbitControl.exe
start "" "%~dp0dist"
pause
exit /b 0

:fail
echo.
echo [ERRO] O executavel nao foi gerado. Veja as mensagens acima.
pause
exit /b 1
