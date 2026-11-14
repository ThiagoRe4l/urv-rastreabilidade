from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import DestinoPesagem, Fracao


class MaterialSaida(BaseModel):
    fracao: Fracao
    destino: DestinoPesagem
    peso_kg: Decimal


class RelatorioMdicSaida(BaseModel):
    """Art. 27, incisos I e II. Incidentes e plano de atualização ficam fora do MVP (RF-24)."""

    ano: int
    registros: int = Field(description="Veículos em fim de vida com entrada no ano")
    certificados_emitidos: int
    urv_gerada: Decimal = Field(description="Soma dos créditos dos certificados emitidos no ano")
    urv_transferida: Decimal
    urv_consumida: Decimal
    materiais: list[MaterialSaida] = Field(description="Peso rastreado por fração e destino")
    peso_total_kg: Decimal
