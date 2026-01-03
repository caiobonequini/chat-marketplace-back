"""Cliente HTTP base para integração com MV Marketplace API Gateway."""
import httpx
from typing import Optional, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class MarketplaceClient:
    """Cliente HTTP base que encapsula a lógica de autenticação com x-api-key."""
    
    def __init__(self, api_key: str, base_url: str, timeout: float = 30.0):
        """
        Inicializa o cliente do marketplace.
        
        Args:
            api_key: Chave de API do cliente (x-api-key)
            base_url: URL base do serviço
            timeout: Timeout para requisições em segundos
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                'x-api-key': api_key,
                'Content-Type': 'application/json'
            }
        )
        logger.info(f"MarketplaceClient inicializado: base_url={self.base_url}")
    
    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """
        Faz uma requisição POST.
        
        Args:
            endpoint: Caminho do endpoint (relativo à base_url)
            data: Dados para enviar como form-data
            json: Dados para enviar como JSON
            files: Arquivos para enviar (multipart/form-data)
            headers: Headers adicionais
            
        Returns:
            Resposta HTTP
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self.client.headers.copy()
        if headers:
            request_headers.update(headers)
        
        # Se houver files, remover Content-Type para deixar httpx definir
        if files:
            request_headers.pop('Content-Type', None)
        
        try:
            response = await self.client.post(
                url,
                data=data,
                json=json,
                files=files,
                headers=request_headers
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP {e.response.status_code} em POST {url}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Erro de requisição em POST {url}: {e}")
            raise
    
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """
        Faz uma requisição GET.
        
        Args:
            endpoint: Caminho do endpoint (relativo à base_url)
            params: Parâmetros de query string
            headers: Headers adicionais
            
        Returns:
            Resposta HTTP
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self.client.headers.copy()
        if headers:
            request_headers.update(headers)
        
        try:
            response = await self.client.get(url, params=params, headers=request_headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP {e.response.status_code} em GET {url}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Erro de requisição em GET {url}: {e}")
            raise
    
    async def close(self):
        """Fecha o cliente HTTP."""
        await self.client.aclose()
        logger.debug("MarketplaceClient fechado")
    
    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

