# Referência da API

## Endpoints HTTP

### GET `/`

Retorna informações sobre a API.

**Resposta:**
```json
{
  "message": "Chat Marketplace Backend - Real-Time Voice Chat",
  "version": "1.0.0",
  "websocket_endpoint": "ws://localhost:8000/ws/voice-chat",
  "note": "WebSocket não pode ser acessado via HTTP GET...",
  "endpoints": {
    "health": "/health",
    "websocket": "/ws/voice-chat",
    "test_page": "/test"
  }
}
```

### GET `/health`

Health check do servidor.

**Resposta:**
```json
{
  "status": "healthy"
}
```

### GET `/test`

Página HTML para testar conexão WebSocket.

**Resposta:** HTML com interface de teste interativa.

## Endpoint WebSocket

### `ws://localhost:8000/ws/voice-chat`

Conexão WebSocket para chat por voz em tempo real.

## Protocolo de Mensagens

### Mensagens do Cliente → Servidor

#### `audio_chunk`

Envia um chunk de áudio PCM codificado em base64.

**Formato:**
```json
{
  "type": "audio_chunk",
  "session_id": "uuid-opcional",
  "data": {
    "audio": "base64-encoded-audio-data"
  }
}
```

**Especificações:**
- Formato: PCM 16-bit (LINEAR16)
- Sample rate: 16000 Hz (configuração ideal para Vertex AI)
- Canais: Mono (1)
- Codificação: Base64
- Tamanho recomendado: 4096 bytes

#### `start_speaking`

Notifica que o usuário começou a falar.

**Formato:**
```json
{
  "type": "start_speaking",
  "session_id": "uuid-da-sessao"
}
```

**Comportamento:**
- Ativa flag `is_speaking`
- Se bot estiver falando, ativa barge-in
- Cancela stream atual do bot

#### `stop_speaking`

Notifica que o usuário parou de falar.

**Formato:**
```json
{
  "type": "stop_speaking",
  "session_id": "uuid-da-sessao"
}
```

**Comportamento:**
- Desativa flag `is_speaking`
- Processa áudio acumulado no buffer
- Envia para Dialogflow

#### `barge_in`

Interrupção explícita do usuário.

**Formato:**
```json
{
  "type": "barge_in",
  "session_id": "uuid-da-sessao"
}
```

**Comportamento:**
- Para resposta do bot imediatamente
- Limpa buffer de áudio
- Cancela stream atual
- Prepara para nova fala

### Mensagens do Servidor → Cliente

#### `session_start`

Enviado quando a conexão é estabelecida.

**Formato:**
```json
{
  "type": "session_start",
  "session_id": "uuid-da-sessao",
  "data": {
    "session_id": "uuid-da-sessao"
  },
  "timestamp": 1234567890.123
}
```

#### `audio_response`

Chunk de áudio da resposta do bot.

**Formato:**
```json
{
  "type": "audio_response",
  "session_id": "uuid-da-sessao",
  "data": {
    "audio": "base64-encoded-audio-data"
  },
  "timestamp": 1234567890.123
}
```

**Especificações:**
- Formato: PCM 16-bit (LINEAR16)
- Sample rate: 16000 Hz (configuração ideal para Vertex AI)
- Canais: Mono (1)
- Codificação: Base64

#### `transcription`

Texto transcrito do que o usuário disse.

**Formato:**
```json
{
  "type": "transcription",
  "session_id": "uuid-da-sessao",
  "data": {
    "text": "Quero comprar um iPhone"
  },
  "timestamp": 1234567890.123
}
```

#### `intent`

Intenção detectada pelo Dialogflow.

**Formato:**
```json
{
  "type": "intent",
  "session_id": "uuid-da-sessao",
  "data": {
    "intent": "buscar_produto",
    "confidence": 0.95
  },
  "timestamp": 1234567890.123
}
```

**Campos:**
- `intent`: Nome da intenção detectada
- `confidence`: Confiança (0.0 a 1.0)

#### `tool_call`

Notificação de que uma ferramenta foi chamada.

**Formato:**
```json
{
  "type": "tool_call",
  "session_id": "uuid-da-sessao",
  "data": {
    "tool": "search_products",
    "parameters": {
      "query": "iPhone",
      "category": "eletrônicos"
    }
  },
  "timestamp": 1234567890.123
}
```

#### `error`

