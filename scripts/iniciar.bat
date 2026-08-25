@echo off
setlocal
cd /d "%~dp0\.."

title Dashboard Gerencial de Metas

if not exist ".venv" (
    echo Ambiente virtual nao encontrado. Executando instalacao...
    call scripts\instalar.bat
)

if not exist ".env" (
    echo [ERRO] Arquivo .env nao encontrado. Copie .env.example para .env
    echo e configure os dados de conexao com o SQL Server antes de continuar.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo ============================================
echo   Iniciando Dashboard Gerencial de Metas...
echo   O navegador sera aberto automaticamente.
echo   (Se a porta padrao 5000 ja estiver em uso por
echo   outro sistema nesta maquina, o proximo endereco
echo   disponivel sera usado - veja abaixo qual foi.)
echo   Para encerrar, feche esta janela ou pressione Ctrl+C.
echo ============================================
echo.

python app.py

pause
