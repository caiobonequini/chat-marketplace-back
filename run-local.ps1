# Script para executar o servidor localmente
# Execute este script após o setup

Write-Host "=== Iniciando Chat Marketplace Backend ===" -ForegroundColor Cyan
Write-Host ""

# Verificar se ambiente virtual existe
if (-not (Test-Path "venv")) {
    Write-Host "❌ Ambiente virtual não encontrado!" -ForegroundColor Red
    Write-Host "Execute primeiro: .\setup-local.ps1" -ForegroundColor Yellow
    exit 1
}

# Ativar ambiente virtual
Write-Host "Ativando ambiente virtual..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Verificar se .env existe
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  Arquivo .env não encontrado!" -ForegroundColor Yellow
    Write-Host "Criando .env de exemplo..." -ForegroundColor Yellow
    # O setup-local.ps1 já cria o .env, mas vamos garantir
}

# Executar servidor
Write-Host "Iniciando servidor..." -ForegroundColor Yellow
Write-Host ""
python run.py

