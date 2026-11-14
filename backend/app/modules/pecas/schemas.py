import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import PecaClassificacao, PecaCondicao, PecaDestino


class PecaCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    descricao: str | None = Field(None, max_length=4000)
    classificacao: PecaClassificacao
    condicao: PecaCondicao | None = Field(None, description="Obrigatória para peça reutilizável")
    destino: PecaDestino

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("nome muito curto")
        return v

    @model_validator(mode="after")
    def _condicao(self) -> "PecaCriar":
        if self.classificacao == PecaClassificacao.REUTILIZAVEL and self.condicao is None:
            raise ValueError("condicao é obrigatória para peça reutilizável")
        return self


class PecaAtualizar(BaseModel):
    destino: PecaDestino | None = None
    descaracterizada: bool | None = None

    @model_validator(mode="after")
    def _algum_campo(self) -> "PecaAtualizar":
        if self.destino is None and self.descaracterizada is None:
            raise ValueError("informe destino ou descaracterizada")
        return self


class Etiqueta(BaseModel):
    """Conteúdo do QR Code da peça reutilizável. RF-09, Anexo III, item 8."""

    nome: str
    chassi: str
    data: date
    cnpj: str = Field(description="CNPJ da empresa de desmontagem")
    codigo: str


class PecaSaida(BaseModel):
    id: uuid.UUID
    veiculo_id: uuid.UUID
    chassi: str
    nome: str
    descricao: str | None
    classificacao: PecaClassificacao
    codigo_rastreio: str | None
    condicao: PecaCondicao | None
    destino: PecaDestino | None
    descaracterizada: bool
    criado_em: datetime
    etiqueta: Etiqueta | None = Field(description="Só para peça reutilizável")


class RastreioSaida(Etiqueta):
    """Consulta pública: só a etiqueta e o destino atual, nada mais (RF-09)."""

    destino: PecaDestino | None
