# Guia de Configuração

## Pré-requisitos

1. **Python 3.13** instalado
2. **Conta Google Cloud** com Dialogflow CX configurado
3. **Credenciais do Google Cloud** (arquivo JSON)

## Passo 1: Instalar Dependências

```bash
pip install -r requirements.txt
```

## Passo 2: Habilitar APIs do Google Cloud

Antes de configurar as credenciais, você precisa habilitar as APIs necessárias:

### APIs Obrigatórias:

1. **Dialogflow CX API**
   - Acesse: https://console.cloud.google.com/apis/library/dialogflow.googleapis.com
   - Clique em "Enable" (Habilitar)

2. **Cloud Text-to-Speech API** ⚠️ **OBRIGATÓRIA**
   - Acesse: https://console.cloud.google.com/apis/library/texttospeech.googleapis.com
   - Clique em "Enable" (Habilitar)
   - **Ou use o link direto do erro** (se aparecer no log)

### Via gcloud CLI (alternativa):

```bash
gcloud services enable dialogflow.googleapis.com --project=seu-project-id
gcloud services enable texttospeech.googleapis.com --project=seu-project-id
```

**Nota**: Após habilitar, aguarde alguns minutos para a propagação das mudanças.

## Passo 3: Configurar Credenciais do Google Cloud

1. Baixe o arquivo JSON de credenciais do Google Cloud Console
2. Coloque o arquivo na pasta `credentials/` (crie a pasta se não existir)
3. Renomeie para `google-credentials.json` (ou use o nome que preferir)

## Passo 4: Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT_ID=seu-project-id-aqui
DIALOGFLOW_AGENT_ID=seu-agent-id-aqui
DIALOGFLOW_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./credentials/google-credentials.json

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Audio Configuration
# Configuração ideal para Vertex AI / Dialogflow CX: LINEAR16 @ 16000 Hz
SAMPLE_RATE=16000
CHANNELS=1
CHUNK_SIZE=4096
VAD_AGGRESSIVENESS=2

# Dialogflow Configuration
DIALOGFLOW_LANGUAGE_CODE=pt-BR
DIALOGFLOW_ENABLE_AUTO_SENTIMENT=true
```

### Onde encontrar os valores:

- **GOOGLE_CLOUD_PROJECT_ID**: ID do projeto no Google Cloud Console
- **DIALOGFLOW_AGENT_ID**: ID do agente no Dialogflow CX (geralmente um UUID)
- **DIALOGFLOW_LOCATION**: Região onde o agente está localizado
  - Se o agente está em `global`: use `global`
  - Se está em região específica: use a localização física (ex: `us-central1`, `us-east1`)
  - O código mapeia automaticamente: `us-central1` → `us`, `europe-west1` → `eu`
- **DIALOGFLOW_REGION_ID** (opcional): Força o ID de região (`us`, `eu`, `global`). Se não especificado, será mapeado automaticamente.
- **GOOGLE_APPLICATION_CREDENTIALS**: Caminho relativo ou absoluto para o arquivo JSON de credenciais

### ⚠️ Erro Comum: API não habilitada

Se você receber o erro:
```
403 Cloud Text-to-Speech API has not been used in project ... or it is disabled
```

**Solução**: Habilite a API seguindo o **Passo 2** acima. O erro fornece um link direto para habilitar:
- Link direto: https://console.cloud.google.com/apis/api/texttospeech.googleapis.com/overview?project=seu-project-id
- Substitua `seu-project-id` pelo ID do seu projeto

**Importante**: Após habilitar, aguarde alguns minutos para a propagação das mudanças.

## Passo 5: Executar o Servidor

### Opção 1: Usando Python diretamente

```bash
python run.py
```

ou

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Opção 2: Usando Docker

```bash
docker-compose up --build
```

## Passo 5: Verificar se está funcionando

Acesse `http://localhost:8000` no navegador. Você deve ver:

```json
{
  "message": "Chat Marketplace Backend - Real-Time Voice Chat",
  "version": "1.0.0",
  "websocket_endpoint": "/ws/voice-chat"
}
```

## Estrutura de Diretórios Recomendada

```
chat-marketplace-back/
├── credentials/
│   └── google-credentials.json  # Arquivo de credenciais do Google Cloud
├── .env                          # Variáveis de ambiente
├── main.py
├── config.py
├── requirements.txt
└── ...
```

## Troubleshooting

### Erro: "Credentials not found"

- Verifique se o arquivo de credenciais existe no caminho especificado
- Verifique se a variável `GOOGLE_APPLICATION_CREDENTIALS` está correta no `.env`

### Erro: "Agent not found"

- Verifique se o `DIALOGFLOW_AGENT_ID` está correto
- Verifique se o agente está na localização correta (`DIALOGFLOW_LOCATION`)
- Verifique se as credenciais têm permissão para acessar o agente

### Erro: "Module not found"

- Execute `pip install -r requirements.txt` novamente
- Verifique se está usando Python 3.13

### WebSocket não conecta

- Verifique se o servidor está rodando na porta correta
- Verifique se não há firewall bloqueando a conexão
- Verifique os logs do servidor para mais detalhes

## Próximos Passos

1. Configure seu agente no Dialogflow CX
2. Configure as ferramentas (tools) no Dialogflow para chamar APIs
3. Conecte seu frontend Angular ao WebSocket
4. Teste o fluxo completo de conversa

