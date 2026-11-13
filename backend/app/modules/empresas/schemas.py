import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.core.cnpj import cnpj_valido, normalizar_cnpj
from app.models import CredenciamentoStatus, TipoEmpresa


class EmpresaResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cnpj: str
    razao_social: str
    tipo: TipoEmpresa


class EmpresaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cnpj: str
    razao_social: str
    tipo: TipoEmpresa
    credenciamento_status: CredenciamentoStatus | None
    credenciamento_validade: date | None
    registro_compromissos: bool
    criado_em: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def credenciamento_vigente(self) -> bool:
        """ATIVO e dentro da validade hoje (arts. 11 e 16). Sempre falso para FABRICANTE."""
        return (
            self.credenciamento_status == CredenciamentoStatus.ATIVO
            and self.credenciamento_validade is not None
            and self.credenciamento_validade >= date.today()
        )


class EmpresaCriar(BaseModel):
    cnpj: str = Field(description="Com ou sem máscara; gravado só com dígitos")
    razao_social: str = Field(min_length=2, max_length=200)
    tipo: TipoEmpresa
    registro_compromissos: bool | None = Field(
        None, description="Só para FABRICANTE: ato de registro de compromissos no MDIC (art. 8º II)"
    )

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        if not cnpj_valido(v):
            raise ValueError("CNPJ inválido")
        return normalizar_cnpj(v)

    @field_validator("razao_social")
    @classmethod
    def _razao(cls, v: str) -> str:
        return v.strip()


class EmpresaAtualizar(BaseModel):
    registro_compromissos: bool


class CredenciamentoAtualizar(BaseModel):
    status: CredenciamentoStatus
    validade: date | None = Field(None, description="Obrigatória quando status = ATIVO")


class VinculoCriar(BaseModel):
    geradora_id: uuid.UUID
    fabricante_id: uuid.UUID


class VinculoAtualizar(BaseModel):
    ativo: bool


class VinculoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    geradora_id: uuid.UUID
    fabricante_id: uuid.UUID
    ativo: bool
    criado_em: datetime
    geradora: EmpresaResumo
    fabricante: EmpresaResumo
