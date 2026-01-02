"""Handler WebSocket para chat em tempo real."""
import asyncio
import json
import uuid
import time
from typing import Dict, Optional, Set
from collections import deque
from fastapi import WebSocket, WebSocketDisconnect

from config import settings
from models.messages import (
    MessageType,
    ClientMessage,
    ServerMessage,
    AudioResponseMessage,
    TranscriptionMessage,
    IntentMessage,
    ToolCallMessage,
    ErrorMessage,
)
from dialogflow_service import DialogflowService
from vad_service import VADService
from audio_processor import AudioProcessor
from tts_service import TTSService
from tools.products import ProductsTool
from utils.logger import get_logger

logger = get_logger(__name__)


class VoiceChatSession:
    """Sessão de chat por voz."""
    
    def __init__(self, session_id: str, websocket: WebSocket):
        """Inicializa uma sessão de chat."""
        self.session_id = session_id
        self.websocket = websocket
        self.dialogflow = DialogflowService()
        self.tts = TTSService()
        self.vad = VADService(
            sample_rate=settings.sample_rate,
            aggressiveness=settings.vad_aggressiveness
        )
        self.audio_processor = AudioProcessor()
        self.products_tool = ProductsTool()
        
        # Estado da sessão
        self.is_speaking = False
        self.is_bot_speaking = False
        self.audio_buffer = deque(maxlen=100)  # Buffer de áudio
        self.current_stream_task: Optional[asyncio.Task] = None
        self.barge_in_flag = asyncio.Event()
        
        logger.info(f"Sessão criada: {session_id}")
    
    async def initialize(self):
        """Inicializa a sessão."""
        await self.dialogflow.initialize()
        await self.tts.initialize()
        logger.info(f"Sessão inicializada: {self.session_id}")
    
    async def send_message(self, message: ServerMessage):
        """Envia mensagem para o cliente."""
        try:
            message_dict = message.model_dump(exclude_none=True)
            if message.timestamp is None:
                message_dict['timestamp'] = time.time()
            await self.websocket.send_json(message_dict)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
    
    async def send_error(self, error: str, details: str = ""):
        """Envia mensagem de erro."""
        error_msg = ErrorMessage(
            type=MessageType.ERROR,
            session_id=self.session_id,
            data={'error': error, 'message': details}
        )
        await self.send_message(error_msg)
    
    async def handle_audio_chunk(self, audio_base64: str):
        """Processa chunk de áudio recebido."""
        try:
            # Decodificar áudio
            audio_bytes = self.audio_processor.base64_to_bytes(audio_base64)
            
            # Adicionar ao buffer
            self.audio_buffer.append(audio_bytes)
            
            # Detectar se há fala
            is_speech = self.vad.is_speech(audio_bytes)
            
            if is_speech and not self.is_speaking:
                # Usuário começou a falar
                self.is_speaking = True
                logger.info(f"Sessão {self.session_id}: Usuário começou a falar")
                
                # Se o bot estiver falando, ativar barge-in
                if self.is_bot_speaking:
                    logger.info(f"Sessão {self.session_id}: Barge-in ativado")
                    self.barge_in_flag.set()
                    self.is_bot_speaking = False
                    # Cancelar stream atual se existir
                    if self.current_stream_task and not self.current_stream_task.done():
                        self.current_stream_task.cancel()
            
            elif not is_speech and self.is_speaking:
                # Verificar se é silêncio prolongado
                # Por enquanto, vamos processar quando receber stop_speaking
                pass
            
        except Exception as e:
            logger.error(f"Erro ao processar chunk de áudio: {e}")
            await self.send_error("audio_processing_error", str(e))
    
    async def handle_start_speaking(self):
        """Handle quando usuário começa a falar."""
        self.is_speaking = True
        logger.info(f"Sessão {self.session_id}: Usuário começou a falar")
        
        # Se o bot estiver falando, ativar barge-in
        if self.is_bot_speaking:
            logger.info(f"Sessão {self.session_id}: Barge-in ativado")
            self.barge_in_flag.set()
            self.is_bot_speaking = False
            if self.current_stream_task and not self.current_stream_task.done():
                self.current_stream_task.cancel()
    
    async def handle_stop_speaking(self):
        """Handle quando usuário para de falar."""
        if not self.is_speaking:
            return
        
        self.is_speaking = False
        logger.info(f"Sessão {self.session_id}: Usuário parou de falar")
        
        # Processar áudio acumulado
        if len(self.audio_buffer) > 0:
            await self.process_audio_stream()
    
    async def handle_barge_in(self):
        """Handle interrupção explícita do usuário."""
        logger.info(f"Sessão {self.session_id}: Barge-in explícito")
        self.barge_in_flag.set()
        self.is_bot_speaking = False
        self.is_speaking = True
        
        if self.current_stream_task and not self.current_stream_task.done():
            self.current_stream_task.cancel()
    
    async def process_audio_stream(self):
        """Processa stream de áudio acumulado."""
        if len(self.audio_buffer) == 0:
            return
        
        # Limpar flag de barge-in
        self.barge_in_flag.clear()
        
        # Criar async iterator de chunks
        async def audio_chunks_generator():
            """Gera chunks de áudio do buffer."""
            for chunk in list(self.audio_buffer):
                # Verificar barge-in
                if self.barge_in_flag.is_set():
                    logger.info(f"Sessão {self.session_id}: Barge-in durante processamento")
                    break
                yield chunk
            # Limpar buffer após processar
            self.audio_buffer.clear()
        
        # Processar com Dialogflow
        try:
            self.current_stream_task = asyncio.create_task(
                self._process_dialogflow_stream(audio_chunks_generator())
            )
            await self.current_stream_task
        except asyncio.CancelledError:
            logger.info(f"Sessão {self.session_id}: Stream cancelado por barge-in")
        except Exception as e:
            logger.error(f"Erro ao processar stream: {e}")
            await self.send_error("stream_processing_error", str(e))
    
    async def _process_dialogflow_stream(self, audio_chunks):
        """Processa stream com Dialogflow."""
        try:
            self.is_bot_speaking = True
            
            async for response in self.dialogflow.streaming_detect_intent(
                session_id=self.session_id,
                audio_chunks=audio_chunks,
                sample_rate=settings.sample_rate
            ):
                # Verificar barge-in
                if self.barge_in_flag.is_set():
                    logger.info(f"Sessão {self.session_id}: Barge-in durante resposta")
                    break
                
                # Processar resposta
                if 'error' in response:
                    await self.send_error("dialogflow_error", response['error'])
                    continue
                
                # Enviar transcrição se houver
                if 'text' in response:
                    transcription_msg = TranscriptionMessage(
                        type=MessageType.TRANSCRIPTION,
                        session_id=self.session_id,
                        data={'text': response['text']}
                    )
                    await self.send_message(transcription_msg)
                
                # Enviar intenção se houver
                if 'intent' in response:
                    intent_msg = IntentMessage(
                        type=MessageType.INTENT,
                        session_id=self.session_id,
                        data=response['intent']
                    )
                    await self.send_message(intent_msg)
                
                # Processar chamadas de ferramentas
                if 'payload' in response:
                    payload = response['payload']
                    if 'tool_calls' in payload:
                        await self._handle_tool_calls(payload['tool_calls'])
                
                # Gerar áudio usando Vertex AI TTS
                # Usamos apenas Vertex AI TTS para melhor controle e streaming
                audio_data = None
                
                if 'text' in response and response['text']:
                    try:
                        logger.info(f"Convertendo texto para áudio com Vertex AI TTS: {response['text']}")
                        audio_data = await self.tts.synthesize_speech(response['text'])
                        logger.debug(f"Áudio sintetizado: {len(audio_data)} bytes")
                    except Exception as e:
                        logger.error(f"Erro ao sintetizar fala: {e}")
                        # Continuar sem áudio se TTS falhar
                
                # Enviar áudio se disponível
                if audio_data:
                    audio_base64 = self.audio_processor.bytes_to_base64(audio_data)
                    audio_msg = AudioResponseMessage(
                        type=MessageType.AUDIO_RESPONSE,
                        session_id=self.session_id,
                        data={'audio': audio_base64}
                    )
                    await self.send_message(audio_msg)
            
            self.is_bot_speaking = False
            
        except Exception as e:
            logger.error(f"Erro ao processar stream Dialogflow: {e}")
            self.is_bot_speaking = False
            await self.send_error("dialogflow_stream_error", str(e))
    
    async def _handle_tool_calls(self, tool_calls: list):
        """Processa chamadas de ferramentas."""
        for tool_call in tool_calls:
            tool_name = tool_call.get('name', '')
            parameters = tool_call.get('parameters', {})
            
            logger.info(
                f"Sessão {self.session_id}: Chamando ferramenta "
                f"{tool_name} com parâmetros {parameters}"
            )
            
            # Enviar notificação de chamada de ferramenta
            tool_call_msg = ToolCallMessage(
                type=MessageType.TOOL_CALL,
                session_id=self.session_id,
                data={
                    'tool': tool_name,
                    'parameters': parameters
                }
            )
            await self.send_message(tool_call_msg)
            
            # Executar ferramenta
            if tool_name == "search_products":
                result = await self.products_tool.search_products(
                    query=parameters.get('query'),
                    category=parameters.get('category'),
                    min_price=parameters.get('min_price'),
                    max_price=parameters.get('max_price'),
                    limit=parameters.get('limit', 10)
                )
                
                # Enviar resultado (pode ser usado para continuar conversa)
                logger.info(f"Resultado da ferramenta: {result}")
    
    async def cleanup(self):
        """Limpa recursos da sessão."""
        if self.current_stream_task and not self.current_stream_task.done():
            self.current_stream_task.cancel()
        self.audio_buffer.clear()
        logger.info(f"Sessão {self.session_id}: Limpeza concluída")


