import re
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import MmvStatus


class MmvCriar(BaseModel):
    """Art. 5º, incisos I a III."""

    codigo: str = Field(min_length=1, max_length=60, description="Código de Marca/Modelo/Versão")
    ncm: str = Field(description="NCM de 8 dígitos, com ou sem pontos; gravado só com dígitos")
    nivel: int = Field(ge=1, le=2, description="Nível de reciclabilidade pretendido (1 ou 2)")
    percentual_reciclabilidade: Decimal = Field(
        ge=0, le=100, max_digits=5, decimal_places=2, description="Em pontos, de 0 a 100. Prefira string."
    )
    ja_comercializado: bool = Field(
        description="Já teve saída do estabelecimento ou desembaraço antes do cadastro (art. 5º §3º)"
    )

    @field_validator("codigo")
    @classmethod
    def _codigo(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("código vazio")
        return v

    @field_validator("ncm")
    @classmethod
    def _ncm(cls, v: str) -> str:
        digitos = re.sub(r"[.\s]", "", v or "")
        if not re.fullmatch(r"\d{8}", digitos):
            raise ValueError("NCM precisa ter 8 dígitos")
        return digitos


class MmvSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fabricante_id: uuid.UUID
    codigo: str
    ncm: str
    nivel: int
    percentual_reciclabilidade: Decimal
    ja_comercializado: bool
    efeitos_a_partir_de: date
    status: MmvStatus
    criado_em: datetime
    rm: int = Field(description="RM do nível vigente hoje em config_parametro (art. 3º §3º; lacuna L-01)")
