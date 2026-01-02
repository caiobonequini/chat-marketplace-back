"""Aplicação principal FastAPI com WebSocket."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn

from config import settings
from websocket_handler import websocket_manager
from utils.logger import setup_logging, get_logger

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
                <button onclick="sendTestMessage()" id="testBtn" disabled>Enviar Mensagem de Teste</button>
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
                
                if (connected) {
                    statusEl.textContent = 'Conectado';
                    statusEl.className = 'status connected';
                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
                    testBtn.disabled = false;
                } else {
                    statusEl.textContent = 'Desconectado';
                    statusEl.className = 'status disconnected';
                    connectBtn.disabled = false;
                    disconnectBtn.disabled = true;
                    testBtn.disabled = true;
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
                        addMessage('Recebido: ' + JSON.stringify(data, null, 2), 'success');
                    } catch (e) {
                        addMessage('Recebido: ' + event.data, 'success');
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
                if (ws) {
                    ws.close();
                    ws = null;
                    addMessage('Desconectado manualmente', 'info');
                }
            }
            
            function sendTestMessage() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    addMessage('Não está conectado!', 'error');
                    return;
                }
                
                const testMessage = {
                    type: 'start_speaking',
                    session_id: null
                };
                
                try {
                    ws.send(JSON.stringify(testMessage));
                    addMessage('Enviado: ' + JSON.stringify(testMessage), 'info');
                } catch (e) {
                    addMessage('Erro ao enviar: ' + e.message, 'error');
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