class WebSocketManager:
    """Gerenciador de conexões WebSocket."""
    
    def __init__(self):
        """Inicializa o gerenciador."""
        self.active_sessions: Dict[str, VoiceChatSession] = {}
        logger.info("WebSocketManager inicializado")
    
    async def connect(self, websocket: WebSocket) -> str:
        """
        Aceita conexão WebSocket e cria sessão.
        
        Returns:
            ID da sessão criada
        """
        await websocket.accept()
        session_id = str(uuid.uuid4())
        
        session = VoiceChatSession(session_id, websocket)
        await session.initialize()
        
        self.active_sessions[session_id] = session
        
        logger.info(f"Nova conexão WebSocket: {session_id}")
        
        # Enviar mensagem de início de sessão
        session_start_msg = ServerMessage(
            type=MessageType.SESSION_START,
            session_id=session_id,
            data={'session_id': session_id}
        )
        await session.send_message(session_start_msg)
        
        return session_id
    
    async def disconnect(self, session_id: str):
        """Desconecta sessão."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            await session.cleanup()
            del self.active_sessions[session_id]
            logger.info(f"Sessão desconectada: {session_id}")
    
    def get_session(self, session_id: str) -> Optional[VoiceChatSession]:
        """Retorna sessão pelo ID."""
        return self.active_sessions.get(session_id)
    
    async def handle_message(self, session_id: str, message: dict):
        """Processa mensagem recebida."""
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"Sessão não encontrada: {session_id}")
            return
        
        try:
            # Usar parse_message para validação flexível
            client_msg = ClientMessage.parse_message(message)
            
            if client_msg.type == MessageType.AUDIO_CHUNK:
                audio_data = client_msg.data.get('audio', '') if client_msg.data else ''
                if audio_data:
                    await session.handle_audio_chunk(audio_data)
            
            elif client_msg.type == MessageType.START_SPEAKING:
                await session.handle_start_speaking()
            
            elif client_msg.type == MessageType.STOP_SPEAKING:
                await session.handle_stop_speaking()
            
            elif client_msg.type == MessageType.BARGE_IN:
                await session.handle_barge_in()
            
            else:
                logger.warning(f"Tipo de mensagem desconhecido: {client_msg.type}")
        
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
            await session.send_error("message_processing_error", str(e))


# Instância global do gerenciador
websocket_manager = WebSocketManager()

