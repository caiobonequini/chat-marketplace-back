"""Ferramenta de busca de produtos."""
from typing import Dict, Any, List, Optional
from utils.logger import get_logger
import aiohttp

logger = get_logger(__name__)


class ProductsTool:
    """Ferramenta para buscar produtos."""
    
    def __init__(self, api_base_url: str = "http://localhost:3000/api"):
        """
        Inicializa a ferramenta de produtos.
        
        Args:
            api_base_url: URL base da API de produtos
        """
        self.api_base_url = api_base_url.rstrip('/')
        logger.info(f"ProductsTool inicializado: api_base_url={self.api_base_url}")
    
    async def search_products(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Busca produtos.
        
        Args:
            query: Termo de busca
            category: Categoria do produto
            min_price: Preço mínimo
            max_price: Preço máximo
            limit: Limite de resultados
            
        Returns:
            Dicionário com resultados da busca
        """
        try:
            params = {}
            if query:
                params['q'] = query
            if category:
                params['category'] = category
            if min_price is not None:
                params['min_price'] = min_price
            if max_price is not None:
                params['max_price'] = max_price
            params['limit'] = limit
            
            url = f"{self.api_base_url}/products"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Produtos encontrados: {len(data.get('products', []))}")
                        return {
                            'success': True,
                            'products': data.get('products', []),
                            'count': len(data.get('products', []))
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Erro na API de produtos: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f"Erro HTTP {response.status}",
                            'products': []
                        }
        
        except aiohttp.ClientError as e:
            logger.error(f"Erro de conexão com API de produtos: {e}")
            return {
                'success': False,
                'error': str(e),
                'products': []
            }
        except Exception as e:
            logger.error(f"Erro ao buscar produtos: {e}")
            return {
                'success': False,
                'error': str(e),
                'products': []
            }
    
    async def get_product_by_id(self, product_id: str) -> Dict[str, Any]:
        """
        Busca um produto por ID.
        
        Args:
            product_id: ID do produto
            
        Returns:
            Dicionário com dados do produto
        """
        try:
            url = f"{self.api_base_url}/products/{product_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'product': data
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Erro ao buscar produto: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f"Erro HTTP {response.status}"
                        }
        
        except Exception as e:
            logger.error(f"Erro ao buscar produto por ID: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def parse_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa chamada de ferramenta do Dialogflow.
        
        Args:
            tool_name: Nome da ferramenta chamada
            parameters: Parâmetros da chamada
            
        Returns:
            Resultado da execução da ferramenta
        """
        if tool_name == "search_products":
            # Executar busca de forma assíncrona
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    self.search_products(
                        query=parameters.get('query'),
                        category=parameters.get('category'),
                        min_price=parameters.get('min_price'),
                        max_price=parameters.get('max_price'),
                        limit=parameters.get('limit', 10)
                    )
                )
            except Exception as e:
                logger.error(f"Erro ao processar chamada de ferramenta: {e}")
                return {'success': False, 'error': str(e)}
        
        return {'success': False, 'error': f'Ferramenta desconhecida: {tool_name}'}

