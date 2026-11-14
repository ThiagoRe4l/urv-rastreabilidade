import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class DivergenciaSaida(BaseModel):
    verificacao: str = Field(description="CREDITO_FATOR, FATOR_VIGENTE, LANCAMENTO, SALDO ou TRILHA")
    entidade: str
    entidade_id: uuid.UUID
    detalhe: str


class ReconciliacaoSaida(BaseModel):
    """Registros de negócio conferidos contra o que os sustenta. RF-22, art. 20 V; art. 24 I."""

    conciliado: bool = Field(description="Verdadeiro sem nenhuma divergência")
    verificados: dict[str, int] = Field(description="Quantos registros de cada tipo foram conferidos")
    divergencias: list[DivergenciaSaida]
    total_divergencias: int
