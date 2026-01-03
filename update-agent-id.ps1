# Script para atualizar o Agent ID no .env
# Uso: .\update-agent-id.ps1 -AgentId "ee1f79d8-b348-4360-94b5-eb6308f7cef1"

param(
    [Parameter(Mandatory=$true)]
    [string]$AgentId
)

Write-Host "=== Atualizando Agent ID no .env ===" -ForegroundColor Cyan
Write-Host ""

# Verificar se .env existe
if (-not (Test-Path ".env")) {
    Write-Host "❌ Arquivo .env não encontrado!" -ForegroundColor Red
    Write-Host "Criando arquivo .env de exemplo..." -ForegroundColor Yellow
    
    $envContent = @"
# Configurações do Google Cloud
GOOGLE_CLOUD_PROJECT_ID=mv-ia-472317
DIALOGFLOW_AGENT_ID=$AgentId
DIALOGFLOW_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./credentials/mv-ia-472317-61f2d9bbfd9d.json

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
    Write-Host "✅ Arquivo .env criado com Agent ID: $AgentId" -ForegroundColor Green
    exit 0
}

# Ler conteúdo atual
$envContent = Get-Content ".env" -Raw

# Verificar se DIALOGFLOW_AGENT_ID já existe
if ($envContent -match "DIALOGFLOW_AGENT_ID\s*=\s*(.+)") {
    $oldAgentId = $matches[1].Trim()
    Write-Host "Agent ID atual: $oldAgentId" -ForegroundColor Yellow
    
    # Substituir
    $envContent = $envContent -replace "DIALOGFLOW_AGENT_ID\s*=\s*.+", "DIALOGFLOW_AGENT_ID=$AgentId"
    
    Write-Host "✅ Agent ID atualizado para: $AgentId" -ForegroundColor Green
} else {
    # Adicionar se não existir
    Write-Host "DIALOGFLOW_AGENT_ID não encontrado. Adicionando..." -ForegroundColor Yellow
    
    if ($envContent -match "GOOGLE_CLOUD_PROJECT_ID") {
        $envContent = $envContent -replace "(GOOGLE_CLOUD_PROJECT_ID\s*=\s*.+)", "`$1`r`nDIALOGFLOW_AGENT_ID=$AgentId"
    } else {
        $envContent = "DIALOGFLOW_AGENT_ID=$AgentId`r`n" + $envContent
    }
    
    Write-Host "✅ Agent ID adicionado: $AgentId" -ForegroundColor Green
}

# Salvar arquivo
$envContent | Out-File -FilePath ".env" -Encoding UTF8 -NoNewline

Write-Host ""
Write-Host "✅ Arquivo .env atualizado com sucesso!" -ForegroundColor Green
Write-Host ""
Write-Host "Próximo passo: Reinicie o servidor para aplicar as mudanças." -ForegroundColor Yellow
Write-Host "   .\run-local.ps1" -ForegroundColor White

