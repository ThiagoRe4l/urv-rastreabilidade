import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models import Papel
from app.modules.empresas.schemas import EmpresaResumo


class LoginEntrada(BaseModel):
    # str simples: e-mails de demonstração usam o domínio reservado ".local".
    email: str = Field(min_length=3, max_length=254)
    senha: str = Field(min_length=1, max_length=200)


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: str
    papel: Papel
    empresa: EmpresaResumo | None


class LoginSaida(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    usuario: UsuarioSaida