Mensagem de erro.

**Formato:**
```json
{
  "type": "error",
  "session_id": "uuid-da-sessao",
  "data": {
    "error": "error_code",
    "message": "Descrição detalhada do erro"
  },
  "timestamp": 1234567890.123
}
```

**Códigos de Erro:**

- `audio_processing_error`: Erro ao processar áudio
- `stream_processing_error`: Erro ao processar stream
- `dialogflow_error`: Erro na API do Dialogflow
- `dialogflow_stream_error`: Erro no streaming do Dialogflow
- `message_processing_error`: Erro ao processar mensagem
- `websocket_error`: Erro geral no WebSocket

## Exemplo de Fluxo Completo

### 1. Conectar

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/voice-chat');

ws.onopen = () => {
  console.log('Conectado');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Recebido:', message);
};
```

### 2. Receber Sessão

```javascript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'session_start') {
    sessionId = message.data.session_id;
    console.log('Sessão:', sessionId);
  }
};
```

### 3. Enviar Áudio

```javascript
// Capturar áudio do microfone
// Configuração ideal para Vertex AI: LINEAR16 @ 16000 Hz
const mediaStream = await navigator.mediaDevices.getUserMedia({ 
  audio: {
    sampleRate: 16000,
    channelCount: 1
  }
});

const audioContext = new AudioContext({ sampleRate: 16000 });
const source = audioContext.createMediaStreamSource(mediaStream);
const processor = audioContext.createScriptProcessor(4096, 1, 1);

processor.onaudioprocess = (e) => {
  const audioData = e.inputBuffer.getChannelData(0);
  const pcm16 = convertFloat32ToPCM16(audioData);
  const base64 = btoa(String.fromCharCode(...pcm16));
  
  ws.send(JSON.stringify({
    type: 'audio_chunk',
    session_id: sessionId,
    data: { audio: base64 }
  }));
};

source.connect(processor);
processor.connect(audioContext.destination);
```

### 4. Detectar Fim de Fala

```javascript
// Quando detectar silêncio prolongado
ws.send(JSON.stringify({
  type: 'stop_speaking',
  session_id: sessionId
}));
```

### 5. Receber Resposta

```javascript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch(message.type) {
    case 'audio_response':
      // Reproduzir áudio
      const audioData = atob(message.data.audio);
      playAudio(audioData);
      break;
    
    case 'transcription':
      console.log('Usuário disse:', message.data.text);
      break;
    
    case 'intent':
      console.log('Intenção:', message.data.intent);
      break;
    
    case 'error':
      console.error('Erro:', message.data.message);
      break;
  }
};
```

### 6. Barge-in

```javascript
// Quando usuário começar a falar durante resposta
ws.send(JSON.stringify({
  type: 'barge_in',
  session_id: sessionId
}));
```

## Tratamento de Erros

### Erros de Conexão

```javascript
ws.onerror = (error) => {
  console.error('Erro WebSocket:', error);
  // Tentar reconectar
};

ws.onclose = (event) => {
  console.log('Conexão fechada:', event.code, event.reason);
  // Implementar reconexão com backoff exponencial
};
```

### Erros do Servidor

```javascript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'error') {
    console.error('Erro do servidor:', message.data.error);
    console.error('Mensagem:', message.data.message);
    
    // Tratar erro específico
    switch(message.data.error) {
      case 'dialogflow_error':
        // Erro no Dialogflow - tentar novamente
        break;
      case 'audio_processing_error':
        // Erro no processamento - verificar formato de áudio
        break;
    }
  }
};
```

## Boas Práticas

1. **Sempre aguarde `session_start`** antes de enviar mensagens
2. **Use `start_speaking`/`stop_speaking`** para melhor controle
3. **Implemente reconexão** com backoff exponencial
4. **Valide mensagens** antes de processar
5. **Trate erros** adequadamente
6. **Limite tamanho de chunks** de áudio (4096 bytes)
7. **Use barge-in** para melhor UX

## Limites e Restrições

- **Tamanho máximo de mensagem**: 1MB (configurável)
- **Timeout de conexão**: Sem timeout (gerenciado pelo cliente)
- **Sessões simultâneas**: Ilimitadas (limitado por recursos)
- **Tamanho de buffer**: 100 chunks máximo
- **Sample rate**: 16000 Hz (LINEAR16 - configuração ideal para Vertex AI)

