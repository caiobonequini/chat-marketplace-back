"""Estratégias de chat usando Pattern Strategy."""
import abc
import json
from typing import Dict, Any, Optional, AsyncIterator
from google.cloud import dialogflowcx_v3beta1 as dialogflow
from google.api_core import exceptions as gcp_exceptions
from services.marketplace_client import MarketplaceClient
from utils.logger import get_logger

logger = get_logger(__name__)


class IChatStrategy(abc.ABC):
    """Interface para estratégias de chat."""
    
    @abc.abstractmethod
    async def send_message(
        self,
        message: str,
        history: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Envia uma mensagem e retorna a resposta.
        
        Args:
            message: Mensagem do usuário
            history: Histórico de mensagens (opcional)
            **kwargs: Parâmetros adicionais específicos da estratégia
            
        Returns:
            Dicionário com a resposta do chat
        """
        pass
    
    @abc.abstractmethod
    async def initialize(self):
        """Inicializa a estratégia."""
        pass
    
    @abc.abstractmethod
    async def cleanup(self):
        """Limpa recursos da estratégia."""
        pass


class NotebookMVStrategy(IChatStrategy, MarketplaceClient):
    """Estratégia usando NotebookMV (RAG) via API Gateway MV."""
    
    def __init__(
        self,
        api_key: str,
        workspace_id: str,
        base_url: str = "https://notebook-mv-back-dev-829403472317.us-central1.run.app"
    ):
        """
        Inicializa a estratégia NotebookMV.
        
        Args:
            api_key: Chave de API do cliente
            workspace_id: ID do workspace no NotebookMV
            base_url: URL base do serviço NotebookMV
        """
        MarketplaceClient.__init__(self, api_key, base_url)
        self.workspace_id = workspace_id
        logger.info(f"NotebookMVStrategy inicializado: workspace_id={workspace_id}")
    
    async def initialize(self):
        """Inicializa a estratégia."""
        # Testar conexão com endpoint de health
        try:
            response = await self.get("/api-key-teste")
            logger.info(f"NotebookMV health check: {response.status_code}")
        except Exception as e:
            logger.warning(f"Health check do NotebookMV falhou: {e}")
    
    async def send_message(
        self,
        message: str,
        history: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Envia mensagem para o NotebookMV.
        
        Args:
            message: Mensagem do usuário
            history: Histórico de mensagens (formato: [{"role": "user", "content": "..."}, ...])
            **kwargs: Parâmetros adicionais
            
        Returns:
            Resposta do NotebookMV
        """
        if history is None:
            history = []
        
        payload = {
            "message": message,
            "history": history
        }
        
        endpoint = f"/workspace/{self.workspace_id}/chat"
        
        try:
            response = await self.post(endpoint, json=payload)
            result = response.json()
            logger.info(f"NotebookMV resposta recebida: {len(result.get('response', ''))} caracteres")
            return {
                "text": result.get("response", result.get("message", "")),
                "source": "notebook_mv",
                "raw_response": result
            }
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para NotebookMV: {e}")
            return {
                "text": "Desculpe, ocorreu um erro ao processar sua mensagem.",
                "error": str(e),
                "source": "notebook_mv"
            }
    
    async def cleanup(self):
        """Limpa recursos."""
        await self.close()


class SofyaLLMStrategy(IChatStrategy, MarketplaceClient):
    """Estratégia usando Sofya/Clinical LLM via API Gateway MV."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://clinical-llm.aiaas.mv.com.br/v1",
        model: str = "medium-reasoning"
    ):
        """
        Inicializa a estratégia Sofya LLM.
        
        Args:
            api_key: Chave de API do cliente
            base_url: URL base do serviço Clinical LLM
            model: Nome do modelo (padrão: medium-reasoning)
        """
        MarketplaceClient.__init__(self, api_key, base_url)
        self.model = model
        logger.info(f"SofyaLLMStrategy inicializado: model={model}")
    
    async def initialize(self):
        """Inicializa a estratégia."""
        logger.debug("SofyaLLMStrategy inicializado")
    
    async def send_message(
        self,
        message: str,
        history: Optional[list] = None,
        temperature: float = 0.1,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Envia mensagem para o Sofya LLM.
        
        Args:
            message: Mensagem do usuário
            history: Histórico de mensagens (formato: [{"role": "user", "content": "..."}, ...])
            temperature: Temperatura do modelo (padrão: 0.1)
            **kwargs: Parâmetros adicionais
            
        Returns:
            Resposta do LLM
        """
        if history is None:
            history = []
        
        # Adicionar mensagem atual ao histórico
        input_messages = history + [{"role": "user", "content": message}]
        
        payload = {
            "input": input_messages,
            "temperature": temperature
        }
        
        headers = {
            "x-model": self.model
        }
        
        endpoint = "/responses"
        
        try:
            response = await self.post(endpoint, json=payload, headers=headers)
            result = response.json()
            
            # Extrair texto da resposta (ajustar conforme formato real da API)
            text = result.get("response", result.get("output", result.get("text", "")))
            if isinstance(text, list) and len(text) > 0:
                text = text[0].get("content", "") if isinstance(text[0], dict) else str(text[0])
            
            logger.info(f"Sofya LLM resposta recebida: {len(text)} caracteres")
            return {
                "text": text,
                "source": "sofya_llm",
                "model": self.model,
                "raw_response": result
            }
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para Sofya LLM: {e}")
            return {
                "text": "Desculpe, ocorreu um erro ao processar sua mensagem.",
                "error": str(e),
                "source": "sofya_llm"
            }
    
    async def cleanup(self):
        """Limpa recursos."""
        await self.close()


class DialogFlowDynamicStrategy(IChatStrategy):
    """Estratégia usando Dialogflow CX com credenciais dinâmicas (em memória)."""
    
    def __init__(
        self,
        credentials_json: Dict[str, Any],
        project_id: str,
        agent_id: str,
        location: str = "us-central1",
        language_code: str = "pt-BR"
    ):
        """
        Inicializa a estratégia Dialogflow com credenciais dinâmicas.
        
        Args:
            credentials_json: Credenciais do Google Cloud em formato dict (JSON parseado)
            project_id: ID do projeto Google Cloud
            agent_id: ID do agente Dialogflow CX
            location: Localização do agente (ex: us-central1)
            language_code: Código do idioma (padrão: pt-BR)
        """
        self.credentials_json = credentials_json
        self.project_id = project_id
        self.agent_id = agent_id
        self.location = location
        self.language_code = language_code
        self.client: Optional[dialogflow.SessionsClient] = None
        self.agent_path = f"projects/{project_id}/locations/{location}/agents/{agent_id}"
        logger.info(f"DialogFlowDynamicStrategy inicializado: project={project_id}, agent={agent_id}")
    
    async def initialize(self):
        """Inicializa o cliente Dialogflow com credenciais em memória."""
        import os
        import tempfile
        from google.oauth2 import service_account
        from google.auth import default
        
        try:
            # Criar credenciais a partir do JSON em memória
            credentials = service_account.Credentials.from_service_account_info(
                self.credentials_json
            )
            
            # Configurar endpoint baseado na localização
            client_options = None
            if self.location == "global":
                from google.api_core import client_options as google_client_options
                client_options = google_client_options.ClientOptions(
                    api_endpoint="dialogflow.googleapis.com:443"
                )
            else:
                from google.api_core import client_options as google_client_options
                client_options = google_client_options.ClientOptions(
                    api_endpoint=f"{self.location}-dialogflow.googleapis.com:443"
                )
            
            # Criar cliente em thread separada
            import asyncio
            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(
                None,
                lambda: dialogflow.SessionsClient(
                    credentials=credentials,
                    client_options=client_options
                )
            )
            logger.info("Cliente Dialogflow inicializado com credenciais dinâmicas")
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente Dialogflow: {e}")
            raise
    
    async def send_message(
        self,
        message: str,
        history: Optional[list] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Envia mensagem para o Dialogflow CX.
        
        Args:
            message: Mensagem do usuário
            history: Histórico (não usado diretamente, Dialogflow mantém contexto)
            session_id: ID da sessão Dialogflow
            **kwargs: Parâmetros adicionais
            
        Returns:
            Resposta do Dialogflow
        """
        if not self.client:
            await self.initialize()
        
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
        
        session_path = f"{self.agent_path}/sessions/{session_id}"
        
        from google.cloud.dialogflowcx_v3beta1.types import session as session_types
        
        query_input = session_types.QueryInput(
            text=session_types.TextInput(text=message),
            language_code=self.language_code
        )
        
        request = session_types.DetectIntentRequest(
            session=session_path,
            query_input=query_input
        )
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.detect_intent(request=request)
            )
            
            # Extrair texto da resposta
            text = ""
            if response.query_result.response_messages:
                for msg in response.query_result.response_messages:
                    if msg.text:
                        text = msg.text.text[0] if msg.text.text else ""
                        break
            
            intent_name = None
            confidence = 0.0
            if response.query_result.intent:
                intent_name = response.query_result.intent.display_name
                confidence = response.query_result.intent_detection_confidence
            
            logger.info(f"Dialogflow resposta recebida: intent={intent_name}, confidence={confidence}")
            
            return {
                "text": text,
                "source": "dialogflow",
                "intent": intent_name,
                "confidence": confidence,
                "session_id": session_id,
                "raw_response": {
                    "intent": intent_name,
                    "confidence": confidence,
                    "parameters": dict(response.query_result.parameters) if response.query_result.parameters else {}
                }
            }
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para Dialogflow: {e}")
            return {
                "text": "Desculpe, ocorreu um erro ao processar sua mensagem.",
                "error": str(e),
                "source": "dialogflow"
            }
    
    async def cleanup(self):
        """Limpa recursos."""
        if self.client:
            self.client.close()
            self.client = None
        logger.debug("DialogFlowDynamicStrategy limpo")

