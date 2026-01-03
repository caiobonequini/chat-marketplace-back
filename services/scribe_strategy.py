"""Estratégia para Speech-to-Text usando Sofya Scribe."""
from typing import Dict, Any, Optional
from services.marketplace_client import MarketplaceClient
from utils.logger import get_logger

logger = get_logger(__name__)


class SofyaScribeStrategy:
    """Estratégia para transcrição de áudio usando Sofya Scribe."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://clinical-services.aiaas.mv.com.br/scribe"
    ):
        """
        Inicializa a estratégia Sofya Scribe.
        
        Args:
            api_key: Chave de API do cliente (opcional - não necessário se não usar Gateway)
            base_url: URL base do serviço Scribe
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.client = None
        logger.info(f"SofyaScribeStrategy inicializado (API key: {'fornecida' if api_key else 'não fornecida - chamada direta'})")
    
    async def _get_client(self):
        """Retorna cliente HTTP (httpx)."""
        if not self.client:
            import httpx
            headers = {}
            if self.api_key:
                headers['x-api-key'] = self.api_key
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers
            )
        return self.client
    
    async def close(self):
        """Fecha o cliente HTTP."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def transcribe_audio_file(
        self,
        audio_file: bytes,
        filename: str,
        content_type: str = "audio/wav"
    ) -> Dict[str, Any]:
        """
        Transcreve um arquivo de áudio.
        
        Args:
            audio_file: Bytes do arquivo de áudio
            filename: Nome do arquivo
            content_type: Tipo MIME do áudio (padrão: audio/wav)
            
        Returns:
            Dicionário com a transcrição
        """
        endpoint = "/api/transcriber"
        
        files = {
            "file": (filename, audio_file, content_type)
        }
        
        try:
            client = await self._get_client()
            url = f"{self.base_url}{endpoint}"
            
            logger.debug(f"Enviando áudio para Sofya Scribe: {len(audio_file)} bytes, tipo: {content_type}")
            response = await client.post(url, files=files)
            
            # Log da resposta antes de fazer raise_for_status
            logger.debug(f"Resposta Sofya Scribe: status={response.status_code}, headers={dict(response.headers)}")
            
            if response.status_code != 200:
                # Tentar ler o corpo da resposta para debug
                try:
                    error_body = response.text
                    logger.error(f"Erro do Sofya Scribe (status {response.status_code}): {error_body}")
                except:
                    pass
                response.raise_for_status()
            
            result = response.json()
            
            # Extrair texto da transcrição (ajustar conforme formato real da API)
            # Sofya Scribe pode retornar em diferentes formatos
            text = ""
            if isinstance(result, dict):
                text = result.get("transcription", result.get("text", result.get("result", result.get("raw", ""))))
            elif isinstance(result, str):
                text = result
            
            logger.info(f"Transcrição concluída: {len(text)} caracteres")
            return {
                "text": text,
                "source": "sofya_scribe",
                "raw_response": result
            }
        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {e}", exc_info=True)
            # Se for erro HTTP, tentar extrair mais informações
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.text
                    logger.error(f"Detalhes do erro HTTP: {error_detail}")
                except:
                    pass
            return {
                "text": "",
                "error": str(e),
                "source": "sofya_scribe"
            }
    
    async def transcribe_audio_stream(
        self,
        audio_stream: bytes,
        content_type: str = "audio/wav"
    ) -> Dict[str, Any]:
        """
        Transcreve um stream de áudio.
        
        Nota: Se o serviço suportar WebSocket para streaming, implementar aqui.
        Por enquanto, trata como arquivo único.
        
        Args:
            audio_stream: Bytes do stream de áudio
            content_type: Tipo MIME do áudio
            
        Returns:
            Dicionário com a transcrição
        """
        return await self.transcribe_audio_file(
            audio_stream,
            "stream.wav",
            content_type
        )

