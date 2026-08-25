@echo off
setlocal
cd /d "%~dp0\.."

echo ============================================
echo   Dashboard Gerencial de Metas - Instalacao
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no PATH.
    echo Instale o Python 3.11 ou superior em https://www.python.org/downloads/
    echo e marque a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Criando ambiente virtual em .venv ...
    python -m venv .venv
)

echo Ativando ambiente virtual...
call .venv\Scripts\activate.bat

echo Atualizando pip...
python -m pip install --upgrade pip >nul

echo Instalando dependencias do requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias. Verifique sua conexao com a internet.
    pause
    exit /b 1
)

if not exist ".env" (
    echo Criando arquivo .env a partir de .env.example ...
    copy ".env.example" ".env" >nul
    echo.
    echo [ATENCAO] Abra o arquivo .env e configure a senha do SQL Server
    echo antes de iniciar o sistema.
)

echo.
echo ============================================
echo   Instalacao concluida com sucesso!
echo   Use o arquivo iniciar.bat para executar o sistema.
echo ============================================
pause
