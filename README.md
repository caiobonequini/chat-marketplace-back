# Chat Marketplace Backend - Real-Time Voice Chat

Backend profissional com WebSocket para chat em tempo real com integração ao **Dialogflow CX** e **Vertex AI**. Sistema de voz com streaming bidirecional, detecção de atividade de voz (VAD) e suporte a interrupções (barge-in).

**Configuração de Áudio**: LINEAR16 @ 16000 Hz (otimizado para Vertex AI endpoints)

## 🎯 Funcionalidades

- ✅ **Streaming bidirecional de áudio** via WebSocket
- ✅ **Integração com Dialogflow CX** para processamento de áudio e intenções
- ✅ **Voice Activity Detection (VAD)** para detectar início/fim de fala
- ✅ **Barge-in (interrupção em tempo real)** - permite interromper o bot enquanto fala
- ✅ **Integração com ferramentas/APIs (tools)** - chamadas de APIs durante a conversa
- ✅ **Baixa latência** - respostas em tempo real com streaming

## 📋 Requisitos

- Python 3.13
- Conta Google Cloud com Dialogflow CX configurado
- Credenciais do Google Cloud (arquivo JSON)
- **APIs habilitadas**: Dialogflow CX API e Cloud Text-to-Speech API

## 🚀 Instalação Rápida

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente (criar arquivo .env)
# Ver SETUP.md para detalhes

# 3. Executar servidor
python run.py
```

## 📖 Documentação

### Documentação Principal
- **[docs/INDEX.md](docs/INDEX.md)** - Índice completo da documentação
- **[SETUP.md](SETUP.md)** - Guia completo de configuração
- **[INSTALL_WINDOWS.md](INSTALL_WINDOWS.md)** - Guia de instalação no Windows

### Arquitetura e Design
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Arquitetura detalhada do sistema

### API e Integração
- **[API.md](API.md)** - Documentação da API WebSocket
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** - Referência completa da API

### Desenvolvimento
- **[.cursorrules](.cursorrules)** - Regras e padrões de desenvolvimento

## 🏗️ Estrutura do Projeto

```
.
├── main.py                 # Aplicação FastAPI principal
├── config.py              # Configurações e variáveis de ambiente
├── websocket_handler.py   # Handler WebSocket e gerenciamento de sessões
├── dialogflow_service.py  # Serviço de integração com Dialogflow CX
├── vad_service.py         # Voice Activity Detection (WebRTC VAD)
├── audio_processor.py     # Processamento e conversão de áudio
├── tools/                 # Ferramentas/APIs integradas
│   └── products.py        # Busca de produtos
├── models/                # Modelos Pydantic
│   └── messages.py        # Modelos de mensagens WebSocket
├── utils/                 # Utilitários
│   └── logger.py          # Sistema de logging estruturado
├── run.py                 # Script para executar o servidor
├── test_websocket.py      # Exemplo de teste WebSocket
├── Dockerfile             # Container Docker
└── docker-compose.yml     # Orquestração Docker Compose
```

## 🔌 WebSocket Endpoint

```
ws://localhost:8000/ws/voice-chat
```

### Mensagens Suportadas

**Cliente → Servidor:**
- `audio_chunk`: Chunk de áudio PCM codificado em base64
- `start_speaking`: Notifica que usuário começou a falar
- `stop_speaking`: Notifica que usuário parou de falar
- `barge_in`: Interrupção explícita do usuário

**Servidor → Cliente:**
- `session_start`: Confirmação de início de sessão
- `audio_response`: Chunk de áudio da resposta do bot
- `transcription`: Texto transcrito da fala do usuário
- `intent`: Intenção detectada pelo Dialogflow
- `tool_call`: Notificação de chamada de ferramenta
- `error`: Mensagem de erro

Veja [API.md](API.md) para detalhes completos do protocolo.

## 🎤 Especificações de Áudio

- **Formato**: PCM 16-bit (LINEAR16)
- **Taxa de Amostragem**: 16000 Hz (configuração ideal para Vertex AI)
- **Canais**: Mono (1 canal)
- **Codificação**: Base64 para transmissão WebSocket
- **Tamanho do Chunk**: Recomendado 4096 bytes

## 🐳 Docker

```bash
# Build e execução
docker-compose up --build

# Apenas build
docker build -t chat-marketplace-backend .

# Executar container
docker run -p 8000:8000 --env-file .env chat-marketplace-backend
```

## 🧪 Testes

```bash
# Testar conexão WebSocket (exemplo)
python test_websocket.py
```

## 📝 Variáveis de Ambiente

Veja [SETUP.md](SETUP.md) para configuração completa. Principais variáveis:

- `GOOGLE_CLOUD_PROJECT_ID` - ID do projeto Google Cloud
- `DIALOGFLOW_AGENT_ID` - ID do agente Dialogflow CX
- `DIALOGFLOW_LOCATION` - Localização do agente (ex: us-central1)
- `GOOGLE_APPLICATION_CREDENTIALS` - Caminho para credenciais JSON

## 🔧 Desenvolvimento

```bash
# Modo desenvolvimento com reload automático
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Modo produção
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📚 Recursos Adicionais

- [Documentação Dialogflow CX](https://cloud.google.com/dialogflow/cx/docs)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)
- [WebRTC VAD](https://github.com/wiseman/py-webrtcvad)

