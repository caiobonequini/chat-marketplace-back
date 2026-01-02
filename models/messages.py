"""Modelos de mensagens WebSocket."""
from pydantic import BaseModel
from typing import Optional, Literal, Dict, Any
from enum import Enum
from utils.logger import get_logger


class MessageType(str, Enum):
    """Tipos de mensagens WebSocket."""
    AUDIO_CHUNK = "audio_chunk"
    START_SPEAKING = "start_speaking"
    STOP_SPEAKING = "stop_speaking"
    END_OF_SPEECH = "end_of_speech"  # Alias para stop_speaking
    BARGE_IN = "barge_in"
    AUDIO_RESPONSE = "audio_response"
    TRANSCRIPTION = "transcription"
    INTENT = "intent"
    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"
    ERROR = "error"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


class ClientMessage(BaseModel):
    """Mensagem do cliente para o servidor."""
    type: MessageType
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    
    @classmethod
    def parse_message(cls, message_dict: Dict[str, Any]) -> "ClientMessage":
        """
        Parse uma mensagem com validação flexível.
        
        Aceita formatos:
        - {"type": "audio_chunk", "data": {"audio": "..."}}
        - {"type": "audio_chunk", "data": "..."}  # data como string (base64 direto)
        - {"type": "end_of_speech"}  # mapeia para stop_speaking
        """
        # Criar cópia para não modificar o original
        normalized = message_dict.copy()
        
        # Normalizar tipo: mapear end_of_speech para stop_speaking
        msg_type = normalized.get("type", "")
        if msg_type == "end_of_speech":
            normalized["type"] = "stop_speaking"
        
        # Normalizar data: se é string e tipo é audio_chunk, converter para dict
        if isinstance(normalized.get("data"), str):
            if normalized.get("type") in ["audio_chunk", MessageType.AUDIO_CHUNK]:
                normalized["data"] = {"audio": normalized["data"]}
            # Se não for audio_chunk, manter como None (data opcional)
            elif normalized.get("type") not in ["audio_chunk", MessageType.AUDIO_CHUNK]:
                normalized["data"] = None
        
        try:
            return cls(**normalized)
        except Exception as e:
            # Se ainda falhar, logar e tentar criar com valores mínimos
            logger = get_logger(__name__)
            logger.warning(f"Erro ao parsear mensagem: {e}, mensagem: {normalized}")
            # Tentar criar com tipo como string primeiro, depois converter
            try:
                # Converter tipo string para enum se necessário
                if isinstance(normalized.get("type"), str):
                    normalized["type"] = MessageType(normalized["type"])
                return cls(**normalized)
            except Exception:
                # Última tentativa: criar mensagem básica
                logger.error(f"Não foi possível parsear mensagem: {normalized}")
                raise


class AudioChunkMessage(ClientMessage):
    """Mensagem com chunk de áudio."""
    type: Literal[MessageType.AUDIO_CHUNK] = MessageType.AUDIO_CHUNK
    data: Dict[str, Any]  # Deve conter 'audio': base64 string


class ServerMessage(BaseModel):
    """Mensagem do servidor para o cliente."""
    type: MessageType
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None


class AudioResponseMessage(ServerMessage):
    """Mensagem com chunk de áudio da resposta."""
    type: Literal[MessageType.AUDIO_RESPONSE] = MessageType.AUDIO_RESPONSE
    data: Dict[str, Any]  # Deve conter 'audio': base64 string


class TranscriptionMessage(ServerMessage):
    """Mensagem com transcrição."""
    type: Literal[MessageType.TRANSCRIPTION] = MessageType.TRANSCRIPTION
    data: Dict[str, str]  # Deve conter 'text': string


class IntentMessage(ServerMessage):
    """Mensagem com intenção detectada."""
    type: Literal[MessageType.INTENT] = MessageType.INTENT
    data: Dict[str, Any]  # Deve conter 'intent': string, 'confidence': float


class ToolCallMessage(ServerMessage):
    """Mensagem com chamada de ferramenta."""
    type: Literal[MessageType.TOOL_CALL] = MessageType.TOOL_CALL
    data: Dict[str, Any]  # Deve conter 'tool': string, 'parameters': dict


class ErrorMessage(ServerMessage):
    """Mensagem de erro."""
    type: Literal[MessageType.ERROR] = MessageType.ERROR
    data: Dict[str, str]  # Deve conter 'error': string, 'message': string

