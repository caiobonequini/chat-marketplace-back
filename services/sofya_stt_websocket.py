"""Cliente WebSocket para Sofya STT (Speech-to-Text) em streaming."""
import asyncio
import json
from typing import Dict, Any, Optional, AsyncIterator, Callable
import websockets
from utils.logger import get_logger

logger = get_logger(__name__)


class SofyaSTTWebSocket:
    """Cliente WebSocket para transcrição de áudio em tempo real usando Sofya STT."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        ws_url: str = "wss://clinical-services.aiaas.mv.com.br/scribe/ws/transcriber",
        language: str = "pt-BR"
    ):
        """
        Inicializa o cliente WebSocket do Sofya STT.
        
        Args:
            api_key: Chave de API (opcional - não necessário se não usar Gateway)
            ws_url: URL do WebSocket do Sofya STT
            language: Código do idioma (padrão: pt-BR)
        """
        self.api_key = api_key
        self.ws_url = ws_url
        self.language = language
        self.websocket = None
        self.final_transcription = ""
        self.partial_transcription = ""
        logger.info(f"SofyaSTTWebSocket inicializado (URL: {ws_url}, language: {language})")
    
    async def connect(self):
        """Conecta ao WebSocket do Sofya STT."""
        try:
            # Adicionar parâmetros de query string se necessário (ex: language)
            url = f"{self.ws_url}?language={self.language}"
            
            # Headers opcionais (se API key for necessária)
            extra_headers = {}
            if self.api_key:
                extra_headers['x-api-key'] = self.api_key
            
            logger.debug(f"Conectando ao WebSocket Sofya STT: {url}")
            self.websocket = await websockets.connect(
                url,
                extra_headers=extra_headers if extra_headers else None
            )
            logger.info("✅ Conectado ao WebSocket Sofya STT")
        except Exception as e:
            logger.error(f"Erro ao conectar ao WebSocket Sofya STT: {e}", exc_info=True)
            raise
    
    async def close(self):
        """Fecha a conexão WebSocket."""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.debug("Conexão WebSocket Sofya STT fechada")
            except Exception as e:
                logger.error(f"Erro ao fechar WebSocket: {e}")
            finally:
                self.websocket = None
    
    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        on_partial: Optional[Callable[[str], None]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Transcreve um stream de áudio via WebSocket.
        
        Args:
            audio_chunks: AsyncIterator de chunks de áudio PCM (16-bit, 16kHz, mono)
            on_partial: Callback opcional para receber transcrições parciais
            timeout: Timeout em segundos para aguardar resposta final
        
        Returns:
            Dicionário com a transcrição final:
            {
                "text": "texto transcrito",
                "status": "final",
                "source": "sofya_stt_websocket"
            }
        """
        if not self.websocket:
            await self.connect()
        
        self.final_transcription = ""
        self.partial_transcription = ""
        
        try:
            # Task para enviar chunks de áudio
            async def send_audio():
                """Envia chunks de áudio para o servidor."""
                try:
                    chunk_count = 0
                    total_bytes = 0
                    async for chunk in audio_chunks:
                        if self.websocket and not self.websocket.closed:
                            # Enviar como dados binários (PCM raw, 16-bit, 16kHz, mono)
                            await self.websocket.send(chunk)
                            chunk_count += 1
                            total_bytes += len(chunk)
                            logger.debug(f"Chunk {chunk_count} enviado: {len(chunk)} bytes (total: {total_bytes} bytes)")
                        else:
                            logger.warning("WebSocket fechado, parando envio de áudio")
                            break
                    
                    # Enviar comando de finalização após todos os chunks
                    if self.websocket and not self.websocket.closed:
                        finish_message = json.dumps({"action": "finish"})
                        await self.websocket.send(finish_message)
                        logger.debug(f"Comando 'finish' enviado (total: {chunk_count} chunks, {total_bytes} bytes)")
                except Exception as e:
                    logger.error(f"Erro ao enviar áudio: {e}", exc_info=True)
            
            # Task para receber respostas
            async def receive_responses():
                """Recebe e processa respostas do servidor."""
                try:
                    attempts_without_response = 0
                    max_attempts = 10  # Máximo de tentativas sem resposta
                    
                    while attempts_without_response < max_attempts:
                        try:
                            # Aguardar resposta com timeout curto
                            response = await asyncio.wait_for(
                                self.websocket.recv(),
                                timeout=1.0
                            )
                            
                            # Resetar contador se recebeu resposta
                            attempts_without_response = 0
                            
                            # Processar resposta JSON
                            if isinstance(response, str):
                                try:
                                    data = json.loads(response)
                                    status = data.get("status", "")
                                    result_data = data.get("data", {})
                                    text = result_data.get("text", "")
                                    
                                    if status == "partial":
                                        # Transcrição parcial
                                        self.partial_transcription = text
                                        logger.debug(f"📝 Transcrição parcial: {text}")
                                        
                                        # Chamar callback se fornecido
                                        if on_partial and text:
                                            on_partial(text)
                                    
                                    elif status == "final":
                                        # Transcrição final
                                        self.final_transcription = text
                                        logger.info(f"✅ Transcrição final: {text}")
                                        
                                        # Se já temos transcrição final, podemos parar
                                        if text:
                                            break
                                
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Resposta não é JSON válido: {response[:100]}")
                            
                            elif isinstance(response, bytes):
                                logger.debug(f"Resposta binária recebida: {len(response)} bytes")
                        
                        except asyncio.TimeoutError:
                            # Timeout ao aguardar resposta
                            attempts_without_response += 1
                            logger.debug(f"Timeout aguardando resposta ({attempts_without_response}/{max_attempts})")
                            
                            # Se já temos transcrição final, podemos parar
                            if self.final_transcription:
                                break
                        
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("Conexão WebSocket fechada pelo servidor")
                            break
                
                except Exception as e:
                    logger.error(f"Erro ao receber respostas: {e}", exc_info=True)
            
            # Executar envio e recebimento em paralelo
            send_task = asyncio.create_task(send_audio())
            receive_task = asyncio.create_task(receive_responses())
            
            # Aguardar ambas as tasks
            await asyncio.gather(send_task, receive_task, return_exceptions=True)
            
            # Se não recebemos transcrição final, usar a parcial como fallback
            if not self.final_transcription and self.partial_transcription:
                logger.info(f"Usando transcrição parcial como final: {self.partial_transcription}")
                self.final_transcription = self.partial_transcription
            
            return {
                "text": self.final_transcription,
                "partial": self.partial_transcription,
                "status": "final" if self.final_transcription else "partial",
                "source": "sofya_stt_websocket"
            }
        
        except Exception as e:
            logger.error(f"Erro durante transcrição via WebSocket: {e}", exc_info=True)
            return {
                "text": "",
                "error": str(e),
                "source": "sofya_stt_websocket"
            }
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

