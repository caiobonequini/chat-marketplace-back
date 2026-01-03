"""Serviço de integração com Dialogflow CX."""
import asyncio
from typing import Optional, AsyncIterator, Dict, Any
from google.cloud.dialogflowcx_v3beta1 import (
    SessionsClient,
    DetectIntentRequest,
    StreamingDetectIntentRequest,
    QueryInput,
    AudioInput,
    InputAudioConfig,
    AudioEncoding,
)
from google.cloud.dialogflowcx_v3beta1.types import audio_config
from google.cloud.dialogflowcx_v3beta1.types import session
from google.cloud.dialogflowcx_v3beta1.types.session import TextInput
from google.api_core import exceptions as gcp_exceptions
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class DialogflowService:
    """Serviço para interagir com Dialogflow CX."""
    
    def __init__(self):
        """Inicializa o serviço Dialogflow."""
        self.project_id = settings.google_cloud_project_id
        self.agent_id = settings.dialogflow_agent_id
        self.location = settings.dialogflow_location
        self.language_code = settings.dialogflow_language_code
        
        # IMPORTANTE: O Dialogflow CX pode usar localização física (us-central1) ou multirregião (us/eu/global)
        # Se dialogflow_region_id está configurado, usar diretamente
        # Caso contrário, usar a localização física diretamente (não mapear)
        if hasattr(settings, 'dialogflow_region_id') and settings.dialogflow_region_id:
            self.region_id = settings.dialogflow_region_id.lower()
            logger.info(f"Usando region_id configurado explicitamente: {self.region_id}")
        elif self.location.lower() == "global":
            self.region_id = "global"
        else:
            # Para localizações físicas (us-central1, europe-west1, etc), usar diretamente
            # O Dialogflow CX aceita localizações físicas no session_path
            self.region_id = self.location.lower()
            logger.info(f"Usando localização física diretamente: {self.region_id}")
        
        # Caminho completo do agente (usa region_id/localização física)
        self.agent_path = f"projects/{self.project_id}/locations/{self.region_id}/agents/{self.agent_id}"
        logger.debug(f"Agent path: {self.agent_path}")
        
        # Cliente de sessões
        self.client: Optional[SessionsClient] = None
        
        logger.info(
            f"DialogflowService inicializado: "
            f"project={self.project_id}, agent={self.agent_id}, "
            f"location={self.location}, region_id={self.region_id}"
        )
    
    async def initialize(self):
        """Inicializa o cliente Dialogflow de forma assíncrona."""
        try:
            # Criar cliente com configuração de região
            # Segundo a documentação do Dialogflow CX:
            # - Para região 'global': usar 'dialogflow.googleapis.com' (sem prefixo)
            # - Para localizações físicas (us-central1, europe-west1): usar '{location}-dialogflow.googleapis.com'
            # - Para regiões multirregião (us, eu): usar '{region_id}-dialogflow.googleapis.com'
            client_options = None
            if self.region_id == "global":
                # Para região global, usar endpoint padrão sem prefixo de região
                api_endpoint = "dialogflow.googleapis.com:443"
                from google.api_core import client_options as google_client_options
                client_options = google_client_options.ClientOptions(
                    api_endpoint=api_endpoint
                )
                logger.debug(f"Configurando endpoint para região global: {api_endpoint}")
            elif self.region_id in ["us", "eu"]:
                # Para regiões multirregião (us, eu), usar endpoint com prefixo de região
                api_endpoint = f"{self.region_id}-dialogflow.googleapis.com:443"
                from google.api_core import client_options as google_client_options
                client_options = google_client_options.ClientOptions(
                    api_endpoint=api_endpoint
                )
                logger.debug(f"Configurando endpoint para região multirregião {self.region_id}: {api_endpoint}")
            else:
                # Para localizações físicas (us-central1, europe-west1, etc), usar endpoint com localização física
                api_endpoint = f"{self.region_id}-dialogflow.googleapis.com:443"
                from google.api_core import client_options as google_client_options
                client_options = google_client_options.ClientOptions(
                    api_endpoint=api_endpoint
                )
                logger.debug(f"Configurando endpoint para localização física {self.region_id}: {api_endpoint}")
            
            # Criar cliente em thread separada para não bloquear
            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(
                None,
                lambda: SessionsClient(client_options=client_options)
            )
            logger.info(
                f"Cliente Dialogflow inicializado com sucesso "
                f"(location={self.location}, region_id={self.region_id}, "
                f"endpoint={client_options.api_endpoint if client_options else 'default'})"
            )
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente Dialogflow: {e}")
            raise
    
    def _get_session_path(self, session_id: str) -> str:
        """Retorna o caminho completo da sessão."""
        session_path = f"{self.agent_path}/sessions/{session_id}"
        logger.debug(f"DEBUG: Session Path gerado: {session_path}")
        return session_path
    
    async def streaming_detect_intent(
        self,
        session_id: str,
        audio_chunks: AsyncIterator[bytes],
        sample_rate: int = 16000
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Detecta intenção usando streaming de áudio.
        
        Args:
            session_id: ID da sessão
            audio_chunks: AsyncIterator de chunks de áudio
            sample_rate: Taxa de amostragem do áudio
            
        Yields:
            Dicionários com respostas do Dialogflow
        """
        if not self.client:
            await self.initialize()
        
        session_path = self._get_session_path(session_id)
        
        # Configurar entrada de áudio
        audio_config = InputAudioConfig(
            audio_encoding=AudioEncoding.AUDIO_ENCODING_LINEAR_16,
            sample_rate_hertz=sample_rate,
            single_utterance=False,  # Permite múltiplas interações
        )
        
        # Criar AudioInput com a configuração
        audio_input = AudioInput(config=audio_config)
        
        # QueryInput precisa incluir language_code
        query_input = QueryInput(
            audio=audio_input,
            language_code=self.language_code
        )
        
        try:
            # Criar requisição inicial
            # Nota: Não usamos OutputAudioConfig - usamos Vertex AI TTS diretamente
            initial_request = StreamingDetectIntentRequest(
                session=session_path,
                query_input=query_input,
            )
            
            # Coletar todos os chunks primeiro (necessário para o generator síncrono)
            audio_chunks_list = []
            async for chunk in audio_chunks:
                audio_chunks_list.append(chunk)
            
            # Verificar se há chunks para processar
            if not audio_chunks_list:
                logger.warning("Nenhum chunk de áudio recebido")
                yield {'error': 'Nenhum chunk de áudio recebido'}
                return
            
            # Criar stream de requisições (síncrono)
            # Usar closure para capturar variáveis necessárias
            def request_generator():
                """Gera requisições de streaming."""
                # Enviar requisição inicial
                logger.debug("Enviando requisição inicial")
                yield initial_request
                
                # Enviar chunks de áudio
                logger.debug(f"Enviando {len(audio_chunks_list)} chunks de áudio")
                for idx, audio_chunk in enumerate(audio_chunks_list):
                    if not audio_chunk:
                        logger.warning(f"Chunk {idx} está vazio, pulando")
                        continue
                    
                    try:
                        # Para requisições subsequentes, o áudio deve estar dentro de query_input
                        # Estrutura: StreamingDetectIntentRequest -> QueryInput -> AudioInput -> audio (bytes)
                        # IMPORTANTE: QueryInput precisa incluir language_code mesmo para chunks subsequentes
                        audio_input = AudioInput(audio=audio_chunk)
                        query_input = QueryInput(
                            audio=audio_input,
                            language_code=self.language_code
                        )
                        
                        request = StreamingDetectIntentRequest(
                            session=session_path,
                            query_input=query_input,
                        )
                        yield request
                    except Exception as e:
                        logger.error(f"Erro ao criar requisição para chunk {idx}: {e}")
                        raise
            
            # Executar streaming em thread separada
            loop = asyncio.get_event_loop()
            
            def run_streaming():
                """Executa streaming de forma síncrona."""
                responses = []
                try:
                    logger.debug("Iniciando streaming_detect_intent")
                    # Criar o generator
                    request_gen = request_generator()
                    
                    # Chamar streaming_detect_intent
                    stream = self.client.streaming_detect_intent(request_gen)
                    
                    # Iterar sobre as respostas
                    logger.debug("Iterando sobre respostas do stream")
                    for response in stream:
                        if response:
                            responses.append(response)
                            logger.debug(f"Resposta recebida: {type(response)}")
                    
                    logger.info(f"Streaming concluído. {len(responses)} respostas recebidas")
                except Exception as e:
                    logger.error(f"Erro no streaming Dialogflow: {e}", exc_info=True)
                    raise
                return responses
            
            # Executar e aguardar respostas
            try:
                responses = await loop.run_in_executor(None, run_streaming)
            except Exception as e:
                logger.error(f"Erro ao executar streaming: {e}", exc_info=True)
                yield {'error': str(e)}
                return
            
            # Processar respostas
            if not responses:
                logger.warning("Nenhuma resposta recebida do Dialogflow")
                yield {'error': 'Nenhuma resposta recebida do Dialogflow'}
                return
            
            # Variável para armazenar transcrição do usuário (pode vir em resposta intermediária)
            user_transcription_found = None
            
            for response in responses:
                result = {}
                
                # DEBUG: Logar estrutura completa da resposta
                logger.debug(f"Tipo de resposta: {type(response)}")
                logger.debug(f"Atributos da resposta: {[attr for attr in dir(response) if not attr.startswith('_')]}")
                
                # Verificar se há transcrição em respostas intermediárias
                # No Dialogflow CX, a transcrição pode vir em uma resposta antes do detect_intent_response
                if hasattr(response, 'recognition_result') and response.recognition_result:
                    logger.debug(f"recognition_result encontrado: {response.recognition_result}")
                    if hasattr(response.recognition_result, 'transcript'):
                        user_transcription_found = response.recognition_result.transcript
                        logger.info(f"✅ Transcrição encontrada em recognition_result: {user_transcription_found}")
                
                # Verificar outros campos possíveis
                if hasattr(response, 'recognition_result'):
                    logger.debug(f"recognition_result existe: {response.recognition_result}")
                if hasattr(response, 'query_result'):
                    logger.debug(f"query_result existe diretamente na resposta")
                
                # Detectar intenção
                if response.detect_intent_response:
                    detect_response = response.detect_intent_response
                    
                    # DEBUG: Logar estrutura completa do query_result para entender o que está disponível
                    logger.debug(f"QueryResult disponível: {dir(detect_response.query_result)}")
                    if hasattr(detect_response.query_result, 'query_text'):
                        logger.debug(f"query_text existe: {detect_response.query_result.query_text}")
                    if hasattr(detect_response.query_result, 'transcript'):
                        logger.debug(f"transcript existe: {detect_response.query_result.transcript}")
                    if hasattr(detect_response.query_result, 'input_text'):
                        logger.debug(f"input_text existe: {detect_response.query_result.input_text}")
                    
                    # TRANSCRIÇÃO DO USUÁRIO (query_text) - o que o usuário realmente falou
                    # Dialogflow CX retorna a transcrição do usuário em query_result.query_text
                    # ou em query_result.transcript (dependendo da versão)
                    user_transcription = None
                    if hasattr(detect_response.query_result, 'query_text') and detect_response.query_result.query_text:
                        user_transcription = detect_response.query_result.query_text
                        logger.info(f"Transcrição do usuário capturada via query_text: {user_transcription}")
                    elif hasattr(detect_response.query_result, 'transcript') and detect_response.query_result.transcript:
                        user_transcription = detect_response.query_result.transcript
                        logger.info(f"Transcrição do usuário capturada via transcript: {user_transcription}")
                    elif hasattr(detect_response.query_result, 'input_text') and detect_response.query_result.input_text:
                        user_transcription = detect_response.query_result.input_text
                        logger.info(f"Transcrição do usuário capturada via input_text: {user_transcription}")
                    else:
                        # Tentar acessar diretamente os atributos disponíveis
                        logger.warning(f"Nenhum campo de transcrição encontrado. Atributos disponíveis: {[attr for attr in dir(detect_response.query_result) if not attr.startswith('_')]}")
                        # Para streaming, a transcrição pode vir em uma resposta intermediária
                        # Vamos tentar pegar de qualquer lugar possível
                        try:
                            # Verificar se há um campo 'text' ou similar
                            if hasattr(detect_response.query_result, 'text'):
                                user_transcription = detect_response.query_result.text
                                logger.info(f"Transcrição do usuário capturada via text: {user_transcription}")
                        except Exception as e:
                            logger.debug(f"Erro ao tentar acessar campo text: {e}")
                    
                    # Usar transcrição encontrada em recognition_result se disponível
                    if user_transcription_found:
                        result['user_transcription'] = user_transcription_found
                        logger.info(f"✅ Transcrição do usuário (de recognition_result): {user_transcription_found}")
                    elif user_transcription:
                        result['user_transcription'] = user_transcription
                        logger.info(f"✅ Transcrição do usuário (de query_result): {user_transcription}")
                    else:
                        logger.warning("⚠️ Nenhuma transcrição do usuário foi encontrada na resposta do Dialogflow")
                        # FALLBACK TEMPORÁRIO: Se não houver transcrição, usar placeholder
                        # Isso mantém o diálogo funcionando enquanto investigamos o problema
                        result['user_transcription'] = "[Transcrição não disponível]"
                        logger.warning("⚠️ Usando placeholder para transcrição - investigar estrutura do Dialogflow")
                    
                    # RESPOSTA DO BOT (response_messages) - o que o bot respondeu
                    if detect_response.query_result.response_messages:
                        for message in detect_response.query_result.response_messages:
                            if message.text:
                                result['text'] = message.text.text[0]  # Resposta do bot
                    
                    # Intenção detectada
                    if detect_response.query_result.intent:
                        result['intent'] = {
                            'name': detect_response.query_result.intent.display_name,
                            'confidence': detect_response.query_result.intent_detection_confidence,
                        }
                    
                    # Parâmetros
                    if detect_response.query_result.parameters:
                        result['parameters'] = dict(detect_response.query_result.parameters)
                    
                    # Nota: Não extraímos output_audio - usamos Vertex AI TTS diretamente
                    # O áudio será gerado no websocket_handler usando o texto da resposta
                    
                    # Fulfillment (chamadas de ferramentas)
                    if detect_response.query_result.response_messages:
                        for message in detect_response.query_result.response_messages:
                            if message.payload:
                                result['payload'] = dict(message.payload)
                    
                    yield result
                
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Erro na API do Google: {e}")
            yield {'error': str(e)}
        except Exception as e:
            logger.error(f"Erro no streaming detect intent: {e}")
            yield {'error': str(e)}
    
    async def detect_intent_text(
        self,
        session_id: str,
        text: str
    ) -> Dict[str, Any]:
        """
        Detecta intenção usando texto.
        
        Args:
            session_id: ID da sessão
            text: Texto da consulta
            
        Returns:
            Dicionário com resultado da detecção
        """
        if not self.client:
            await self.initialize()
        
        session_path = self._get_session_path(session_id)
        
        # Criar TextInput com o texto
        text_input = TextInput(text=text)
        query_input = QueryInput(text=text_input, language_code=self.language_code)
        
        request = DetectIntentRequest(
            session=session_path,
            query_input=query_input,
        )
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.detect_intent(request=request)
            )
            
            result = {}
            
            if response.query_result.response_messages:
                for message in response.query_result.response_messages:
                    if message.text:
                        result['text'] = message.text.text[0]
            
            if response.query_result.intent:
                result['intent'] = {
                    'name': response.query_result.intent.display_name,
                    'confidence': response.query_result.intent_detection_confidence,
                }
            
            if response.query_result.parameters:
                result['parameters'] = dict(response.query_result.parameters)
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao detectar intenção: {e}")
            return {'error': str(e)}

