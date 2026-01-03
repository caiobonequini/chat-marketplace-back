"""Handler WebSocket para chat em tempo real."""
import asyncio
import json
import uuid
import time
from typing import Dict, Optional, Set, Any
from collections import deque
from fastapi import WebSocket, WebSocketDisconnect

from config import settings
from models.messages import (
    MessageType,
    ClientMessage,
    ServerMessage,
    AudioResponseMessage,
    TranscriptionMessage,
    BotResponseMessage,
    IntentMessage,
    ToolCallMessage,
    ErrorMessage,
)
from dialogflow_service import DialogflowService
from vad_service import VADService
from audio_processor import AudioProcessor
from tts_service import TTSService
from tools.products import ProductsTool
from services.chat_strategy import (
    IChatStrategy,
    NotebookMVStrategy,
    SofyaLLMStrategy,
    DialogFlowDynamicStrategy
)
from utils.logger import get_logger

logger = get_logger(__name__)


class VoiceChatSession:
    """Sessão de chat por voz."""
    
    def __init__(self, session_id: str, websocket: WebSocket, chat_config: Optional[Dict] = None):
        """
        Inicializa uma sessão de chat.
        
        Args:
            session_id: ID da sessão
            websocket: Conexão WebSocket
            chat_config: Configuração do chat (apiKey, mode, workspaceId, dialogFlowConfig)
        """
        self.session_id = session_id
        self.websocket = websocket
        self.chat_config = chat_config or {}
        self.chat_strategy: Optional[IChatStrategy] = None
        
        # Serviços padrão
        self.dialogflow = DialogflowService() if not chat_config or chat_config.get("mode") == "DIALOGFLOW" else None
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
        self.message_history: list = []
        self.stt_only_mode = False  # Flag para modo STT apenas (sem Dialogflow)
        
        logger.info(f"Sessão criada: {session_id}, mode: {chat_config.get('mode') if chat_config else 'default'}")
    
    async def initialize(self):
        """Inicializa a sessão."""
        # Inicializar estratégia de chat baseada na configuração
        mode = self.chat_config.get("mode", "DIALOGFLOW")
        api_key = self.chat_config.get("apiKey")
        
        if mode == "RAG" and api_key:
            workspace_id = self.chat_config.get("workspaceId")
            if workspace_id:
                self.chat_strategy = NotebookMVStrategy(
                    api_key=api_key,
                    workspace_id=workspace_id
                )
                await self.chat_strategy.initialize()
            else:
                logger.warning("workspaceId não fornecido para modo RAG")
        
        elif mode == "LLM" and api_key:
            self.chat_strategy = SofyaLLMStrategy(api_key=api_key)
            await self.chat_strategy.initialize()
        
        elif mode == "DIALOGFLOW":
            dialogflow_config = self.chat_config.get("dialogFlowConfig")
            if dialogflow_config:
                # Usar Dialogflow dinâmico com credenciais em memória
                self.chat_strategy = DialogFlowDynamicStrategy(
                    credentials_json=dialogflow_config.get("credentials"),
                    project_id=dialogflow_config.get("projectId"),
                    agent_id=dialogflow_config.get("agentId"),
                    location=dialogflow_config.get("location", "us-central1"),
                    language_code=dialogflow_config.get("languageCode", "pt-BR")
                )
                await self.chat_strategy.initialize()
            else:
                # Usar Dialogflow padrão (configuração global)
                if self.dialogflow:
                    await self.dialogflow.initialize()
        
        await self.tts.initialize()
        logger.info(f"Sessão inicializada: {self.session_id}, strategy: {type(self.chat_strategy).__name__ if self.chat_strategy else 'DialogflowService'}")
    
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
        
        # Se for modo test_stt, não processar com Dialogflow aqui
        # O processamento será feito quando receber a mensagem test_stt
        # Processar áudio acumulado apenas se não for modo test_stt
        # (o modo test_stt será processado quando receber a mensagem test_stt explicitamente)
    
    async def handle_barge_in(self):
        """Handle interrupção explícita do usuário."""
        logger.info(f"Sessão {self.session_id}: Barge-in explícito")
        self.barge_in_flag.set()
        self.is_bot_speaking = False
        self.is_speaking = True
        
        if self.current_stream_task and not self.current_stream_task.done():
            self.current_stream_task.cancel()
    
    async def handle_test_stt(self):
        """Testa apenas o STT (transcrição) sem processar com Dialogflow."""
        try:
            logger.info(f"Sessão {self.session_id}: Teste STT solicitado")
            
            # Ativar modo STT apenas
            self.stt_only_mode = True
            
            # Coletar áudio do buffer
            if len(self.audio_buffer) == 0:
                await self.send_error("test_stt_error", "Nenhum áudio no buffer. Fale primeiro e depois clique em 'Testar STT'.")
                self.stt_only_mode = False
                return
            
            audio_bytes = b''.join(self.audio_buffer)
            self.audio_buffer.clear()  # Limpar buffer após coletar
            
            if len(audio_bytes) == 0:
                await self.send_error("test_stt_error", "Áudio vazio no buffer.")
                return
            
            # Validar tamanho mínimo
            MIN_AUDIO_SIZE = 1600  # ~100ms a 16kHz
            if len(audio_bytes) < MIN_AUDIO_SIZE:
                await self.send_error("test_stt_error", f"Áudio muito curto ({len(audio_bytes)} bytes). Fale por mais tempo.")
                return
            
            # Transcrever usando Sofya STT WebSocket
            from services.sofya_stt_websocket import SofyaSTTWebSocket
            import re
            
            api_key = self.chat_config.get("apiKey") if hasattr(self, 'chat_config') else None
            
            # Criar async generator para chunks de áudio
            async def audio_chunks_generator():
                """Gera chunks de áudio para o WebSocket."""
                chunk_size = 3200  # ~100ms a 16kHz
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i:i + chunk_size]
                    if chunk:
                        yield chunk
            
            # Callback para transcrições parciais
            def on_partial_transcription(text: str):
                """Callback para transcrições parciais."""
                if text and len(text.strip()) > 0:
                    logger.debug(f"📝 Transcrição parcial (teste STT): {text}")
            
            # Usar WebSocket do Sofya STT
            stt_ws = SofyaSTTWebSocket(api_key=api_key)
            try:
                transcription_result = await stt_ws.transcribe_stream(
                    audio_chunks_generator(),
                    on_partial=on_partial_transcription,
                    timeout=30.0
                )
                
                user_transcription = transcription_result.get("text", "").strip()
                
                # Enviar transcrição (mesmo que vazia, para debug)
                transcription_msg = TranscriptionMessage(
                    type=MessageType.TRANSCRIPTION,
                    session_id=self.session_id,
                    data={'text': user_transcription if user_transcription else '[Transcrição vazia - possivelmente ruído]'}
                )
                await self.send_message(transcription_msg)
                
                if user_transcription:
                    logger.info(f"✅ Teste STT - Transcrição: {user_transcription}")
                else:
                    logger.warning("⚠️ Teste STT - Transcrição vazia (possivelmente ruído)")
                    await self.send_error("test_stt_warning", "Transcrição vazia. Verifique se você falou claramente e se o microfone está funcionando.")
            
            except Exception as e:
                logger.error(f"Erro no teste STT: {e}", exc_info=True)
                await self.send_error("test_stt_error", f"Erro ao transcrever: {str(e)}")
            finally:
                await stt_ws.close()
                # Desativar modo STT apenas após processar
                self.stt_only_mode = False
        
        except Exception as e:
            logger.error(f"Erro ao processar teste STT: {e}", exc_info=True)
            await self.send_error("test_stt_error", str(e))
            self.stt_only_mode = False
    
    async def handle_text_message(self, text: str):
        """Processa mensagem de texto do usuário."""
        try:
            if not text or not text.strip():
                logger.warning("Mensagem de texto vazia")
                return
            
            user_text = text.strip()
            logger.info(f"📝 Mensagem de texto recebida: {user_text}")
            
            # Enviar como transcrição (para aparecer no histórico como "Você")
            transcription_msg = TranscriptionMessage(
                type=MessageType.TRANSCRIPTION,
                session_id=self.session_id,
                data={'text': user_text}
            )
            await self.send_message(transcription_msg)
            
            # Processar com Dialogflow ou estratégia de chat
            if self.dialogflow or isinstance(self.chat_strategy, DialogFlowDynamicStrategy):
                dialogflow_service = self.dialogflow if self.dialogflow else None
                
                if isinstance(self.chat_strategy, DialogFlowDynamicStrategy):
                    dialogflow_service = self.dialogflow or DialogflowService()
                    if not self.dialogflow:
                        await dialogflow_service.initialize()
                
                if dialogflow_service:
                    response = await dialogflow_service.detect_intent_text(
                        session_id=self.session_id,
                        text=user_text
                    )
                    
                    if 'error' in response:
                        await self.send_error("dialogflow_error", response['error'])
                        return
                    
                    if 'text' in response and response['text']:
                        # Enviar resposta do bot
                        bot_response_msg = BotResponseMessage(
                            type=MessageType.BOT_RESPONSE,
                            session_id=self.session_id,
                            data={'text': response['text']}
                        )
                        await self.send_message(bot_response_msg)
                        
                        # Enviar intenção se houver
                        if 'intent' in response:
                            intent_msg = IntentMessage(
                                type=MessageType.INTENT,
                                session_id=self.session_id,
                                data=response['intent']
                            )
                            await self.send_message(intent_msg)
                        
                        # Gerar áudio usando Vertex AI TTS
                        try:
                            logger.info(f"Convertendo texto para áudio com Vertex AI TTS: {response['text']}")
                            audio_data = await self.tts.synthesize_speech(response['text'])
                            logger.debug(f"Áudio sintetizado: {len(audio_data)} bytes")
                            
                            if audio_data:
                                audio_base64 = self.audio_processor.bytes_to_base64(audio_data)
                                audio_msg = AudioResponseMessage(
                                    type=MessageType.AUDIO_RESPONSE,
                                    session_id=self.session_id,
                                    data={'audio': audio_base64}
                                )
                                await self.send_message(audio_msg)
                        except Exception as e:
                            logger.error(f"Erro ao sintetizar fala: {e}")
            
            elif self.chat_strategy:
                # Usar estratégia de chat (RAG ou LLM)
                chat_response = await self.chat_strategy.detect_intent_text(
                    session_id=self.session_id,
                    text=user_text
                )
                
                if 'error' in chat_response:
                    await self.send_error("chat_error", chat_response['error'])
                    return
                
                if 'text' in chat_response and chat_response['text']:
                    # Enviar resposta do bot
                    bot_response_msg = BotResponseMessage(
                        type=MessageType.BOT_RESPONSE,
                        session_id=self.session_id,
                        data={'text': chat_response['text']}
                    )
                    await self.send_message(bot_response_msg)
                    
                    # Gerar áudio TTS
                    try:
                        audio_data = await self.tts.synthesize_speech(chat_response['text'])
                        if audio_data:
                            audio_base64 = self.audio_processor.bytes_to_base64(audio_data)
                            audio_msg = AudioResponseMessage(
                                type=MessageType.AUDIO_RESPONSE,
                                session_id=self.session_id,
                                data={'audio': audio_base64}
                            )
                            await self.send_message(audio_msg)
                    except Exception as e:
                        logger.error(f"Erro ao sintetizar fala: {e}")
        
        except Exception as e:
            logger.error(f"Erro ao processar mensagem de texto: {e}", exc_info=True)
            await self.send_error("text_message_error", str(e))
    
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
        """
        Processa stream de áudio.
        
        Se usar estratégia de chat (RAG/LLM), primeiro transcreve o áudio e depois envia texto.
        Se usar Dialogflow, processa streaming diretamente.
        """
        try:
            self.is_bot_speaking = True
            
            # Se usar estratégia de chat (RAG/LLM), precisa transcrever primeiro
            if self.chat_strategy and not isinstance(self.chat_strategy, DialogFlowDynamicStrategy):
                # Para RAG/LLM: coletar todo o áudio, transcrever, e enviar texto
                audio_bytes = b''.join([chunk async for chunk in audio_chunks])
                
                if len(audio_bytes) == 0:
                    logger.warning("Nenhum áudio coletado")
                    self.is_bot_speaking = False
                    return
                
                # Transcrever usando Sofya Scribe (pode funcionar sem API key)
                from services.scribe_strategy import SofyaScribeStrategy
                import re
                
                api_key = self.chat_config.get("apiKey")
                scribe = SofyaScribeStrategy(api_key=api_key)  # API key opcional
                try:
                    transcription_result = await scribe.transcribe_audio_stream(audio_bytes)
                    transcribed_text = transcription_result.get("text", "").strip()
                    
                    # Validar transcrição: ignorar se muito curta (provavelmente ruído)
                    if len(transcribed_text) < 5:
                        logger.warning(f"Transcrição muito curta (ruído?): '{transcribed_text}' - ignorando")
                        transcribed_text = ""
                    else:
                        # Validar se não é apenas caracteres especiais ou números isolados
                        clean_text = re.sub(r'[^a-zA-ZáàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ\s]', '', transcribed_text)
                        if len(clean_text.strip()) < 3:
                            logger.warning(f"Transcrição inválida (apenas ruído?): '{transcribed_text}' - ignorando")
                            transcribed_text = ""
                        else:
                            logger.info(f"✅ Transcrição Sofya Scribe (RAG/LLM): {transcribed_text}")
                except Exception as e:
                    logger.error(f"Erro ao transcrever: {e}", exc_info=True)
                    transcribed_text = ""
                finally:
                    await scribe.close()
                
                if not transcribed_text:
                    logger.warning("Transcrição vazia")
                    self.is_bot_speaking = False
                    return
                
                # Enviar transcrição
                transcription_msg = TranscriptionMessage(
                    type=MessageType.TRANSCRIPTION,
                    session_id=self.session_id,
                    data={'text': transcribed_text}
                )
                await self.send_message(transcription_msg)
                
                # Enviar para estratégia de chat
                chat_response = await self.chat_strategy.send_message(
                    message=transcribed_text,
                    history=self.message_history
                )
                
                # Atualizar histórico
                self.message_history.append({"role": "user", "content": transcribed_text})
                if chat_response.get("text"):
                    self.message_history.append({"role": "assistant", "content": chat_response["text"]})
                
                response_text = chat_response.get("text", "")
                
                # Gerar áudio TTS
                if response_text:
                    try:
                        audio_data = await self.tts.synthesize_speech(response_text)
                        audio_base64 = self.audio_processor.bytes_to_base64(audio_data)
                        audio_msg = AudioResponseMessage(
                            type=MessageType.AUDIO_RESPONSE,
                            session_id=self.session_id,
                            data={'audio': audio_base64}
                        )
                        await self.send_message(audio_msg)
                    except Exception as e:
                        logger.error(f"Erro ao sintetizar fala: {e}")
            
            # Se usar Dialogflow (padrão ou dinâmico)
            elif self.dialogflow or isinstance(self.chat_strategy, DialogFlowDynamicStrategy):
                # TRANSCREVER ÁUDIO usando Sofya Scribe (Marketplace)
                # Coletar todos os chunks de áudio
                audio_bytes = b''.join([chunk async for chunk in audio_chunks])
                
                if len(audio_bytes) == 0:
                    logger.warning("Nenhum áudio coletado para transcrição")
                    self.is_bot_speaking = False
                    return
                
                # Validar tamanho mínimo de áudio (evitar processar ruído muito curto)
                MIN_AUDIO_SIZE = 1600  # ~100ms a 16kHz (mínimo para ser considerado fala)
                if len(audio_bytes) < MIN_AUDIO_SIZE:
                    logger.warning(f"Áudio muito curto ({len(audio_bytes)} bytes) - ignorando como ruído")
                    self.is_bot_speaking = False
                    return
                
                # Transcrever usando Sofya STT WebSocket (streaming em tempo real)
                from services.sofya_stt_websocket import SofyaSTTWebSocket
                import re
                
                api_key = self.chat_config.get("apiKey") if hasattr(self, 'chat_config') else None
                user_transcription = ""
                
                # Criar async generator para chunks de áudio
                async def audio_chunks_generator():
                    """Gera chunks de áudio para o WebSocket."""
                    # Dividir áudio em chunks menores para streaming
                    chunk_size = 3200  # ~100ms a 16kHz (2 bytes por sample)
                    for i in range(0, len(audio_bytes), chunk_size):
                        chunk = audio_bytes[i:i + chunk_size]
                        if chunk:
                            yield chunk
                
                # Callback para transcrições parciais (feedback visual)
                # Nota: callback não pode ser async, então apenas logamos
                def on_partial_transcription(text: str):
                    """Callback para transcrições parciais."""
                    if text and len(text.strip()) > 0:
                        logger.debug(f"📝 Transcrição parcial recebida: {text}")
                
                # Usar WebSocket do Sofya STT
                stt_ws = SofyaSTTWebSocket(api_key=api_key)
                try:
                    transcription_result = await stt_ws.transcribe_stream(
                        audio_chunks_generator(),
                        on_partial=on_partial_transcription,
                        timeout=30.0
                    )
                    
                    user_transcription = transcription_result.get("text", "").strip()
                    
                    # Validar transcrição: ignorar se muito curta (provavelmente ruído)
                    if len(user_transcription) < 5:
                        logger.warning(f"Transcrição muito curta (ruído?): '{user_transcription}' - ignorando")
                        user_transcription = ""
                    else:
                        # Validar se não é apenas caracteres especiais ou números isolados
                        clean_text = re.sub(r'[^a-zA-ZáàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ\s]', '', user_transcription)
                        if len(clean_text.strip()) < 3:
                            logger.warning(f"Transcrição inválida (apenas ruído?): '{user_transcription}' - ignorando")
                            user_transcription = ""
                        else:
                            logger.info(f"✅ Transcrição Sofya STT WebSocket: {user_transcription}")
                
                except Exception as e:
                    logger.error(f"Erro ao transcrever com Sofya STT WebSocket: {e}", exc_info=True)
                    user_transcription = ""
                finally:
                    await stt_ws.close()
                
                # Se transcrição vazia, não processar (evitar loops e erros)
                if not user_transcription:
                    logger.warning("Transcrição vazia - ignorando (provavelmente ruído)")
                    self.is_bot_speaking = False
                    return
                
                # Enviar transcrição do usuário ao frontend
                transcription_msg = TranscriptionMessage(
                    type=MessageType.TRANSCRIPTION,
                    session_id=self.session_id,
                    data={'text': user_transcription}
                )
                await self.send_message(transcription_msg)
                logger.info(f"📤 Transcrição do usuário (Sofya Scribe): {user_transcription}")
                
                # Processar com Dialogflow usando TEXTO
                dialogflow_service = self.dialogflow if self.dialogflow else None
                
                if isinstance(self.chat_strategy, DialogFlowDynamicStrategy):
                    dialogflow_service = self.dialogflow or DialogflowService()
                    if not self.dialogflow:
                        await dialogflow_service.initialize()
                
                if dialogflow_service:
                    # Usar detect_intent_text (já temos o texto transcrito)
                    response = await dialogflow_service.detect_intent_text(
                        session_id=self.session_id,
                        text=user_transcription
                    )
                    
                    if 'error' in response:
                        await self.send_error("dialogflow_error", response['error'])
                        self.is_bot_speaking = False
                        return
                    
                    # Processar resposta
                    if 'text' in response and response['text']:
                        # Enviar resposta do bot
                        bot_response_msg = BotResponseMessage(
                            type=MessageType.BOT_RESPONSE,
                            session_id=self.session_id,
                            data={'text': response['text']}
                        )
                        await self.send_message(bot_response_msg)
                        
                        # Enviar intenção se houver
                        if 'intent' in response:
                            intent_msg = IntentMessage(
                                type=MessageType.INTENT,
                                session_id=self.session_id,
                                data=response['intent']
                            )
                            await self.send_message(intent_msg)
                        
                        # Gerar áudio usando Vertex AI TTS
                        try:
                            logger.info(f"Convertendo texto para áudio com Vertex AI TTS: {response['text']}")
                            audio_data = await self.tts.synthesize_speech(response['text'])
                            logger.debug(f"Áudio sintetizado: {len(audio_data)} bytes")
                            
                            if audio_data:
                                audio_base64 = self.audio_processor.bytes_to_base64(audio_data)
                                audio_msg = AudioResponseMessage(
                                    type=MessageType.AUDIO_RESPONSE,
                                    session_id=self.session_id,
                                    data={'audio': audio_base64}
                                )
                                await self.send_message(audio_msg)
                        except Exception as e:
                            logger.error(f"Erro ao sintetizar fala: {e}")
                
                self.is_bot_speaking = False
            
        except Exception as e:
            logger.error(f"Erro ao processar stream: {e}")
            self.is_bot_speaking = False
            await self.send_error("stream_processing_error", str(e))
    
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
        
        # Limpar estratégia de chat
        if self.chat_strategy:
            try:
                await self.chat_strategy.cleanup()
            except Exception as e:
                logger.error(f"Erro ao limpar estratégia de chat: {e}")
        
        logger.info(f"Sessão {self.session_id}: Limpeza concluída")


