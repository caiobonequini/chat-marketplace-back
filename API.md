# Documentação da API WebSocket

## Endpoint WebSocket

```
ws://localhost:8000/ws/voice-chat
```

## Protocolo de Mensagens

### Mensagens do Cliente → Servidor

#### 1. Chunk de Áudio
Envia um chunk de áudio PCM codificado em base64.

```json
{
  "type": "audio_chunk",
  "session_id": "opcional-se-ainda-não-enviado",
  "data": {
    "audio": "base64-encoded-audio-data"
  }
}
```

#### 2. Início de Fala
Notifica que o usuário começou a falar.

```json
{
  "type": "start_speaking",
  "session_id": "uuid-da-sessao"
}
```

#### 3. Fim de Fala
Notifica que o usuário parou de falar.

```json
{
  "type": "stop_speaking",
  "session_id": "uuid-da-sessao"
}
```

#### 4. Barge-in (Interrupção)
Interrompe a resposta do bot explicitamente.

```json
{
  "type": "barge_in",
  "session_id": "uuid-da-sessao"
}
```

### Mensagens do Servidor → Cliente

#### 1. Início de Sessão
Enviado quando a conexão é estabelecida.

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

#### 2. Chunk de Áudio da Resposta
Chunk de áudio da resposta do bot.

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

#### 3. Transcrição
Texto transcrito do que o usuário disse.

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

#### 4. Intenção Detectada
Intenção detectada pelo Dialogflow.

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

#### 5. Chamada de Ferramenta
Notificação de que uma ferramenta foi chamada.

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

#### 6. Erro
Mensagem de erro.

```json
{
  "type": "error",
  "session_id": "uuid-da-sessao",
  "data": {
    "error": "error_code",
    "message": "Descrição do erro"
  },
  "timestamp": 1234567890.123
}
```

## Exemplo de Fluxo Completo

### 1. Conectar ao WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/voice-chat');

ws.onopen = () => {
  console.log('Conectado ao servidor');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch(message.type) {
    case 'session_start':
      console.log('Sessão iniciada:', message.data.session_id);
      sessionId = message.data.session_id;
      break;
    
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

### 2. Enviar Áudio
```javascript
// Capturar áudio do microfone
// Configuração ideal para Vertex AI: LINEAR16 @ 16000 Hz
const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
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

### 3. Detectar Fim de Fala
```javascript
// Quando detectar silêncio prolongado
ws.send(JSON.stringify({
  type: 'stop_speaking',
  session_id: sessionId
}));
```

### 4. Barge-in
```javascript
// Quando usuário começar a falar durante resposta do bot
ws.send(JSON.stringify({
  type: 'barge_in',
  session_id: sessionId
}));
```

## Especificações de Áudio

- **Formato**: PCM 16-bit (LINEAR16)
- **Taxa de Amostragem**: 16000 Hz (configuração ideal para Vertex AI / Dialogflow CX)
- **Canais**: Mono (1 canal)
- **Codificação**: Base64 para transmissão WebSocket
- **Tamanho do Chunk**: Recomendado 4096 bytes

**Nota**: Esta configuração (LINEAR16 @ 16000 Hz) é otimizada para uso com Vertex AI endpoints, garantindo melhor qualidade e menor latência.

## Tratamento de Erros

O servidor pode enviar mensagens de erro em vários cenários:

- `audio_processing_error`: Erro ao processar áudio
- `stream_processing_error`: Erro ao processar stream
- `dialogflow_error`: Erro na API do Dialogflow
- `dialogflow_stream_error`: Erro no streaming do Dialogflow
- `message_processing_error`: Erro ao processar mensagem
- `websocket_error`: Erro geral no WebSocket

Sempre verifique o tipo de mensagem e trate erros adequadamente.

