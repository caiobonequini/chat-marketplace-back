"""Aplicação principal FastAPI com WebSocket."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from typing import Optional
import uvicorn

from config import settings
from websocket_handler import websocket_manager
from utils.logger import setup_logging, get_logger
from models.upload import UploadResponse
from services.scribe_strategy import SofyaScribeStrategy
from services.marketplace_client import MarketplaceClient

# Configurar logging
setup_logging(debug=settings.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    logger.info("Iniciando aplicação...")
    yield
    logger.info("Encerrando aplicação...")


# Criar aplicação FastAPI
app = FastAPI(
    title="Chat Marketplace Backend - Real-Time Voice Chat",
    description="Backend com WebSocket para chat em tempo real com Dialogflow CX",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Endpoint raiz."""
    return {
        "message": "Chat Marketplace Backend - Real-Time Voice Chat",
        "version": "1.0.0",
        "websocket_endpoint": "ws://localhost:8000/ws/voice-chat",
        "note": "WebSocket não pode ser acessado via HTTP GET. Use um cliente WebSocket ou acesse /test para página de teste.",
        "endpoints": {
            "health": "/health",
            "websocket": "/ws/voice-chat",
            "test_page": "/test"
        }
    }


@app.get("/health")
async def health():
    """Endpoint de health check."""
    return {"status": "healthy"}


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    workspace_id: Optional[str] = Form(None),
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """
    Endpoint para upload de arquivos (PDF/Áudio).
    
    Se for áudio: transcreve usando Sofya Scribe.
    Se for PDF ou texto transcrito: indexa no NotebookMV.
    
    Args:
        file: Arquivo a ser enviado
        workspace_id: ID do workspace (obrigatório para indexação)
        x_api_key: Chave de API do cliente (obrigatória)
    
    Returns:
        Resposta com status do upload e transcrição (se aplicável)
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="x-api-key header é obrigatório")
    
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id é obrigatório para indexação")
    
    try:
        # Ler conteúdo do arquivo
        file_content = await file.read()
        file_type = file.content_type or ""
        filename = file.filename or "unknown"
        
        logger.info(f"Upload recebido: {filename}, tipo: {file_type}, tamanho: {len(file_content)} bytes")
        
        transcription = None
        
        # Se for áudio, transcrever primeiro
        if file_type.startswith("audio/") or filename.lower().endswith((".wav", ".mp3", ".ogg", ".m4a", ".flac")):
            logger.info("Processando arquivo de áudio - iniciando transcrição")
            scribe = SofyaScribeStrategy(api_key=x_api_key)
            try:
                result = await scribe.transcribe_audio_file(
                    audio_file=file_content,
                    filename=filename,
                    content_type=file_type
                )
                transcription = result.get("text", "")
                if not transcription:
                    logger.warning("Transcrição retornou texto vazio")
            except Exception as e:
                logger.error(f"Erro ao transcrever áudio: {e}")
                return UploadResponse(
                    success=False,
                    message="Erro ao transcrever áudio",
                    error=str(e)
                )
            finally:
                await scribe.close()
        
        # Indexar no NotebookMV (PDF ou texto transcrito)
        notebook_client = MarketplaceClient(
            api_key=x_api_key,
            base_url="https://notebook-mv-back-dev-829403472317.us-central1.run.app"
        )
        
        try:
            # Se temos transcrição, enviar como texto
            if transcription:
                # Para texto transcrito, podemos enviar via endpoint de chat ou archive
                # Assumindo que há um endpoint para indexar texto
                logger.info(f"Indexando transcrição no workspace {workspace_id}")
                # Nota: Ajustar endpoint conforme API real do NotebookMV
                # Por enquanto, apenas logamos
                pass
            
            # Para PDF, usar endpoint de archive
            if file_type == "application/pdf" or filename.lower().endswith(".pdf"):
                logger.info(f"Indexando PDF no workspace {workspace_id}")
                endpoint = f"/workspace/{workspace_id}/archive/file"
                
                files = {
                    "file": (filename, file_content, file_type)
                }
                
                try:
                    response = await notebook_client.post(endpoint, files=files)
                    result = response.json()
                    file_id = result.get("file_id", result.get("id", ""))
                    
                    return UploadResponse(
                        success=True,
                        message="Arquivo indexado com sucesso",
                        transcription=transcription,
                        file_id=file_id
                    )
                except Exception as e:
                    logger.error(f"Erro ao indexar arquivo: {e}")
                    return UploadResponse(
                        success=False,
                        message="Erro ao indexar arquivo",
                        transcription=transcription,
                        error=str(e)
                    )
            else:
                # Para outros tipos de arquivo ou apenas transcrição
                return UploadResponse(
                    success=True,
                    message="Arquivo processado com sucesso",
                    transcription=transcription
                )
        
        finally:
            await notebook_client.close()
    
    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        return UploadResponse(
            success=False,
            message="Erro ao processar upload",
            error=str(e)
        )


@app.get("/test", response_class=HTMLResponse)
async def test_page():
    """Página HTML simples para testar WebSocket."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste WebSocket - Chat Marketplace</title>
        <meta charset="UTF-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
            }
            .status {
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
                font-weight: bold;
            }
            .status.connected {
                background-color: #d4edda;
                color: #155724;
            }
            .status.disconnected {
                background-color: #f8d7da;
                color: #721c24;
            }
            button {
                padding: 10px 20px;
                margin: 5px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            button.connect {
                background-color: #28a745;
                color: white;
            }
            button.disconnect {
                background-color: #dc3545;
                color: white;
            }
            button:disabled {
                background-color: #ccc;
                cursor: not-allowed;
            }
            #messages {
                margin-top: 20px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
                max-height: 400px;
                overflow-y: auto;
            }
            .message {
                padding: 8px;
                margin: 5px 0;
                border-left: 3px solid #007bff;
                background-color: white;
            }
            .message.error {
                border-left-color: #dc3545;
            }
            .message.success {
                border-left-color: #28a745;
            }
            .message.info {
                border-left-color: #17a2b8;
            }
            .message.warning {
                border-left-color: #ffc107;
            }
            .transcription-box {
                margin-top: 20px;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px;
                color: white;
                font-size: 18px;
                font-weight: bold;
                min-height: 60px;
                display: flex;
                align-items: center;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
            .transcription-box.empty {
                background: #e9ecef;
                color: #6c757d;
                font-weight: normal;
                font-size: 14px;
            }
            .transcription-label {
                font-size: 12px;
                opacity: 0.8;
                margin-bottom: 5px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .chat-history {
                margin-top: 20px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
                max-height: 300px;
                overflow-y: auto;
            }
            .chat-message {
                padding: 10px;
                margin: 10px 0;
                border-radius: 8px;
                max-width: 80%;
            }
            .chat-message.user {
                background-color: #007bff;
                color: white;
                margin-left: auto;
                text-align: right;
            }
            .chat-message.bot {
                background-color: #6c757d;
                color: white;
                margin-right: auto;
            }
            .chat-message-label {
                font-size: 11px;
                opacity: 0.8;
                margin-bottom: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔌 Teste WebSocket - Chat Marketplace</h1>
            
            <div id="status" class="status disconnected">
                Desconectado
            </div>
            
            <div>
                <button id="connectBtn" class="connect" onclick="connect()">Conectar</button>
                <button id="disconnectBtn" class="disconnect" onclick="disconnect()" disabled>Desconectar</button>
                <button onclick="sendTestMessage()" id="testBtn" disabled>🎤 Testar Áudio (2 minutos)</button>
                <button onclick="stopAudioCapture()" id="stopBtn" disabled style="display: none;">⏹️ Parar Captura</button>
                <button onclick="testSTTOnly()" id="testSTTBtn" disabled style="background-color: #17a2b8; color: white;">🎙️ Testar Apenas STT</button>
                <button onclick="stopSTTCapture()" id="stopSTTBtn" disabled style="background-color: #dc3545; color: white; display: none;">⏹️ Parar STT</button>
            </div>
            
            <div class="transcription-box empty" id="transcriptionBox">
                <div>
                    <div class="transcription-label">Última Transcrição</div>
                    <div id="transcriptionText">Aguardando transcrição...</div>
                </div>
            </div>
            
            <!-- Indicador de Volume (Debug) -->
            <div id="volumeIndicator" style="margin-top: 10px; padding: 10px; background: #e9ecef; border-radius: 5px; display: none;">
                <div style="font-size: 12px; color: #6c757d; margin-bottom: 5px;">📊 Volume do Microfone (Debug)</div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="flex: 1; height: 20px; background: #dee2e6; border-radius: 10px; overflow: hidden; position: relative;">
                        <div id="volumeBar" style="height: 100%; background: linear-gradient(90deg, #28a745 0%, #ffc107 70%, #dc3545 100%); width: 0%; transition: width 0.1s;"></div>
                    </div>
                    <div id="volumeText" style="font-size: 11px; color: #495057; min-width: 80px; text-align: right;">0.000</div>
                </div>
                <div id="volumeStatus" style="font-size: 11px; color: #6c757d; margin-top: 5px;">Aguardando...</div>
            </div>
            
            <div class="chat-history" id="chatHistory">
                <div style="text-align: center; color: #6c757d; padding: 10px;">Histórico de conversa aparecerá aqui...</div>
            </div>
            
            <!-- Interface de Chat Texto -->
            <div class="text-chat-container" id="textChatContainer" style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <div style="font-weight: bold; margin-bottom: 10px; color: #333;">💬 Chat de Texto</div>
                <div style="display: flex; gap: 10px;">
                    <input 
                        type="text" 
                        id="textInput" 
                        placeholder="Digite sua mensagem aqui..." 
                        style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px;"
                        onkeypress="if(event.key === 'Enter') sendTextMessage()"
                    />
                    <button 
                        onclick="sendTextMessage()" 
                        id="sendTextBtn"
                        style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px;"
                    >
                        Enviar
                    </button>
                </div>
                <div style="margin-top: 10px; font-size: 12px; color: #6c757d;">
                    💡 Dica: Use o chat de texto se a transcrição de voz não entender corretamente
                </div>
            </div>
            
            <div id="messages"></div>
        </div>
        
        <script>
            let ws = null;
            const wsUrl = 'ws://localhost:8000/ws/voice-chat';
            
            function updateStatus(connected) {
                const statusEl = document.getElementById('status');
                const connectBtn = document.getElementById('connectBtn');
                const disconnectBtn = document.getElementById('disconnectBtn');
                const testBtn = document.getElementById('testBtn');
                const stopBtn = document.getElementById('stopBtn');
                const testSTTBtn = document.getElementById('testSTTBtn');
                
                if (connected) {
                    statusEl.textContent = 'Conectado';
                    statusEl.className = 'status connected';
                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
                    testBtn.disabled = false;
                    if (testSTTBtn) testSTTBtn.disabled = false;
                } else {
                    statusEl.textContent = 'Desconectado';
                    statusEl.className = 'status disconnected';
                    connectBtn.disabled = false;
                    disconnectBtn.disabled = true;
                    testBtn.disabled = true;
                    stopBtn.disabled = true;
                    stopBtn.style.display = 'none';
                    if (testSTTBtn) testSTTBtn.disabled = true;
                    // Parar captura se desconectar
                    stopAudioCapture();
                }
            }
            
            function updateRecordingStatus(recording) {
                const testBtn = document.getElementById('testBtn');
                const stopBtn = document.getElementById('stopBtn');
                
                if (recording) {
                    testBtn.disabled = true;
                    stopBtn.disabled = false;
                    stopBtn.style.display = 'inline-block';
                } else {
                    testBtn.disabled = false;
                    stopBtn.disabled = true;
                    stopBtn.style.display = 'none';
                }
            }
            
            function addMessage(message, type = 'info') {
                const messagesEl = document.getElementById('messages');
                const messageEl = document.createElement('div');
                messageEl.className = 'message ' + type;
                messageEl.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message;
                messagesEl.appendChild(messageEl);
                messagesEl.scrollTop = messagesEl.scrollHeight;
            }
            
            /**
             * Atualiza a caixa de transcrição destacada
             */
            function updateTranscriptionBox(text, isEmpty) {
                const box = document.getElementById('transcriptionBox');
                const textEl = document.getElementById('transcriptionText');
                
                if (isEmpty || !text || text.trim().length === 0) {
                    box.className = 'transcription-box empty';
                    textEl.textContent = 'Aguardando transcrição...';
                } else {
                    box.className = 'transcription-box';
                    textEl.textContent = text;
                }
            }
            
            /**
             * Atualiza o indicador visual de volume (debug)
             */
            function updateVolumeIndicator(volumeRMS, volumeVariance, hasSignificantVolume, hasVariation, threshold) {
                const indicator = document.getElementById('volumeIndicator');
                const volumeBar = document.getElementById('volumeBar');
                const volumeText = document.getElementById('volumeText');
                const volumeStatus = document.getElementById('volumeStatus');
                
                if (!indicator || !volumeBar || !volumeText || !volumeStatus) return;
                
                // Mostrar indicador quando estiver gravando
                if (isRecording) {
                    indicator.style.display = 'block';
                } else {
                    indicator.style.display = 'none';
                    return;
                }
                
                // Calcular porcentagem do volume (0-100%)
                const maxVolume = 0.5; // Volume máximo esperado
                const volumePercent = Math.min(100, (volumeRMS / maxVolume) * 100);
                
                // Atualizar barra de volume
                volumeBar.style.width = volumePercent + '%';
                
                // Atualizar texto numérico
                volumeText.textContent = volumeRMS.toFixed(3);
                
                // Atualizar status
                let statusText = '';
                let statusColor = '#6c757d';
                
                if (!hasSignificantVolume) {
                    statusText = `🔇 Ruído (abaixo de ${threshold.toFixed(3)})`;
                    statusColor = '#6c757d';
                } else if (!hasVariation) {
                    statusText = `⚠️ Ruído constante (sem variação: ${volumeVariance.toFixed(4)})`;
                    statusColor = '#ffc107';
                } else {
                    statusText = `✅ Fala detectada (variação: ${volumeVariance.toFixed(4)})`;
                    statusColor = '#28a745';
                }
                
                volumeStatus.textContent = statusText;
                volumeStatus.style.color = statusColor;
                
                // Cor da barra baseada no status
                if (!hasSignificantVolume) {
                    volumeBar.style.background = '#6c757d';
                } else if (!hasVariation) {
                    volumeBar.style.background = '#ffc107';
                } else {
                    volumeBar.style.background = 'linear-gradient(90deg, #28a745 0%, #ffc107 70%, #dc3545 100%)';
                }
            }
            
            /**
             * Adiciona mensagem ao histórico de chat
             */
            function addChatMessage(text, sender) {
                const chatHistory = document.getElementById('chatHistory');
                
                // Remover mensagem de "aguardando" se existir
                const waitingMsg = chatHistory.querySelector('div[style*="text-align: center"]');
                if (waitingMsg) {
                    waitingMsg.remove();
                }
                
                const messageDiv = document.createElement('div');
                messageDiv.className = 'chat-message ' + sender;
                
                const label = document.createElement('div');
                label.className = 'chat-message-label';
                label.textContent = sender === 'user' ? 'Você' : 'Kora';
                
                const textDiv = document.createElement('div');
                textDiv.textContent = text;
                
                messageDiv.appendChild(label);
                messageDiv.appendChild(textDiv);
                chatHistory.appendChild(messageDiv);
                
                // Scroll para o final
                chatHistory.scrollTop = chatHistory.scrollHeight;
            }
            
            function connect() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    addMessage('Já está conectado!', 'error');
                    return;
                }
                
                addMessage('Conectando ao WebSocket...', 'info');
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function(event) {
                    addMessage('Conectado com sucesso!', 'success');
                    updateStatus(true);
                };
                
                ws.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        
                        // Formatar mensagem baseado no tipo
                        let messageText = '';
                        if (data.type === 'session_start') {
                            messageText = '✅ Sessão iniciada: ' + data.data.session_id;
                        } else if (data.type === 'audio_response') {
                            const audioSize = data.data?.audio ? (data.data.audio.length / 1024).toFixed(2) : '0';
                            messageText = '🔊 Áudio recebido: ' + audioSize + ' KB (Base64)';
                            
                            // Só reproduzir áudio se tivermos uma transcrição válida anterior
                            // (evita reproduzir áudio para ruídos)
                            if (data.data?.audio) {
                                // Verificar se há uma transcrição válida recente
                                // Se não houver, pode ser ruído - não reproduzir
                                playAudioResponse(data.data.audio);
                            }
                        } else if (data.type === 'transcription') {
                            const transcriptionText = data.data?.text || '';
                            
                            // Se estiver em modo STT apenas, mostrar apenas a transcrição (sem diálogo)
                            if (isSTTOnlyMode) {
                                if (transcriptionText.trim().length > 0) {
                                    addMessage('✅ Transcrição: ' + transcriptionText.trim(), 'success');
                                    updateTranscriptionBox(transcriptionText.trim(), false);
                                    addChatMessage(transcriptionText.trim(), 'user');
                                } else {
                                    addMessage('⚠️ Transcrição vazia (possivelmente ruído)', 'warning');
                                }
                                // Parar captura após mostrar transcrição
                                stopSTTCapture();
                                return;
                            }
                            
                            // Validar transcrição: só processar se tiver texto válido
                            if (transcriptionText.trim().length === 0) {
                                messageText = '⚠️ Transcrição vazia (ruído detectado). Ignorando...';
                                addMessage(messageText, 'warning');
                                updateTranscriptionBox('', true); // Limpar transcrição
                                isProcessingUserSpeech = false; // Liberar flag
                                return; // Não processar transcrições vazias
                            }
                            
                            // Validar se o texto não é apenas ruído (muito curto ou sem sentido)
                            if (transcriptionText.trim().length < 5) {
                                messageText = '⚠️ Transcrição muito curta (possível ruído). Ignorando...';
                                addMessage(messageText, 'warning');
                                updateTranscriptionBox('', true); // Limpar transcrição
                                isProcessingUserSpeech = false; // Liberar flag
                                return; // Não processar transcrições muito curtas
                            }
                            
                            // Validar se não é apenas caracteres especiais ou números isolados (ruído)
                            const cleanText = transcriptionText.trim().replace(/[^a-zA-ZáàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ\\s]/g, '');
                            if (cleanText.length < 3) {
                                messageText = '⚠️ Transcrição inválida (apenas ruído). Ignorando...';
                                addMessage(messageText, 'warning');
                                updateTranscriptionBox('', true);
                                isProcessingUserSpeech = false;
                                return;
                            }
                            
                            // É transcrição do usuário - adicionar ao histórico como mensagem do usuário
                            lastUserTranscription = transcriptionText;
                            addChatMessage(transcriptionText, 'user');
                            updateTranscriptionBox(transcriptionText, false);
                            
                            // Liberar flag após um pequeno delay para evitar processamento duplicado
                            setTimeout(() => {
                                isProcessingUserSpeech = false;
                            }, 1000);
                            
                            messageText = '📝 Você falou: ' + transcriptionText;
                        } else if (data.type === 'bot_response') {
                            // RESPOSTA DO BOT (o que o bot respondeu)
                            const botResponseText = data.data?.text || '';
                            
                            if (botResponseText.trim().length > 0) {
                                // Adicionar ao histórico como mensagem do bot
                                addChatMessage(botResponseText, 'bot');
                                messageText = '🤖 Kora respondeu: ' + botResponseText;
                            }
                        } else if (data.type === 'intent') {
                            messageText = '🎯 Intenção: ' + data.data.name + ' (confiança: ' + (data.data.confidence * 100).toFixed(1) + '%)';
                        } else if (data.type === 'error') {
                            messageText = '❌ Erro: ' + data.data.error + ' - ' + data.data.message;
                        } else {
                            messageText = '📨 ' + data.type + ': ' + JSON.stringify(data, null, 2);
                        }
                        
                        addMessage(messageText, data.type === 'error' ? 'error' : 'success');
                    } catch (e) {
                        addMessage('Recebido (não-JSON): ' + event.data.substring(0, 100), 'info');
                    }
                };
                
                ws.onerror = function(error) {
                    addMessage('Erro no WebSocket: ' + error, 'error');
                };
                
                ws.onclose = function(event) {
                    addMessage('Conexão fechada. Código: ' + event.code + ', Razão: ' + event.reason, 'error');
                    updateStatus(false);
                };
            }
            
            function disconnect() {
                stopAudioCapture();
                stopCurrentAudio(); // Parar áudio ao desconectar
                isBotSpeaking = false; // Limpar flag
                if (playbackAudioContext) {
                    playbackAudioContext.close();
                    playbackAudioContext = null;
                }
                if (ws) {
                    ws.close();
                    ws = null;
                    addMessage('Desconectado manualmente', 'info');
                }
            }
            
            let mediaRecorder = null;
            let audioContext = null;
            let sttAudioContext = null; // Contexto de áudio específico para modo STT apenas
            let playbackAudioContext = null;
            let currentAudioSource = null; // Source de áudio atual sendo reproduzido
            let isRecording = false;
            let isSTTOnlyMode = false; // Modo apenas STT (sem diálogo)
            let isBotSpeaking = false; // Flag para indicar que o bot está falando (evita feedback acústico)
            let recordingTimeout = null;
            let timeInterval = null;
            let isUserSpeaking = false;
            let silenceTimer = null;
            let maxSpeechTimer = null; // Timeout máximo de fala contínua
            let silenceChunkCount = 0; // Contador de chunks silenciosos consecutivos
            let lastUserTranscription = null; // Última transcrição do usuário
            let isProcessingUserSpeech = false; // Flag para evitar processar múltiplas vezes
            let speechStartTime = null; // Timestamp do início da fala (para validar duração mínima)
            const RECORDING_DURATION = 120000; // 2 minutos em milissegundos
            const SILENCE_THRESHOLD = 0.04; // Threshold para detectar fala (ajustado para capturar fala normal)
            const BARGE_IN_THRESHOLD = 0.08; // Threshold para barge-in (evita feedback acústico)
            const SILENCE_DURATION = 2000; // 2 segundos de silêncio para enviar
            const MAX_SPEECH_DURATION = 10000; // 10 segundos máximo de fala contínua (força stop_speaking)
            const SILENCE_CHUNKS_THRESHOLD = 30; // Número de chunks silenciosos consecutivos para considerar silêncio
            const MIN_SPEECH_DURATION = 800; // Duração mínima de fala em ms (filtra ruídos muito curtos)
            const MIN_VOLUME_VARIANCE = 0.015; // Variação mínima de volume (fala real tem mais variação que ruído constante)
            
            // Buffer de áudio para teste STT (sempre coletar, independente de threshold)
            let audioBufferForSTT = [];
            const MAX_STT_BUFFER_SIZE = 200; // Máximo de chunks no buffer STT (~10 segundos a 16kHz)
            
            // Histórico de volumes para análise de variação
            let volumeHistory = [];
            const VOLUME_HISTORY_SIZE = 10; // Manter últimos 10 chunks para análise
            
            async function startAudioCapture() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ 
                        audio: {
                            sampleRate: 16000,
                            channelCount: 1,
                            echoCancellation: true,
                            noiseSuppression: true
                        } 
                    });
                    
                    audioContext = new AudioContext({ sampleRate: 16000 });
                    const source = audioContext.createMediaStreamSource(stream);
                    const processor = audioContext.createScriptProcessor(4096, 1, 1);
                    
                    processor.onaudioprocess = (event) => {
                        if (!isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
                        
                        const inputData = event.inputBuffer.getChannelData(0);
                        
                        // Calcular volume RMS (Root Mean Square) - mais preciso que média simples
                        let sumSquares = 0;
                        for (let i = 0; i < inputData.length; i++) {
                            sumSquares += inputData[i] * inputData[i];
                        }
                        const volumeRMS = Math.sqrt(sumSquares / inputData.length);
                        
                        // Calcular variação de volume (fala real tem mais variação que ruído constante)
                        volumeHistory.push(volumeRMS);
                        if (volumeHistory.length > VOLUME_HISTORY_SIZE) {
                            volumeHistory.shift();
                        }
                        
                        let volumeVariance = 0;
                        if (volumeHistory.length >= 3) {
                            const avg = volumeHistory.reduce((a, b) => a + b, 0) / volumeHistory.length;
                            const variance = volumeHistory.reduce((sum, v) => sum + Math.pow(v - avg, 2), 0) / volumeHistory.length;
                            volumeVariance = Math.sqrt(variance);
                        }
                        
                        // Se o bot estiver falando, usar threshold mais alto para barge-in
                        const currentThreshold = isBotSpeaking ? BARGE_IN_THRESHOLD : SILENCE_THRESHOLD;
                        
                        // Validação adicional: volume deve ser significativo E ter variação (fala real)
                        // Ruído constante tem baixa variação, fala real tem alta variação
                        const hasSignificantVolume = volumeRMS > currentThreshold;
                        const hasVariation = volumeHistory.length < 3 || volumeVariance > MIN_VOLUME_VARIANCE;
                        
                        // Atualizar indicador visual de volume (debug)
                        updateVolumeIndicator(volumeRMS, volumeVariance, hasSignificantVolume, hasVariation, currentThreshold);
                        
                        // Detectar início/fim de fala (volume alto E variação significativa)
                        if (hasSignificantVolume && hasVariation) {
                            // Há fala detectada
                            silenceChunkCount = 0; // Resetar contador de silêncio
                            
                            // BARGE-IN: Se o bot estiver falando e detectamos fala forte, parar o bot
                            if (isBotSpeaking && !isUserSpeaking) {
                                stopCurrentAudio();
                                isUserSpeaking = true;
                                speechStartTime = Date.now(); // Registrar início da fala
                                clearTimeout(silenceTimer);
                                ws.send(JSON.stringify({ type: 'start_speaking' }));
                                addMessage('🎤 Você interrompeu o bot (barge-in)...', 'info');
                                
                                // Iniciar timeout máximo de fala
                                clearTimeout(maxSpeechTimer);
                                maxSpeechTimer = setTimeout(() => {
                                    if (isUserSpeaking && isRecording) {
                                        addMessage('⏱️ Fala longa detectada. Processando...', 'info');
                                        isUserSpeaking = false;
                                        speechStartTime = null;
                                        ws.send(JSON.stringify({ type: 'stop_speaking' }));
                                        clearTimeout(silenceTimer);
                                    }
                                }, MAX_SPEECH_DURATION);
                            } else if (!isUserSpeaking && !isBotSpeaking) {
                                // Fala normal quando o bot não está falando
                                isUserSpeaking = true;
                                speechStartTime = Date.now(); // Registrar início da fala
                                clearTimeout(silenceTimer);
                                ws.send(JSON.stringify({ type: 'start_speaking' }));
                                addMessage('🎤 Você começou a falar...', 'info');
                                
                                // Iniciar timeout máximo de fala
                                clearTimeout(maxSpeechTimer);
                                maxSpeechTimer = setTimeout(() => {
                                    if (isUserSpeaking && isRecording) {
                                        addMessage('⏱️ Fala longa detectada. Processando...', 'info');
                                        isUserSpeaking = false;
                                        speechStartTime = null;
                                        ws.send(JSON.stringify({ type: 'stop_speaking' }));
                                        clearTimeout(silenceTimer);
                                    }
                                }, MAX_SPEECH_DURATION);
                            }
                            
                            // Limpar timer de silêncio
                            clearTimeout(silenceTimer);
                            
                            // SEMPRE converter e coletar áudio (para buffer STT e envio normal)
                            // Converter Float32 para Int16 PCM
                            const int16Array = new Int16Array(inputData.length);
                            for (let i = 0; i < inputData.length; i++) {
                                const s = Math.max(-1, Math.min(1, inputData[i]));
                                int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                            }
                            
                            // Converter para Base64
                            const base64 = btoa(String.fromCharCode(...new Uint8Array(int16Array.buffer)));
                            
                            // SEMPRE adicionar ao buffer STT (para teste STT funcionar)
                            audioBufferForSTT.push(base64);
                            if (audioBufferForSTT.length > MAX_STT_BUFFER_SIZE) {
                                audioBufferForSTT.shift(); // Remover chunks mais antigos
                            }
                            
                            // Só enviar chunks de áudio ao backend se o usuário estiver falando E o bot não estiver falando
                            // E não estiver processando uma fala anterior (evita loops)
                            if (isUserSpeaking && !isBotSpeaking && !isProcessingUserSpeech) {
                                // Enviar chunk de áudio
                                const audioMessage = {
                                    type: 'audio_chunk',
                                    data: { audio: base64 }
                                };
                                ws.send(JSON.stringify(audioMessage));
                            }
                        } else {
                            // Silêncio detectado
                            silenceChunkCount++;
                            
                            if (isUserSpeaking && !isBotSpeaking) {
                                // Validar duração mínima de fala antes de processar
                                const speechDuration = speechStartTime ? Date.now() - speechStartTime : 0;
                                
                                // Se detectou muitos chunks silenciosos consecutivos, processar imediatamente
                                if (silenceChunkCount >= SILENCE_CHUNKS_THRESHOLD) {
                                    // Só processar se a fala durou tempo suficiente (filtra ruídos curtos)
                                    if (speechDuration >= MIN_SPEECH_DURATION && !isProcessingUserSpeech) {
                                        isProcessingUserSpeech = true; // Marcar como processando para evitar loops
                                        clearTimeout(silenceTimer);
                                        clearTimeout(maxSpeechTimer);
                                        isUserSpeaking = false;
                                        speechStartTime = null;
                                        silenceChunkCount = 0;
                                        ws.send(JSON.stringify({ type: 'stop_speaking' }));
                                        addMessage('🔇 Silêncio detectado. Processando...', 'info');
                                    } else if (speechDuration < MIN_SPEECH_DURATION) {
                                        // Fala muito curta, provavelmente ruído - descartar
                                        clearTimeout(silenceTimer);
                                        clearTimeout(maxSpeechTimer);
                                        isUserSpeaking = false;
                                        speechStartTime = null;
                                        silenceChunkCount = 0;
                                        addMessage('🔇 Ruído detectado (fala muito curta). Descartando...', 'info');
                                    }
                                } else {
                                    // Iniciar timer de silêncio (fallback)
                                    clearTimeout(silenceTimer);
                                    silenceTimer = setTimeout(() => {
                                        if (isUserSpeaking && isRecording && !isBotSpeaking) {
                                            const finalSpeechDuration = speechStartTime ? Date.now() - speechStartTime : 0;
                                            
                                            // Só processar se a fala durou tempo suficiente e não estiver processando
                                            if (finalSpeechDuration >= MIN_SPEECH_DURATION && !isProcessingUserSpeech) {
                                                isProcessingUserSpeech = true; // Marcar como processando
                                                isUserSpeaking = false;
                                                speechStartTime = null;
                                                silenceChunkCount = 0;
                                                clearTimeout(maxSpeechTimer);
                                                ws.send(JSON.stringify({ type: 'stop_speaking' }));
                                                addMessage('🔇 Silêncio detectado. Processando...', 'info');
                                            } else if (finalSpeechDuration < MIN_SPEECH_DURATION) {
                                                // Fala muito curta, descartar
                                                isUserSpeaking = false;
                                                speechStartTime = null;
                                                silenceChunkCount = 0;
                                                clearTimeout(maxSpeechTimer);
                                                addMessage('🔇 Ruído detectado (fala muito curta). Descartando...', 'info');
                                            }
                                        }
                                    }, SILENCE_DURATION);
                                }
                            }
                        }
                    };
                    
                    source.connect(processor);
                    processor.connect(audioContext.destination);
                    
                    isRecording = true;
                    isUserSpeaking = false;
                    silenceChunkCount = 0;
                    audioBufferForSTT = []; // Limpar buffer STT ao iniciar nova captura
                    const startTime = Date.now();
                    updateRecordingStatus(true);
                    addMessage('✅ Captura de áudio iniciada. Você tem 2 minutos para conversar!', 'success');
                    addMessage('💡 Dica: Fale naturalmente. O sistema detecta quando você para de falar.', 'info');
                    addMessage('💡 Dica: Use o botão "Parar Captura" se quiser processar manualmente.', 'info');
                    
                    // Atualizar contador de tempo restante
                    timeInterval = setInterval(() => {
                        if (!isRecording) {
                            clearInterval(timeInterval);
                            timeInterval = null;
                    return;
                }
                        const elapsed = Date.now() - startTime;
                        const remaining = Math.max(0, RECORDING_DURATION - elapsed);
                        const remainingSeconds = Math.floor(remaining / 1000);
                        const remainingMinutes = Math.floor(remainingSeconds / 60);
                        const seconds = remainingSeconds % 60;
                        
                        // Mostrar tempo restante a cada 30 segundos
                        if (remaining > 0 && remaining % 30000 < 1000) {
                            addMessage(`⏱️ Tempo restante: ${remainingMinutes}:${seconds.toString().padStart(2, '0')}`, 'info');
                        }
                    }, 1000);
                    
                    // Parar após 2 minutos
                    recordingTimeout = setTimeout(() => {
                        if (isRecording) {
                            if (timeInterval) {
                                clearInterval(timeInterval);
                                timeInterval = null;
                            }
                            if (isUserSpeaking) {
                                isUserSpeaking = false;
                                ws.send(JSON.stringify({ type: 'stop_speaking' }));
                            }
                            stopAudioCapture();
                            updateRecordingStatus(false);
                            addMessage('⏱️ Tempo de 2 minutos esgotado. Captura finalizada.', 'info');
                        }
                    }, RECORDING_DURATION);
                    
                } catch (error) {
                    addMessage('Erro ao acessar microfone: ' + error.message, 'error');
                }
            }
            
            function stopAudioCapture() {
                if (!isRecording) return; // Já está parado
                
                isRecording = false;
                updateRecordingStatus(false);
                
                // Limpar timers
                if (recordingTimeout) {
                    clearTimeout(recordingTimeout);
                    recordingTimeout = null;
                }
                if (timeInterval) {
                    clearInterval(timeInterval);
                    timeInterval = null;
                }
                if (silenceTimer) {
                    clearTimeout(silenceTimer);
                    silenceTimer = null;
                }
                if (maxSpeechTimer) {
                    clearTimeout(maxSpeechTimer);
                    maxSpeechTimer = null;
                }
                
                // Enviar stop_speaking se ainda estiver falando
                if (ws && ws.readyState === WebSocket.OPEN && isUserSpeaking) {
                    isUserSpeaking = false;
                    ws.send(JSON.stringify({ type: 'stop_speaking' }));
                    addMessage('🛑 Captura parada. Processando último áudio...', 'info');
                }
                
                silenceChunkCount = 0;
                
                if (audioContext) {
                    audioContext.close();
                    audioContext = null;
                }
            }
            
            /**
             * Para o áudio atual que está sendo reproduzido (para barge-in e evitar sobreposição)
             */
            function stopCurrentAudio() {
                if (currentAudioSource) {
                    try {
                        currentAudioSource.stop();
                        currentAudioSource.disconnect();
                        currentAudioSource = null;
                        isBotSpeaking = false; // Bot parou de falar, pode retomar captura
                        addMessage('⏹️ Áudio interrompido', 'info');
                    } catch (error) {
                        // Source já pode ter terminado naturalmente
                        currentAudioSource = null;
                        isBotSpeaking = false;
                    }
                } else {
                    isBotSpeaking = false; // Garantir que a flag está limpa
                }
            }
            
            /**
             * Reproduz áudio recebido do servidor (PCM 16-bit @ 16kHz em Base64)
             */
            async function playAudioResponse(audioBase64) {
                try {
                    // PARAR qualquer áudio anterior que esteja tocando (evita sobreposição)
                    stopCurrentAudio();
                    
                    // Criar AudioContext para reprodução se não existir
                    if (!playbackAudioContext) {
                        playbackAudioContext = new AudioContext({ sampleRate: 16000 });
                    }
                    
                    // Resumir AudioContext se estiver suspenso (alguns navegadores suspendem até interação do usuário)
                    if (playbackAudioContext.state === 'suspended') {
                        await playbackAudioContext.resume();
                    }
                    
                    // Decodificar Base64 para ArrayBuffer
                    const binaryString = atob(audioBase64);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    
                    // Converter Int16 PCM para Float32
                    // Criar Int16Array a partir dos bytes (2 bytes por sample)
                    const sampleCount = Math.floor(bytes.length / 2);
                    const int16Array = new Int16Array(sampleCount);
                    const dataView = new DataView(bytes.buffer);
                    for (let i = 0; i < sampleCount; i++) {
                        // Ler Int16 little-endian (padrão do PCM)
                        int16Array[i] = dataView.getInt16(i * 2, true);
                    }
                    
                    const float32Array = new Float32Array(sampleCount);
                    for (let i = 0; i < sampleCount; i++) {
                        // Normalizar de Int16 (-32768 a 32767) para Float32 (-1.0 a 1.0)
                        float32Array[i] = Math.max(-1, Math.min(1, int16Array[i] / 32768.0));
                    }
                    
                    // Criar AudioBuffer
                    const audioBuffer = playbackAudioContext.createBuffer(
                        1, // Mono
                        float32Array.length,
                        16000 // Sample rate
                    );
                    
                    // Copiar dados para o buffer
                    audioBuffer.getChannelData(0).set(float32Array);
                    
                    // Criar source e reproduzir
                    const source = playbackAudioContext.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(playbackAudioContext.destination);
                    
                    // Guardar referência para poder parar depois
                    currentAudioSource = source;
                    
                    // MARCAR que o bot está falando (pausa captura para evitar feedback)
                    isBotSpeaking = true;
                    window.lastBotSpeechTime = Date.now(); // Registrar início da fala do bot
                    
                    source.onended = () => {
                        if (currentAudioSource === source) {
                            currentAudioSource = null;
                            isBotSpeaking = false; // Bot parou de falar, pode retomar captura
                            window.lastBotSpeechTime = Date.now(); // Atualizar tempo quando bot termina
                            // Adicionar pequeno delay antes de retomar captura (evita capturar eco)
                            setTimeout(() => {
                                isProcessingUserSpeech = false; // Garantir que flag está limpa
                            }, 500);
                            addMessage('✅ Áudio reproduzido com sucesso', 'success');
                        }
                    };
                    
                    source.start(0);
                    addMessage('▶️ Reproduzindo áudio...', 'info');
                    
                } catch (error) {
                    addMessage('❌ Erro ao reproduzir áudio: ' + error.message, 'error');
                    console.error('Erro ao reproduzir áudio:', error);
                    currentAudioSource = null;
                }
            }
            
            function sendTextMessage() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    addMessage('❌ Não conectado ao WebSocket', 'error');
                    return;
                }
                
                const textInput = document.getElementById('textInput');
                const text = textInput.value.trim();
                
                if (!text) {
                    addMessage('⚠️ Digite uma mensagem antes de enviar', 'warning');
                    return;
                }
                
                // Enviar mensagem de texto
                ws.send(JSON.stringify({
                    type: 'text_message',
                    data: { text: text }
                }));
                
                // Limpar campo de texto
                textInput.value = '';
                addMessage('📤 Mensagem de texto enviada: ' + text, 'info');
            }
            
            async function testSTTOnly() {
                console.log('testSTTOnly chamado');
                
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    addMessage('❌ Não conectado ao WebSocket', 'error');
                    console.error('WebSocket não está conectado');
                    return;
                }
                
                // Se já estiver em modo STT, parar
                if (isSTTOnlyMode) {
                    console.log('Parando modo STT');
                    stopSTTCapture();
                    return;
                }
                
                console.log('Iniciando modo STT apenas');
                addMessage('🎙️ Iniciando modo STT...', 'info');
                
                // Iniciar modo STT apenas
                isSTTOnlyMode = true;
                audioBufferForSTT = []; // Limpar buffer
                window.sttLastProcessedIndex = 0; // Resetar índice de processamento
                
                try {
                    console.log('Solicitando acesso ao microfone...');
                    addMessage('📱 Solicitando permissão de microfone...', 'info');
                    
                    // Verificar se getUserMedia está disponível
                    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                        throw new Error('getUserMedia não está disponível neste navegador. Use HTTPS ou localhost.');
                    }
                    
                    const stream = await navigator.mediaDevices.getUserMedia({ 
                        audio: {
                            sampleRate: 16000,
                            channelCount: 1,
                            echoCancellation: true,
                            noiseSuppression: true
                        } 
                    });
                    
                    console.log('Microfone acessado com sucesso:', stream);
                    addMessage('✅ Microfone ativado!', 'success');
                    
                    // Verificar se o stream está ativo
                    if (!stream.active) {
                        throw new Error('Stream de áudio não está ativo');
                    }
                    
                    // Fechar contexto anterior se existir
                    if (sttAudioContext) {
                        try {
                            await sttAudioContext.close();
                        } catch (e) {
                            console.warn('Erro ao fechar contexto anterior:', e);
                        }
                    }
                    
                    // Criar novo contexto de áudio
                    sttAudioContext = new AudioContext({ sampleRate: 16000 });
                    
                    // Verificar se o contexto está em estado suspenso (comum em navegadores)
                    if (sttAudioContext.state === 'suspended') {
                        console.log('AudioContext suspenso, resumindo...');
                        await sttAudioContext.resume();
                    }
                    
                    console.log('AudioContext criado:', sttAudioContext.state);
                    const source = sttAudioContext.createMediaStreamSource(stream);
                    const processor = sttAudioContext.createScriptProcessor(4096, 1, 1);
                    
                    // Armazenar stream para evitar garbage collection
                    window.sttStream = stream;
                    
                    let sttSilenceChunkCount = 0;
                    let sttIsSpeaking = false;
                    let sttSpeechStartTime = null;
                    let sttLastTranscriptionTime = null;
                    const STT_SILENCE_THRESHOLD = 0.04;
                    const STT_SILENCE_CHUNKS = 60; // ~3 segundos de silêncio para finalizar (quando realmente parar de falar)
                    const STT_MAX_DURATION = 120000; // 2 minutos em milissegundos
                    const STT_PARTIAL_INTERVAL = 10000; // 10 segundos de fala para transcrição parcial
                    
                    // Limpar timers anteriores se existirem
                    if (window.sttMaxDurationTimer) {
                        clearTimeout(window.sttMaxDurationTimer);
                        window.sttMaxDurationTimer = null;
                    }
                    if (window.sttPartialTimer) {
                        clearInterval(window.sttPartialTimer);
                        window.sttPartialTimer = null;
                    }
                    
                    processor.onaudioprocess = (event) => {
                        if (!isSTTOnlyMode || !ws || ws.readyState !== WebSocket.OPEN) return;
                        
                        const inputData = event.inputBuffer.getChannelData(0);
                        
                        // Calcular volume RMS
                        let sumSquares = 0;
                        for (let i = 0; i < inputData.length; i++) {
                            sumSquares += inputData[i] * inputData[i];
                        }
                        const volumeRMS = Math.sqrt(sumSquares / inputData.length);
                        
                        // Converter para PCM e adicionar ao buffer
                        const int16Array = new Int16Array(inputData.length);
                        for (let i = 0; i < inputData.length; i++) {
                            const s = Math.max(-1, Math.min(1, inputData[i]));
                            int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                        }
                        const base64 = btoa(String.fromCharCode(...new Uint8Array(int16Array.buffer)));
                        audioBufferForSTT.push(base64);
                        
                        // Detectar fala
                        if (volumeRMS > STT_SILENCE_THRESHOLD) {
                            sttSilenceChunkCount = 0;
                            if (!sttIsSpeaking) {
                                sttIsSpeaking = true;
                                sttSpeechStartTime = Date.now();
                                sttLastTranscriptionTime = Date.now();
                                window.sttLastProcessedIndex = 0; // Resetar índice ao começar a falar (global)
                                addMessage('🎤 Gravando para STT...', 'info');
                                
                                // Iniciar timer de duração máxima (2 minutos)
                                if (window.sttMaxDurationTimer) {
                                    clearTimeout(window.sttMaxDurationTimer);
                                }
                                window.sttMaxDurationTimer = setTimeout(() => {
                                    if (isSTTOnlyMode && sttIsSpeaking) {
                                        addMessage('⏱️ Tempo máximo de 2 minutos atingido. Finalizando transcrição...', 'info');
                                        sttIsSpeaking = false;
                                        if (window.sttPartialTimer) {
                                            clearInterval(window.sttPartialTimer);
                                            window.sttPartialTimer = null;
                                        }
                                        processSTTOnly(true); // Final = true
                                    }
                                }, STT_MAX_DURATION);
                                
                                // Iniciar timer para transcrições parciais a cada 10 segundos de fala
                                if (window.sttPartialTimer) {
                                    clearInterval(window.sttPartialTimer);
                                }
                                window.sttPartialTimer = setInterval(() => {
                                    if (isSTTOnlyMode && sttIsSpeaking && audioBufferForSTT.length > sttLastProcessedIndex) {
                                        const now = Date.now();
                                        const timeSinceLastTranscription = now - sttLastTranscriptionTime;
                                        if (timeSinceLastTranscription >= STT_PARTIAL_INTERVAL) {
                                            sttLastTranscriptionTime = now;
                                            addMessage('📝 Transcrição parcial (a cada 10s de fala)...', 'info');
                                            processSTTOnly(false); // Parcial = false (não limpa tudo)
                                        }
                                    }
                                }, STT_PARTIAL_INTERVAL);
                            }
                        } else {
                            sttSilenceChunkCount++;
                            // Só finalizar se realmente parou de falar (silêncio de ~3 segundos)
                            // E se já estava falando (não processar se nunca falou)
                            if (sttIsSpeaking && sttSilenceChunkCount >= STT_SILENCE_CHUNKS) {
                                // Parou de falar por tempo suficiente, finalizar STT
                                sttIsSpeaking = false;
                                if (window.sttMaxDurationTimer) {
                                    clearTimeout(window.sttMaxDurationTimer);
                                    window.sttMaxDurationTimer = null;
                                }
                                if (window.sttPartialTimer) {
                                    clearInterval(window.sttPartialTimer);
                                    window.sttPartialTimer = null;
                                }
                                processSTTOnly(true); // Final = true (processa tudo e limpa)
                            }
                        }
                    };
                    
                    source.connect(processor);
                    processor.connect(sttAudioContext.destination);
                    
                    const testSTTBtn = document.getElementById('testSTTBtn');
                    const stopSTTBtn = document.getElementById('stopSTTBtn');
                    if (testSTTBtn) testSTTBtn.disabled = true;
                    if (stopSTTBtn) {
                        stopSTTBtn.disabled = false;
                        stopSTTBtn.style.display = 'inline-block';
                    }
                    addMessage('🎙️ Modo STT ativado. Fale algo...', 'success');
                    addMessage('💡 Você pode falar por até 2 minutos. O sistema transcreverá a cada 10 segundos de fala e finalizará quando você parar de falar.', 'info');
                    console.log('Modo STT configurado com sucesso');
                    
                } catch (error) {
                    console.error('Erro ao iniciar modo STT:', error);
                    console.error('Detalhes do erro:', {
                        name: error.name,
                        message: error.message,
                        stack: error.stack
                    });
                    
                    let errorMsg = '❌ Erro ao acessar microfone: ';
                    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                        errorMsg += 'Permissão de microfone negada. Por favor, permita o acesso ao microfone nas configurações do navegador.';
                    } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                        errorMsg += 'Nenhum microfone encontrado. Verifique se há um microfone conectado.';
                    } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
                        errorMsg += 'Microfone está sendo usado por outro aplicativo. Feche outros aplicativos que usam o microfone.';
                    } else {
                        errorMsg += error.message;
                    }
                    
                    addMessage(errorMsg, 'error');
                    isSTTOnlyMode = false;
                    
                    // Reabilitar botão em caso de erro
                    const testSTTBtn = document.getElementById('testSTTBtn');
                    const stopSTTBtn = document.getElementById('stopSTTBtn');
                    if (testSTTBtn) testSTTBtn.disabled = false;
                    if (stopSTTBtn) {
                        stopSTTBtn.disabled = true;
                        stopSTTBtn.style.display = 'none';
                    }
                }
            }
            
            async function stopSTTCapture() {
                console.log('stopSTTCapture chamado');
                isSTTOnlyMode = false;
                
                // Limpar timers
                if (window.sttMaxDurationTimer) {
                    clearTimeout(window.sttMaxDurationTimer);
                    window.sttMaxDurationTimer = null;
                }
                if (window.sttPartialTimer) {
                    clearInterval(window.sttPartialTimer);
                    window.sttPartialTimer = null;
                }
                window.sttLastProcessedIndex = 0; // Resetar índice
                
                // Parar todas as tracks do stream
                if (window.sttStream) {
                    window.sttStream.getTracks().forEach(track => {
                        track.stop();
                        console.log('Track parada:', track.kind);
                    });
                    window.sttStream = null;
                }
                
                // Fechar contexto de áudio
                if (sttAudioContext) {
                    try {
                        await sttAudioContext.close();
                        console.log('AudioContext fechado');
                } catch (e) {
                        console.warn('Erro ao fechar AudioContext:', e);
                    }
                    sttAudioContext = null;
                }
                
                const testSTTBtn = document.getElementById('testSTTBtn');
                const stopSTTBtn = document.getElementById('stopSTTBtn');
                if (testSTTBtn) testSTTBtn.disabled = false;
                if (stopSTTBtn) {
                    stopSTTBtn.disabled = true;
                    stopSTTBtn.style.display = 'none';
                }
                addMessage('⏹️ Captura STT parada', 'info');
            }
            
            function processSTTOnly(isFinal = false) {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    return;
                }
                
                // Determinar quais chunks processar
                let startIndex = 0;
                let endIndex = audioBufferForSTT.length;
                
                if (!isFinal && typeof window.sttLastProcessedIndex !== 'undefined') {
                    // Transcrição parcial: processar apenas novos chunks desde a última transcrição
                    startIndex = window.sttLastProcessedIndex;
                }
                
                if (startIndex >= endIndex) {
                    // Nenhum chunk novo para processar
                    return;
                }
                
                addMessage('🎙️ Processando transcrição...', 'info');
                
                // Enviar start_speaking
                ws.send(JSON.stringify({ type: 'start_speaking' }));
                
                // Enviar apenas os chunks novos (ou todos se for final)
                for (let i = startIndex; i < endIndex; i++) {
                    const audioMessage = {
                        type: 'audio_chunk',
                        data: { audio: audioBufferForSTT[i] }
                    };
                    ws.send(JSON.stringify(audioMessage));
                }
                
                // Enviar stop_speaking
                ws.send(JSON.stringify({ type: 'stop_speaking' }));
                
                // Atualizar índice do último chunk processado
                if (typeof window.sttLastProcessedIndex === 'undefined') {
                    window.sttLastProcessedIndex = 0;
                }
                window.sttLastProcessedIndex = endIndex;
                
                // Se for final, limpar buffer completamente
                if (isFinal) {
                    audioBufferForSTT = [];
                    window.sttLastProcessedIndex = 0;
                }
                
                // Enviar comando para testar apenas STT
                setTimeout(() => {
                    ws.send(JSON.stringify({ type: 'test_stt' }));
                }, 500);
            }
            
            function sendTestMessage() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    addMessage('Não está conectado!', 'error');
                    return;
                }
                
                // Se já estiver gravando, parar primeiro
                if (isRecording) {
                    addMessage('⏹️ Parando captura atual...', 'info');
                    stopAudioCapture();
                    setTimeout(() => {
                        addMessage('Iniciando novo teste de áudio (2 minutos)...', 'info');
                        startAudioCapture();
                    }, 1000);
                } else {
                    addMessage('Iniciando teste de áudio (2 minutos)...', 'info');
                    startAudioCapture();
                }
            }
            
            // Inicializar status
            updateStatus(false);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.websocket("/ws/voice-chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket para chat por voz em tempo real.
    
    Mensagens esperadas do cliente:
    - {"type": "audio_chunk", "data": {"audio": "base64..."}}
    - {"type": "start_speaking"}
    - {"type": "stop_speaking"}
    - {"type": "barge_in"}
    
    Mensagens enviadas ao cliente:
    - {"type": "audio_response", "data": {"audio": "base64..."}}
    - {"type": "transcription", "data": {"text": "..."}}
    - {"type": "intent", "data": {"intent": "...", "confidence": 0.95}}
    - {"type": "tool_call", "data": {"tool": "...", "parameters": {...}}}
    - {"type": "error", "data": {"error": "...", "message": "..."}}
    """
    session_id = None
    
    try:
        # Conectar e criar sessão
        session_id = await websocket_manager.connect(websocket)
        
        # Loop principal de mensagens
        while True:
            try:
                # Receber mensagem do cliente
                message = await websocket.receive_json()
                
                # Processar mensagem
                await websocket_manager.handle_message(session_id, message)
            
            except WebSocketDisconnect:
                logger.info(f"Cliente desconectado: {session_id}")
                break
            
            except Exception as e:
                logger.error(f"Erro ao processar mensagem WebSocket: {e}")
                if session_id:
                    session = websocket_manager.get_session(session_id)
                    if session:
                        await session.send_error("websocket_error", str(e))
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket desconectado: {session_id}")
    
    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}")
    
    finally:
        # Limpar sessão
        if session_id:
            await websocket_manager.disconnect(session_id)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )

