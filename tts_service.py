"""Serviço de Text-to-Speech usando Vertex AI."""
import asyncio
from typing import Optional
from google.cloud import texttospeech
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class TTSService:
    """Serviço para converter texto em áudio usando Vertex AI Text-to-Speech."""
    
    def __init__(self):
        """Inicializa o serviço TTS."""
        self.project_id = settings.google_cloud_project_id
        self.location = settings.dialogflow_location
        self.language_code = settings.dialogflow_language_code
        self.sample_rate = settings.sample_rate
        
        # Cliente será inicializado de forma assíncrona
        self.client: Optional[texttospeech.TextToSpeechClient] = None
        
        logger.info(
            f"TTSService inicializado: "
            f"project={self.project_id}, location={self.location}, "
            f"language={self.language_code}, sample_rate={self.sample_rate}"
        )
    
    async def initialize(self):
        """Inicializa o cliente TTS de forma assíncrona."""
        try:
            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(
                None,
                lambda: texttospeech.TextToSpeechClient()
            )
            logger.info("Cliente Vertex AI TTS inicializado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente TTS: {e}")
            raise
    
    async def synthesize_speech(
        self,
        text: str,
        voice_name: Optional[str] = None,
        gender: Optional[texttospeech.SsmlVoiceGender] = None,
        audio_encoding: texttospeech.AudioEncoding = texttospeech.AudioEncoding.LINEAR16
    ) -> bytes:
        """
        Converte texto em áudio usando Vertex AI Text-to-Speech.
        
        Args:
            text: Texto a ser convertido em áudio
            voice_name: Nome da voz específica (opcional)
            gender: Gênero da voz (opcional)
            audio_encoding: Codificação de áudio (padrão: LINEAR16)
            
        Returns:
            Bytes de áudio PCM
        """
        if not self.client:
            await self.initialize()
        
        try:
            # Configurar síntese de voz
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Configurar voz
            voice_config = texttospeech.VoiceSelectionParams(
                language_code=self.language_code,
            )
            
            # Se voice_name especificado, usar
            if voice_name:
                voice_config.name = voice_name
            
            # Se gender especificado, usar
            if gender:
                voice_config.ssml_gender = gender
            
            # Configurar áudio
            audio_config = texttospeech.AudioConfig(
                audio_encoding=audio_encoding,
                sample_rate_hertz=self.sample_rate,
            )
            
            # Criar requisição
            request = texttospeech.SynthesizeSpeechRequest(
                input=synthesis_input,
                voice=voice_config,
                audio_config=audio_config,
            )
            
            # Executar síntese em thread separada
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.synthesize_speech(request=request)
            )
            
            logger.debug(f"Áudio sintetizado: {len(response.audio_content)} bytes")
            return response.audio_content
            
        except Exception as e:
            logger.error(f"Erro ao sintetizar fala: {e}")
            raise

