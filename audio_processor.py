"""Processamento de áudio."""
import base64
import numpy as np
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class AudioProcessor:
    """Processador de áudio para conversão e manipulação."""
    
    @staticmethod
    def base64_to_bytes(base64_audio: str) -> bytes:
        """Converte áudio base64 para bytes."""
        try:
            return base64.b64decode(base64_audio)
        except Exception as e:
            logger.error(f"Erro ao decodificar base64: {e}")
            raise
    
    @staticmethod
    def bytes_to_base64(audio_bytes: bytes) -> str:
        """Converte bytes de áudio para base64."""
        try:
            return base64.b64encode(audio_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Erro ao codificar base64: {e}")
            raise
    
    @staticmethod
    def bytes_to_numpy(
        audio_bytes: bytes, 
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: type = np.int16
    ) -> np.ndarray:
        """
        Converte bytes de áudio PCM para numpy array.
        
        Args:
            audio_bytes: Dados de áudio em bytes
            sample_rate: Taxa de amostragem
            channels: Número de canais
            dtype: Tipo de dados (np.int16 para PCM 16-bit)
            
        Returns:
            Array numpy com os dados de áudio
        """
        try:
            audio_array = np.frombuffer(audio_bytes, dtype=dtype)
            
            # Se estéreo, converter para mono (média dos canais)
            if channels == 2:
                audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(dtype)
            
            return audio_array
        except Exception as e:
            logger.error(f"Erro ao converter bytes para numpy: {e}")
            raise
    
    @staticmethod
    def numpy_to_bytes(
        audio_array: np.ndarray,
        dtype: type = np.int16
    ) -> bytes:
        """
        Converte numpy array para bytes PCM.
        
        Args:
            audio_array: Array numpy com dados de áudio
            dtype: Tipo de dados (np.int16 para PCM 16-bit)
            
        Returns:
            Bytes de áudio PCM
        """
        try:
            # Garantir que está no tipo correto
            if audio_array.dtype != dtype:
                audio_array = audio_array.astype(dtype)
            
            return audio_array.tobytes()
        except Exception as e:
            logger.error(f"Erro ao converter numpy para bytes: {e}")
            raise
    
    @staticmethod
    def resample_audio(
        audio_array: np.ndarray,
        original_rate: int,
        target_rate: int
    ) -> np.ndarray:
        """
        Reamostra áudio para uma nova taxa de amostragem.
        
        Args:
            audio_array: Array numpy com dados de áudio
            original_rate: Taxa de amostragem original
            target_rate: Taxa de amostragem desejada
            
        Returns:
            Array numpy reamostrado
        """
        if original_rate == target_rate:
            return audio_array
        
        try:
            # Usar interpolação linear simples
            duration = len(audio_array) / original_rate
            target_length = int(duration * target_rate)
            
            indices = np.linspace(0, len(audio_array) - 1, target_length)
            resampled = np.interp(indices, np.arange(len(audio_array)), audio_array)
            
            return resampled.astype(audio_array.dtype)
        except Exception as e:
            logger.error(f"Erro ao reamostrar áudio: {e}")
            raise
    
    @staticmethod
    def normalize_audio(audio_array: np.ndarray) -> np.ndarray:
        """
        Normaliza áudio para evitar clipping.
        
        Args:
            audio_array: Array numpy com dados de áudio
            
        Returns:
            Array numpy normalizado
        """
        try:
            max_val = np.abs(audio_array).max()
            if max_val > 0:
                # Normalizar para 90% do máximo para evitar clipping
                return (audio_array / max_val * 0.9 * np.iinfo(audio_array.dtype).max).astype(audio_array.dtype)
            return audio_array
        except Exception as e:
            logger.error(f"Erro ao normalizar áudio: {e}")
            return audio_array

