"""Schemas do livro de URV. Todo `Decimal` sai como string no JSON (docs/03-contrato-api.md)."""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models import LancamentoTipo, TipoVeiculo, UrvCreditoStatus
from app.modules.empresas.schemas import EmpresaResumo

# Limite por requisição; um consumo maior é registrado em mais de uma chamada.
MAX_CHASSIS_POR_CONSUMO = 10_000

# VIN de veículo novo: 17 caracteres, sem I, O e Q (ABNT NBR 6066 / ISO 3779). Art. 8º III.
_VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def normalizar_chassi(valor: str) -> str:
    return re.sub(r"[\s-]", "", valor or "").upper()


class SaldoSaida(BaseModel):
    empresa_id: uuid.UUID
    saldo: Decimal
    regularizar_ate: date | None = Field(
        None, description="Só com saldo negativo: prazo do consumo que abriu o saldo devedor (art. 8º §1º)"
    )


class LancamentoSaida(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    tipo: LancamentoTipo
    quantidade: Decimal = Field(description="Com sinal: positivo entra, negativo sai")
    credito_id: uuid.UUID | None
    consumo_id: uuid.UUID | None
    contraparte_id: uuid.UUID | None
    contraparte: EmpresaResumo | None
    criado_em: datetime


class CertificadoResumo(BaseModel):
    id: uuid.UUID
    numero: str
    tipo_veiculo: TipoVeiculo
    fator: Decimal
    emitido_em: datetime


class CreditoSaida(BaseModel):
    id: uuid.UUID
    certificado_id: uuid.UUID
    certificado: CertificadoResumo
    chassi: str
    geradora_id: uuid.UUID
    geradora: EmpresaResumo
    titular_id: uuid.UUID
    titular: EmpresaResumo
    quantidade: Decimal
    status: UrvCreditoStatus
    criado_em: datetime


class TransferenciaCriar(BaseModel):
    fabricante_id: uuid.UUID


class _PrecoMedio(BaseModel):
    mmv_id: uuid.UUID
    preco_medio: Decimal = Field(
        gt=0, max_digits=14, decimal_places=2, description="Pm, em reais (art. 3º §4º). Prefira string."
    )


class ConsumoSimular(_PrecoMedio):
    quantidade: int = Field(gt=0, le=MAX_CHASSIS_POR_CONSUMO, description="Qv: veículos comercializados")


class ConsumoCriar(_PrecoMedio):
    periodo: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$", description="Mês da comercialização, AAAA-MM")
    chassis: list[str] = Field(min_length=1, max_length=MAX_CHASSIS_POR_CONSUMO)

    @field_validator("chassis")
    @classmethod
    def _chassis(cls, valores: list[str]) -> list[str]:
        normalizados = [normalizar_chassi(v) for v in valores]
        invalidos = [v for v in normalizados if not _VIN.match(v)]
        if invalidos:
            raise ValueError(
                "chassi inválido (VIN de 17 caracteres, sem I, O e Q): " + ", ".join(invalidos[:5])
            )
        return normalizados


class MemoriaCalculo(BaseModel):
    """Como o débito foi calculado. RF-18, art. 3º §3º."""

    formula: str
    qv: int
    nivel: int
    rm: int
    pm: Decimal
    pb: Decimal
    razao_preco: Decimal = Field(description="pm / pb, com quatro casas")
    multiplicador: Decimal = Field(description="max(1, pm / pb), com quatro casas")


class SimulacaoSaida(BaseModel):
    urv_debito: Decimal
    saldo_atual: Decimal
    saldo_apos: Decimal
    saldo_suficiente: bool
    permitido: bool = Field(description="Falso quando o registro seria rejeitado por saldo (art. 8º III)")
    regularizar_ate: date | None = Field(None, description="Prazo, se o registro gerasse saldo devedor")
    prazo_saldo_negativo: date = Field(description="Último dia em que se aceita saldo negativo (art. 8º §1º)")
    memoria_calculo: MemoriaCalculo


class ConsumoSaida(BaseModel):
    id: uuid.UUID
    fabricante_id: uuid.UUID
    mmv_id: uuid.UUID
    mmv_codigo: str | None
    periodo: str
    qv: int
    rm: int
    pm: Decimal
    pb: Decimal
    urv_debito: Decimal
    saldo_apos: Decimal
    regularizar_ate: date | None
    prazo_reporte: date
    registrado_em: datetime
    fora_do_prazo: bool = Field(description="Registrado depois do décimo dia útil do mês seguinte (art. 7º)")
    chassis: list[str]
