"""Modelos para upload de arquivos."""
from pydantic import BaseModel
from typing import Optional


class UploadResponse(BaseModel):
    """Resposta do upload."""
    success: bool
    message: str
    transcription: Optional[str] = None
    file_id: Optional[str] = None
    error: Optional[str] = None

