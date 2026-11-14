import re
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.models import (
    AnexoTipo,
    DocumentoEntradaTipo,
    EstadoVeiculo,
    EtapaTipo,
    OrigemAquisicao,
    TipoVeiculo,
)


def normalizar_chassi(valor: str) -> str:
    return re.sub(r"[\s.-]", "", valor or "").upper()


class VeiculoCriar(BaseModel):
    """Recepção do veículo. RF-06, art. 6º I; art. 18 III; Anexo III 14.a."""

    chassi: str = Field(description="Só letras e dígitos; gravado em maiúsculas")
    placa: str
    renavam: str
    data_entrada: date
    tipo: TipoVeiculo = Field(description="Tipo declarado; o efetivo depende da evidência (RF-07)")
    origem_aquisicao: OrigemAquisicao
    documento_entrada_tipo: DocumentoEntradaTipo
    documento_entrada_numero: str = Field(min_length=1, max_length=60)
    certidao_baixa_numero: str = Field(min_length=1, max_length=60)
    peso_entrada_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    sem_viabilidade_desmontagem: bool = False

    @field_validator("chassi")
    @classmethod
    def _chassi(cls, v: str) -> str:
        v = normalizar_chassi(v)
        if not re.fullmatch(r"[A-Z0-9]{6,30}", v):
            raise ValueError("chassi deve ter de 6 a 30 letras ou dígitos")
        return v

    @field_validator("placa")
    @classmethod
    def _placa(cls, v: str) -> str:
        v = re.sub(r"[\s-]", "", v).upper()
        if not re.fullmatch(r"[A-Z0-9]{7}", v):
            raise ValueError("placa deve ter 7 letras ou dígitos")
        return v

    @field_validator("renavam")
    @classmethod
    def _renavam(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\d{9,11}", v):
            raise ValueError("renavam deve ter de 9 a 11 dígitos")
        return v

    @field_validator("documento_entrada_numero", "certidao_baixa_numero")
    @classmethod
    def _sem_espacos(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("não pode ser vazio")
        return v

    @field_validator("data_entrada")
    @classmethod
    def _data(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("data_entrada não pode estar no futuro")
        return v


class VeiculoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empresa_id: uuid.UUID
    chassi: str
    placa: str | None
    renavam: str | None
    data_entrada: date
    tipo_declarado: TipoVeiculo
    tipo: TipoVeiculo
    origem_aquisicao: OrigemAquisicao
    documento_entrada_tipo: DocumentoEntradaTipo
    documento_entrada_numero: str
    certidao_baixa_numero: str | None
    peso_entrada_kg: Decimal | None
    sem_viabilidade_desmontagem: bool
    estado: EstadoVeiculo
    criado_em: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rebaixado(self) -> bool:
        """Verdadeiro enquanto falta a evidência de classificação (RF-07)."""
        return self.tipo != self.tipo_declarado


class EtapaEntrada(BaseModel):
    iniciada_em: AwareDatetime
    concluida_em: AwareDatetime | None = None
    observacoes: str | None = Field(None, max_length=4000)

    @model_validator(mode="after")
    def _ordem(self) -> "EtapaEntrada":
        if self.concluida_em is not None and self.concluida_em < self.iniciada_em:
            raise ValueError("concluida_em não pode ser anterior a iniciada_em")
        return self


class EtapaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    veiculo_id: uuid.UUID
    tipo: EtapaTipo
    iniciada_em: datetime
    concluida_em: datetime | None
    observacoes: str | None


class AnexoSaida(BaseModel):
    """O caminho no disco não é exposto; baixe por GET /anexos/{id}/arquivo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    veiculo_id: uuid.UUID
    etapa_tipo: EtapaTipo | None
    tipo: AnexoTipo
    sha256: str
    nome_original: str | None
    content_type: str | None
    tamanho_bytes: int | None
    enviado_por: uuid.UUID
    criado_em: datetime


class VeiculoDetalhe(VeiculoSaida):
    etapas: list[EtapaSaida]
    anexos: list[AnexoSaida]
    pendencias_certificado: list[str]
    percentual_aproveitado: Decimal | None = Field(description="Em pontos, de 0 a 100; nulo sem pesagens")
    laudo_id: uuid.UUID | None
    certificado_id: uuid.UUID | None
