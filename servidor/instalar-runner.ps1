# Instala o GitHub Actions runner neste servidor, como serviço do Windows na conta SYSTEM.
# Com ele, cada push na main do GitHub publica o sistema aqui sozinho
# (.github\workflows\deploy-servidor.yml). O runner só faz conexões de saída para o GitHub:
# nenhuma porta precisa ser aberta.
#
# Antes de rodar, pegue o token em:
#   GitHub > repositório > Settings > Actions > Runners > New self-hosted runner (Windows)
#   copie o valor que aparece depois de "--token" (vale por 1 hora).
#
# Pode ser rodado de novo: substitui o runner anterior com o mesmo nome.

param([string]$Token)

$ErrorActionPreference = "Stop"

$REPO_URL     = "https://github.com/andre-jnr/metas-frigoam"
$PASTA_RUNNER = "C:\actions-runner\metas"
$ROTULO       = "servidor-metas"   # o workflow roda só em runners com este rótulo
$NOME         = "$env:COMPUTERNAME-metas"

function Passo($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "    OK  $msg" -ForegroundColor Green }
function Falha($msg) { Write-Host "`nERRO: $msg" -ForegroundColor Red; exit 1 }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Falha "rode como Administrador (clique com o botão direito em instalar-runner.bat > Executar como administrador)." }

if (-not $Token) {
    Write-Host "Cole o token do runner (GitHub > Settings > Actions > Runners > New self-hosted runner):"
    $Token = (Read-Host "Token").Trim()
}
if (-not $Token) { Falha "sem token não dá para registrar o runner." }

Passo "Preparando a pasta $PASTA_RUNNER"
New-Item -ItemType Directory -Force $PASTA_RUNNER | Out-Null
Set-Location $PASTA_RUNNER

if (Test-Path ".\.runner") {
    # Reinstalação: apaga o serviço e o registro local; o --replace abaixo substitui o
    # runner de mesmo nome no GitHub (o "config.cmd remove" exigiria outro tipo de token)
    Passo "Removendo a instalação anterior deste runner"
    Get-Service "actions.runner.*" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*$NOME*" } |
        ForEach-Object {
            Stop-Service $_.Name -Force -ErrorAction SilentlyContinue
            sc.exe delete $_.Name | Out-Null
        }
    Remove-Item ".runner", ".credentials", ".credentials_rsaparams", ".service" -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path ".\config.cmd")) {
    Passo "Baixando o GitHub Actions runner (versão mais recente)"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $release = Invoke-RestMethod "https://api.github.com/repos/actions/runner/releases/latest" `
        -Headers @{ "User-Agent" = "instalar-runner" }
    $pacote = $release.assets | Where-Object { $_.name -like "actions-runner-win-x64-*.zip" } | Select-Object -First 1
    if (-not $pacote) { Falha "não achei o pacote do runner para Windows na versão $($release.tag_name)." }
    $zip = Join-Path $env:TEMP $pacote.name
    Invoke-WebRequest $pacote.browser_download_url -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath $PASTA_RUNNER -Force
    Remove-Item $zip -Force
    Ok "runner $($release.tag_name)"
}

Passo "Registrando no GitHub e instalando como serviço"
# Conta SYSTEM: o deploy precisa de administrador para parar/reiniciar a tarefa agendada do sistema
& .\config.cmd --unattended --url $REPO_URL --token $Token --name $NOME --labels $ROTULO `
    --work "_work" --replace --runasservice --windowslogonaccount "NT AUTHORITY\SYSTEM"
if ($LASTEXITCODE -ne 0) { Falha "o registro falhou. O token vale só 1 hora: gere outro e rode de novo." }

$servico = Get-Service "actions.runner.*" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*$NOME*" }
if (-not $servico -or $servico.Status -ne "Running") { Falha "o serviço do runner não está rodando. Confira em services.msc." }
Ok "serviço '$($servico.Name)' rodando (inicia sozinho com o Windows)"

Write-Host "`nPronto! Falta só uma configuração no GitHub:" -ForegroundColor Green
Write-Host "  Settings > Secrets and variables > Actions > Variables > New repository variable"
Write-Host "  Nome: PASTA_SISTEMA   Valor: a pasta do sistema neste servidor (ex.: $((Resolve-Path "$PSScriptRoot\..").Path))"
Write-Host "Depois disso, cada push na main publica aqui sozinho. Acompanhe em GitHub > Actions."
