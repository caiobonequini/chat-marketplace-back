"""Serviço de Voice Activity Detection."""
import numpy as np
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)

# Tentar importar webrtcvad, mas tornar opcional
try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    logger.warning(
        "webrtcvad não está disponível. "
        "VAD será desabilitado. "
        "Para habilitar, instale: pip install webrtcvad "
        "(requer Microsoft Visual C++ Build Tools no Windows)"
    )


class VADService:
    """Serviço para detectar atividade de voz."""
    
    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2):
        """
        Inicializa o serviço VAD.
        
        Args:
            sample_rate: Taxa de amostragem do áudio (8000, 16000, 32000 ou 48000)
            aggressiveness: Nível de agressividade (0-3, onde 3 é mais agressivo)
        """
        self.vad_available = VAD_AVAILABLE
        
        if not self.vad_available:
            logger.warning("VAD desabilitado - webrtcvad não disponível")
            self.vad = None
            self.sample_rate = sample_rate
            self.frame_size = int(self.sample_rate * 0.03)  # 30ms
            return
        
        # webrtcvad suporta apenas 8000, 16000, 32000, 48000
        # Se receber outro valor não suportado, vamos usar 16000 como fallback
        if sample_rate not in [8000, 16000, 32000, 48000]:
            logger.warning(
                f"Sample rate {sample_rate} não suportado pelo VAD. "
                f"Usando 16000 como fallback."
            )
            self.sample_rate = 16000
            self.needs_resample = True
        else:
            self.sample_rate = sample_rate
            self.needs_resample = False
        
        self.vad = webrtcvad.Vad(aggressiveness)
        self.frame_duration_ms = 30  # Duração do frame em ms
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
        
        logger.info(
            f"VAD inicializado: sample_rate={self.sample_rate}, "
            f"aggressiveness={aggressiveness}, frame_size={self.frame_size}"
        )
    
    def is_speech(self, audio_data: bytes) -> bool:
        """
        Detecta se há fala no chunk de áudio.
        
        Args:
            audio_data: Dados de áudio em bytes (PCM 16-bit)
            
        Returns:
            True se há fala detectada, False caso contrário
        """
        if not self.vad_available or self.vad is None:
            # Se VAD não está disponível, assume que sempre há fala
            # (o frontend deve fazer a detecção)
            return True
        
        try:
            # Garantir que o tamanho do frame está correto
            if len(audio_data) < self.frame_size * 2:  # 2 bytes por sample (16-bit)
                # Padding com zeros se necessário
                audio_data = audio_data + b'\x00' * (self.frame_size * 2 - len(audio_data))
            elif len(audio_data) > self.frame_size * 2:
                # Truncar se necessário
                audio_data = audio_data[:self.frame_size * 2]
            
            return self.vad.is_speech(audio_data, self.sample_rate)
        except Exception as e:
            logger.error(f"Erro ao detectar fala: {e}")
            return False
    
    def detect_speech_segments(
        self, 
        audio_chunks: list[bytes], 
        min_silence_ms: int = 500,
        min_speech_ms: int = 250
    ) -> list[tuple[int, int]]:
        """
        Detecta segmentos de fala em uma sequência de chunks.
        
        Args:
            audio_chunks: Lista de chunks de áudio
            min_silence_ms: Duração mínima de silêncio para considerar fim de fala
            min_speech_ms: Duração mínima de fala para considerar início
            
        Returns:
            Lista de tuplas (início, fim) em índices de chunks
        """
        speech_segments = []
        in_speech = False
        speech_start = None
        silence_count = 0
        speech_count = 0
        
        min_silence_frames = int(min_silence_ms / self.frame_duration_ms)
        min_speech_frames = int(min_speech_ms / self.frame_duration_ms)
        
        for i, chunk in enumerate(audio_chunks):
            is_speech = self.is_speech(chunk)
            
            if is_speech:
                speech_count += 1
                silence_count = 0
                
                if not in_speech:
                    in_speech = True
                    speech_start = i
            
            else:
                silence_count += 1
                if in_speech:
                    if silence_count >= min_silence_frames:
                        if speech_count >= min_speech_frames:
                            speech_segments.append((speech_start, i - silence_count))
                        in_speech = False
                        speech_start = None
                        speech_count = 0
        
        # Finalizar segmento se ainda estiver em fala
        if in_speech and speech_count >= min_speech_frames:
            speech_segments.append((speech_start, len(audio_chunks)))
        
        return speech_segments

