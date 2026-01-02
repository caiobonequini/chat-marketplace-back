"""Configurações da aplicação."""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Configurações da aplicação."""
    
    # Google Cloud
    google_cloud_project_id: str
    dialogflow_agent_id: str
    dialogflow_location: str = "us-central1"  # Localização física ou 'global' se agente está em global
    dialogflow_region_id: Optional[str] = None  # ID de região (us/eu/global). Se None, será mapeado automaticamente
    google_application_credentials: Optional[str] = None
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # Audio
    # Configuração ideal para Vertex AI / Dialogflow CX: LINEAR16 @ 16000 Hz
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 4096
    vad_aggressiveness: int = 2
    
    # Dialogflow
    dialogflow_language_code: str = "pt-BR"
    dialogflow_enable_auto_sentiment: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instância global de configurações
settings = Settings()

# Configurar credenciais do Google Cloud se especificado
if settings.google_application_credentials:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

