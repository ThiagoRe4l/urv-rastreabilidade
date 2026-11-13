import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EventoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequencia: int
    ocorrido_em: datetime
    usuario_id: uuid.UUID | None
    empresa_id: uuid.UUID | None
    tipo: str
    entidade: str
    entidade_id: uuid.UUID | None
    payload: dict[str, Any]
    hash_anterior: str
    hash: str


class VerificacaoSaida(BaseModel):
    integra: bool
    total: int
    primeira_quebra: int | None
