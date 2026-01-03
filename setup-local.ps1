# Script de Setup Local para Chat Marketplace Backend
# Execute este script no PowerShell como Administrador (se necessário)

Write-Host "=== Setup Local - Chat Marketplace Backend ===" -ForegroundColor Cyan
Write-Host ""

# Verificar se Python está instalado
Write-Host "1. Verificando instalação do Python..." -ForegroundColor Yellow
$pythonPath = Get-Command python -ErrorAction SilentlyContinue
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue

if (-not $pythonPath -and -not $pyLauncher) {
    Write-Host "   ❌ Python não encontrado!" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Opções para instalar Python:" -ForegroundColor Yellow
    Write-Host "   1. Baixar do site oficial: https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "   2. Instalar via Microsoft Store (recomendado):" -ForegroundColor White
    Write-Host "      - Abra a Microsoft Store" -ForegroundColor White
    Write-Host "      - Procure por 'Python 3.13' ou 'Python 3.12'" -ForegroundColor White
    Write-Host "      - Instale e reinicie o terminal" -ForegroundColor White
    Write-Host ""
    Write-Host "   ⚠️  IMPORTANTE: Marque 'Add Python to PATH' durante a instalação!" -ForegroundColor Red
    Write-Host ""
    Read-Host "   Pressione Enter após instalar o Python para continuar..."
    
    # Verificar novamente
    $pythonPath = Get-Command python -ErrorAction SilentlyContinue
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    
    if (-not $pythonPath -and -not $pyLauncher) {
        Write-Host "   ❌ Python ainda não encontrado. Por favor, instale e tente novamente." -ForegroundColor Red
        exit 1
    }
}

# Determinar comando Python
if ($pythonPath) {
    $pythonCmd = "python"
    $pythonVersion = & python --version 2>&1
} elseif ($pyLauncher) {
    $pythonCmd = "py"
    $pythonVersion = & py --version 2>&1
}

Write-Host "   ✅ Python encontrado: $pythonVersion" -ForegroundColor Green
Write-Host ""

# Verificar se pip está disponível
Write-Host "2. Verificando pip..." -ForegroundColor Yellow
$pipCheck = & $pythonCmd -m pip --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ pip disponível: $pipCheck" -ForegroundColor Green
} else {
    Write-Host "   ❌ pip não encontrado. Instalando pip..." -ForegroundColor Yellow
    & $pythonCmd -m ensurepip --upgrade
}
Write-Host ""

# Criar ambiente virtual
Write-Host "3. Criando ambiente virtual..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "   ⚠️  Ambiente virtual já existe. Removendo..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force venv
}

& $pythonCmd -m venv venv
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Ambiente virtual criado" -ForegroundColor Green
} else {
    Write-Host "   ❌ Erro ao criar ambiente virtual" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Ativar ambiente virtual
Write-Host "4. Ativando ambiente virtual..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Ambiente virtual ativado" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Erro ao ativar. Tente executar manualmente:" -ForegroundColor Yellow
    Write-Host "      .\venv\Scripts\Activate.ps1" -ForegroundColor White
}
Write-Host ""

# Atualizar pip
Write-Host "5. Atualizando pip..." -ForegroundColor Yellow
& python -m pip install --upgrade pip
Write-Host "   ✅ pip atualizado" -ForegroundColor Green
Write-Host ""

# Instalar dependências
Write-Host "6. Instalando dependências..." -ForegroundColor Yellow
& python -m pip install -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Dependências instaladas" -ForegroundColor Green
} else {
    Write-Host "   ❌ Erro ao instalar dependências" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Verificar arquivo .env
Write-Host "7. Verificando configuração (.env)..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "   ⚠️  Arquivo .env não encontrado!" -ForegroundColor Yellow
    Write-Host "   Criando arquivo .env de exemplo..." -ForegroundColor Yellow
    
    $envContent = @"
# Configurações do Google Cloud
GOOGLE_CLOUD_PROJECT_ID=seu-project-id
DIALOGFLOW_AGENT_ID=seu-agent-id
DIALOGFLOW_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json

# Configurações do Servidor
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Configurações de Áudio
SAMPLE_RATE=16000
CHANNELS=1
CHUNK_SIZE=4096
VAD_AGGRESSIVENESS=2

# Configurações do Dialogflow
DIALOGFLOW_LANGUAGE_CODE=pt-BR
DIALOGFLOW_ENABLE_AUTO_SENTIMENT=true
"@
    
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "   ✅ Arquivo .env criado. Por favor, configure as variáveis!" -ForegroundColor Green
} else {
    Write-Host "   ✅ Arquivo .env encontrado" -ForegroundColor Green
}
Write-Host ""

# Resumo
Write-Host "=== Setup Concluído! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Yellow
Write-Host "1. Configure o arquivo .env com suas credenciais" -ForegroundColor White
Write-Host "2. Execute o servidor com: python run.py" -ForegroundColor White
Write-Host "   ou: uvicorn main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "Para ativar o ambiente virtual novamente:" -ForegroundColor Yellow
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""

