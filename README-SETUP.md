# Guia de Setup Local - Windows

## Pré-requisitos

1. **Python 3.13 ou 3.12** instalado
   - Baixe em: https://www.python.org/downloads/
   - **IMPORTANTE**: Marque "Add Python to PATH" durante a instalação
   - Ou instale via Microsoft Store (procure "Python 3.13")

2. **PowerShell** (já vem com Windows)

## Setup Automático (Recomendado)

1. Abra PowerShell no diretório do projeto:
   ```powershell
   cd C:\Users\alisson.pereira\source\chat-marketplace-back
   ```

2. Execute o script de setup:
   ```powershell
   .\setup-local.ps1
   ```

3. Configure o arquivo `.env` com suas credenciais do Google Cloud

4. Execute o servidor:
   ```powershell
   .\run-local.ps1
   ```

## Setup Manual

### 1. Criar ambiente virtual

```powershell
python -m venv venv
```

### 2. Ativar ambiente virtual

```powershell
.\venv\Scripts\Activate.ps1
```

**Nota**: Se receber erro de política de execução, execute:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. Instalar dependências

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Google Cloud
GOOGLE_CLOUD_PROJECT_ID=seu-project-id
DIALOGFLOW_AGENT_ID=seu-agent-id
DIALOGFLOW_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Audio
SAMPLE_RATE=16000
CHANNELS=1
CHUNK_SIZE=4096
VAD_AGGRESSIVENESS=2

# Dialogflow
DIALOGFLOW_LANGUAGE_CODE=pt-BR
```

### 5. Executar servidor

```powershell
python run.py
```

Ou com uvicorn diretamente:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Verificar Instalação

Após instalar, teste se tudo está funcionando:

```powershell
python --version
python -m pip --version
```

## Solução de Problemas

### Python não encontrado

1. Verifique se Python está instalado:
   ```powershell
   python --version
   ```

2. Se não funcionar, tente:
   ```powershell
   py --version
   ```

3. Se ainda não funcionar, adicione Python ao PATH manualmente:
   - Abra "Variáveis de Ambiente" no Windows
   - Adicione o caminho do Python (ex: `C:\Python313\`)

### Erro de política de execução no PowerShell

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Erro ao instalar dependências

Algumas dependências podem precisar de compiladores C++:
- Instale "Microsoft C++ Build Tools" ou
- Use versões pré-compiladas (wheels)

### Erro de credenciais do Google Cloud

1. Baixe o arquivo JSON de credenciais do Google Cloud Console
2. Coloque em `./credentials/service-account.json`
3. Configure o caminho no `.env`

## Testar o Servidor

Após iniciar, acesse:

- **API**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **Test Page**: http://localhost:8000/test
- **WebSocket**: ws://localhost:8000/ws/voice-chat
- **Docs**: http://localhost:8000/docs (Swagger UI)

## Próximos Passos

1. Configure as credenciais do Google Cloud no `.env`
2. Teste a conexão WebSocket usando a página `/test`
3. Integre com o frontend Angular