class WebSocketManager:
    """Gerenciador de conexões WebSocket."""
    
    def __init__(self):
        """Inicializa o gerenciador."""
        self.active_sessions: Dict[str, VoiceChatSession] = {}
        logger.info("WebSocketManager inicializado")
    
    async def connect(self, websocket: WebSocket, chat_config: Optional[Dict] = None) -> str:
        """
        Aceita conexão WebSocket e cria sessão.
        
        Args:
            websocket: Conexão WebSocket
            chat_config: Configuração do chat (opcional, pode ser enviada depois)
        
        Returns:
            ID da sessão criada
        """
        await websocket.accept()
        session_id = str(uuid.uuid4())
        
        session = VoiceChatSession(session_id, websocket, chat_config)
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
            
            # Verificar se é mensagem de configuração
            if client_msg.type == MessageType.SESSION_START and client_msg.data:
                config = client_msg.data
                if config.get("apiKey") or config.get("mode"):
                    # Atualizar configuração da sessão
                    session.chat_config.update(config)
                    # Reinicializar com nova configuração
                    await session.initialize()
                    logger.info(f"Configuração atualizada para sessão {session_id}: mode={config.get('mode')}")
            
            elif client_msg.type == MessageType.AUDIO_CHUNK:
                audio_data = client_msg.data.get('audio', '') if client_msg.data else ''
                if audio_data:
                    await session.handle_audio_chunk(audio_data)
            
            elif client_msg.type == MessageType.START_SPEAKING:
                await session.handle_start_speaking()
            
            elif client_msg.type == MessageType.STOP_SPEAKING:
                await session.handle_stop_speaking()
            
            elif client_msg.type == MessageType.BARGE_IN:
                await session.handle_barge_in()
            
            elif client_msg.type == MessageType.TEXT_MESSAGE:
                # Mensagem de texto do usuário
                text = client_msg.data.get('text', '') if client_msg.data else ''
                if text:
                    await session.handle_text_message(text)
            
            elif client_msg.type == MessageType.TEST_STT:
                # Teste apenas STT (sem Dialogflow)
                await session.handle_test_stt()
            
            else:
                logger.warning(f"Tipo de mensagem desconhecido: {client_msg.type}")
        
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
            await session.send_error("message_processing_error", str(e))


# Instância global do gerenciador
websocket_manager = WebSocketManager()

