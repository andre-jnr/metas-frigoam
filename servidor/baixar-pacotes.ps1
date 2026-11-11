# Baixa os pacotes Python do sistema (requirements.txt) para a pasta servidor\pacotes.
#
# Use quando a internet do servidor falha no meio da instalação ("IncompleteRead",
# "Connection broken", "timed out"): rode este script num computador com boa internet,
# copie a pasta servidor\pacotes para a mesma pasta no servidor e rode o instalar.bat lá.
# O instalador encontra a pasta e instala sem baixar nada.
#
# Os pacotes precisam ser da mesma versão do Python do servidor. Para descobrir, rode no
# servidor:  py -3 --version   (ou  python --version)

param([string]$VersaoPython)

$ErrorActionPreference = "Stop"
$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$destino = Join-Path $PSScriptRoot "pacotes"

function Passo($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "    OK  $msg" -ForegroundColor Green }
function Falha($msg) { Write-Host "`nERRO: $msg" -ForegroundColor Red; exit 1 }

if (-not $VersaoPython) {
    Write-Host "Qual a versão do Python do SERVIDOR? (no servidor: py -3 --version). Ex.: 3.13"
    $VersaoPython = (Read-Host "Versão").Trim()
}
# aceita "3.13", "3.13.2" ou "Python 3.13.2": usa só os dois primeiros números
if ($VersaoPython -match "(\d+)\.(\d+)") { $VersaoPython = "$($Matches[1]).$($Matches[2])" }
else { Falha "versão '$VersaoPython' inválida. Use o formato 3.13." }

# qualquer Python deste computador serve para baixar (a versão alvo vai no --python-version)
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$extra = @()
if (-not (Test-Path $python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py"; $extra = @("-3") }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = "python" }
    else { Falha "nenhum Python encontrado neste computador para baixar os pacotes." }
}

Passo "Baixando os pacotes para Python $VersaoPython (Windows 64 bits)"
if (Test-Path $destino) { Get-ChildItem $destino -Filter "*.whl" | Remove-Item -Force }
New-Item -ItemType Directory -Force $destino | Out-Null
& $python @extra -m pip download --disable-pip-version-check --retries 10 --timeout 60 `
    --only-binary ":all:" --python-version $VersaoPython --platform win_amd64 `
    -r (Join-Path $raiz "requirements.txt") -d $destino
if ($LASTEXITCODE -ne 0) {
    Falha "o download falhou. Se for erro de conexão, tente de novo; se for 'No matching distribution', algum pacote não tem versão pronta para o Python $VersaoPython."
}

$arquivos = Get-ChildItem $destino -Filter "*.whl"
$tamanho = [math]::Round(($arquivos | Measure-Object Length -Sum).Sum / 1MB, 1)
Ok "$($arquivos.Count) pacotes ($tamanho MB) em $destino"
Write-Host "`nAgora copie a pasta servidor\pacotes para a pasta servidor\ do sistema no servidor" -ForegroundColor Green
Write-Host "e rode o servidor\instalar.bat de novo. A instalação não vai precisar de internet."
