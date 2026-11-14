import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.cnpj import cnpj_valido, normalizar_cnpj
from app.models import DestinoPesagem, Fracao


class PesagemCriar(BaseModel):
    fracao: Fracao
    destino: DestinoPesagem
    peso_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class PesagemSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    veiculo_id: uuid.UUID
    fracao: Fracao
    destino: DestinoPesagem
    peso_kg: Decimal
    criado_em: datetime


class PesagensSaida(BaseModel):
    """Lista de pesagens do veículo com o resumo do aproveitamento. RF-11 e RF-12."""

    itens: list[PesagemSaida]
    total: int
    peso_total_kg: Decimal
    percentual_aproveitado: Decimal | None = Field(description="Em pontos, de 0 a 100; nulo sem pesagens")
    meta_ano: Decimal | None = Field(description="Meta do ano corrente em pontos; nula até 2026")
    atende_meta: bool | None = Field(
        description="Alerta, não bloqueio (art. 17 §2º); nulo sem meta ou pesagem"
    )


class DmrCriar(BaseModel):
    numero: str = Field(min_length=1, max_length=60)
    destinatario_nome: str = Field(min_length=2, max_length=200)
    destinatario_cnpj: str = Field(description="Com ou sem máscara; gravado só com dígitos")
    tipo_material: str = Field(min_length=1, max_length=100)
    peso_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=3)

    @field_validator("destinatario_cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        if not cnpj_valido(v):
            raise ValueError("CNPJ inválido")
        return normalizar_cnpj(v)

    @field_validator("numero", "destinatario_nome", "tipo_material")
    @classmethod
    def _texto(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("não pode ser vazio")
        return v


class DmrSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    veiculo_id: uuid.UUID
    numero: str
    mtr_numero: str
    destinatario_nome: str
    destinatario_cnpj: str
    tipo_material: str
    peso_kg: Decimal
    emitida_em: datetime
