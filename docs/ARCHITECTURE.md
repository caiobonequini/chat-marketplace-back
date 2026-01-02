# Arquitetura do Sistema

## Visão Geral

O Chat Marketplace Backend é um sistema de chat por voz em tempo real que utiliza WebSocket para comunicação bidirecional, integrado com Dialogflow CX para processamento de linguagem natural e detecção de intenções.

## Componentes Principais

### 1. FastAPI Application (`main.py`)

**Responsabilidades:**
- Inicialização da aplicação FastAPI
- Configuração de CORS
- Endpoints HTTP (raiz, health check, página de teste)
- Endpoint WebSocket principal (`/ws/voice-chat`)

**Características:**
- Suporte a múltiplas conexões simultâneas
- Gerenciamento de ciclo de vida da aplicação
- Logging estruturado

### 2. WebSocket Handler (`websocket_handler.py`)

**Componentes:**

#### `VoiceChatSession`
Gerencia uma sessão individual de chat por voz.

**Estado:**
- `is_speaking`: Usuário está falando
- `is_bot_speaking`: Bot está respondendo
- `audio_buffer`: Buffer circular de chunks de áudio (max 100)
- `barge_in_flag`: Event para sinalizar interrupção

**Métodos principais:**
- `handle_audio_chunk()`: Processa chunk de áudio recebido
- `handle_start_speaking()`: Detecta início de fala
- `handle_stop_speaking()`: Detecta fim de fala
- `handle_barge_in()`: Processa interrupção
- `process_audio_stream()`: Envia áudio para Dialogflow
- `_process_dialogflow_stream()`: Processa respostas do Dialogflow

#### `WebSocketManager`
Gerencia múltiplas sessões simultâneas.

**Funcionalidades:**
- Criação e destruição de sessões
- Roteamento de mensagens para sessões corretas
- Limpeza automática de recursos

### 3. Dialogflow Service (`dialogflow_service.py`)

**Responsabilidades:**
- Integração com Google Cloud Dialogflow CX
- Streaming de áudio para detecção de intenções
- Processamento de respostas (texto, áudio, intenções, parâmetros)
- Detecção de chamadas de ferramentas

**Fluxo:**
1. Recebe chunks de áudio via AsyncIterator
2. Envia para Dialogflow via `streaming_detect_intent`
3. Processa respostas em tempo real
4. Extrai texto, intenções, parâmetros e áudio de resposta

### 4. VAD Service (`vad_service.py`)

**Responsabilidades:**
- Detecção de atividade de voz (Voice Activity Detection)
- Identificação de início/fim de fala
- Suporte opcional (funciona sem webrtcvad)

**Características:**
- Usa WebRTC VAD quando disponível
- Fallback: assume sempre há fala se VAD não disponível
- Suporta sample rates: 8000, 16000, 32000, 48000 Hz
- Reamostragem automática para 16000 Hz se necessário

### 5. Audio Processor (`audio_processor.py`)

**Responsabilidades:**
- Conversão entre formatos (base64 ↔ bytes ↔ numpy)
- Reamostragem de áudio
- Normalização de áudio

**Operações:**
- `base64_to_bytes()`: Decodifica base64 para bytes PCM
- `bytes_to_base64()`: Codifica bytes PCM para base64
- `bytes_to_numpy()`: Converte bytes para array numpy
- `numpy_to_bytes()`: Converte array numpy para bytes
- `resample_audio()`: Reamostra áudio para nova taxa
- `normalize_audio()`: Normaliza amplitude

### 6. Tools (`tools/products.py`)

**Responsabilidades:**
- Integração com APIs externas
- Busca de produtos
- Processamento de chamadas de ferramentas do Dialogflow

**Exemplo:**
- `search_products()`: Busca produtos via API REST
- `get_product_by_id()`: Busca produto específico
- `parse_tool_call()`: Processa chamada do Dialogflow

## Fluxo de Dados

### 1. Conexão Inicial

```
Cliente → WebSocket Connect → Servidor
Servidor → session_start → Cliente
```

### 2. Envio de Áudio

```
Cliente → audio_chunk (base64) → Servidor
Servidor → VAD Detection → is_speech?
Servidor → Buffer de Áudio
```

### 3. Processamento

```
Servidor → stop_speaking → Processar Buffer
Servidor → Dialogflow Streaming → Enviar Chunks
Dialogflow → Processar Áudio → Detectar Intenção
Dialogflow → Gerar Resposta → Enviar Áudio
```

### 4. Resposta

```
Dialogflow → audio_response (base64) → Servidor
Servidor → audio_response → Cliente
Cliente → Reproduzir Áudio
```

### 5. Barge-in

```
Cliente → barge_in → Servidor
Servidor → Cancelar Stream Atual
Servidor → Limpar Buffer
Servidor → Processar Nova Fala
```

## Gerenciamento de Estado

### Sessão

Cada conexão WebSocket cria uma sessão única identificada por UUID.

**Estado da Sessão:**
- ID único (UUID)
- Conexão WebSocket ativa
- Buffer de áudio
- Flags de estado (is_speaking, is_bot_speaking)
- Task de stream atual
- Event de barge-in

### Lifecycle

1. **Criação**: Ao conectar WebSocket
2. **Ativação**: Após inicializar Dialogflow
3. **Processamento**: Durante troca de mensagens
4. **Limpeza**: Ao desconectar

## Tratamento de Erros

### Níveis de Erro

1. **Erro de Conexão**: WebSocket não conecta
2. **Erro de Processamento**: Falha ao processar mensagem
3. **Erro de Dialogflow**: Falha na API do Google
4. **Erro de Áudio**: Falha ao processar áudio

### Estratégias

- **Logging**: Todos os erros são logados
- **Notificação**: Cliente recebe mensagem de erro via WebSocket
- **Recuperação**: Sistema tenta continuar quando possível
- **Cleanup**: Recursos são limpos mesmo em caso de erro

## Performance

### Otimizações

1. **Buffer Circular**: Limita uso de memória
2. **Streaming**: Processa enquanto recebe
3. **Async/Await**: Não bloqueia event loop
4. **Task Cancellation**: Cancela operações desnecessárias

### Limites

- Buffer de áudio: 100 chunks máximo
- Sessões simultâneas: Ilimitadas (limitado por recursos)
- Tamanho de chunk: 4096 bytes recomendado
- Sample rate: 16000 Hz padrão (LINEAR16 - configuração ideal para Vertex AI)

## Segurança

### Considerações

1. **CORS**: Configurado para desenvolvimento (ajustar em produção)
2. **Credenciais**: Google Cloud via variáveis de ambiente
3. **Validação**: Pydantic valida todas as mensagens
4. **Sanitização**: Base64 encoding para áudio

### Recomendações para Produção

- Restringir origens CORS
- Usar HTTPS/WSS
- Implementar autenticação
- Rate limiting
- Validação de tamanho de mensagens

## Escalabilidade

### Horizontal

- Múltiplas instâncias do servidor
- Load balancer com sticky sessions
- Banco de dados compartilhado para estado (se necessário)

### Vertical

- Aumentar workers do Uvicorn
- Otimizar processamento de áudio
- Cache de respostas do Dialogflow

## Monitoramento

### Métricas Importantes

- Número de sessões ativas
- Latência de processamento
- Taxa de erros
- Uso de memória
- Throughput de mensagens

### Logging

- Logs estruturados em JSON
- Níveis: DEBUG, INFO, WARNING, ERROR
- Contexto: session_id, timestamp, tipo de mensagem

