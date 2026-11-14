import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import TipoVeiculo, UrvCreditoStatus
from app.modules.veiculos.schemas import VeiculoSaida


class LaudoCriar(BaseModel):
    """Dados pessoais mínimos: nome e registro do responsável técnico (RNF-02)."""

    responsavel_nome: str = Field(min_length=2, max_length=200)
    responsavel_registro: str = Field(min_length=1, max_length=60, description="Registro profissional")

    @field_validator("responsavel_nome", "responsavel_registro")
    @classmethod
    def _texto(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("não pode ser vazio")
        return v


class AssinaturaSaida(BaseModel):
    algoritmo: str = Field(description='"SIMULADA-..." no MVP: prova integridade, não identidade')
    valor: str


class LaudoSaida(BaseModel):
    id: uuid.UUID
    veiculo_id: uuid.UUID
    responsavel_nome: str
    responsavel_registro: str
    assinado_em: datetime
    hash_conteudo: str
    assinatura: AssinaturaSaida | None


class CreditoResumo(BaseModel):
    """Crédito de URV gerado pelo certificado (RF-16). O livro é do módulo `urv`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quantidade: Decimal
    status: UrvCreditoStatus
    geradora_id: uuid.UUID
    titular_id: uuid.UUID


class CertificadoSaida(BaseModel):
    id: uuid.UUID
    numero: str
    veiculo_id: uuid.UUID
    chassi: str
    empresa_id: uuid.UUID
    tipo_veiculo: TipoVeiculo
    fator: Decimal
    percentual_aproveitado: Decimal | None = Field(description="Em pontos, de 0 a 100")
    meta_ano: Decimal | None = Field(description="Nula em 2026 (art. 18 §7º)")
    atende_meta: bool | None = Field(description="Alerta, não bloqueio (RF-12)")
    emitido_em: datetime
    hash_conteudo: str
    credito: CreditoResumo | None


class CertificadoDetalhe(CertificadoSaida):
    laudo: LaudoSaida | None
    veiculo: VeiculoSaida
