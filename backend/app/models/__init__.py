"""Todos os modelos SQLAlchemy. Dono: fundação. Outros agentes não alteram esta pasta."""

from app.models.auditoria import EventoAuditoria
from app.models.base import Base
from app.models.configuracao import ConfigFator, ConfigParametro
from app.models.documentos import Certificado, Laudo
from app.models.empresa import Empresa, Usuario, Vinculo
from app.models.enums import (
    PAPEIS_SEM_EMPRESA,
    AnexoTipo,
    ChaveParametro,
    CredenciamentoStatus,
    DestinoPesagem,
    DocumentoEntradaTipo,
    EstadoVeiculo,
    EtapaTipo,
    Fracao,
    LancamentoTipo,
    MmvStatus,
    OrigemAquisicao,
    Papel,
    PecaClassificacao,
    PecaCondicao,
    PecaDestino,
    TipoEmpresa,
    TipoVeiculo,
    UrvCreditoStatus,
)
from app.models.mmv import Mmv
from app.models.urv import Consumo, ConsumoChassi, UrvCredito, UrvLancamento
from app.models.veiculo import Anexo, Dmr, Etapa, Peca, Pesagem, Veiculo

__all__ = [
    "PAPEIS_SEM_EMPRESA",
    "Anexo",
    "AnexoTipo",
    "Base",
    "Certificado",
    "ChaveParametro",
    "ConfigFator",
    "ConfigParametro",
    "Consumo",
    "ConsumoChassi",
    "CredenciamentoStatus",
    "DestinoPesagem",
    "Dmr",
    "DocumentoEntradaTipo",
    "Empresa",
    "EstadoVeiculo",
    "Etapa",
    "EtapaTipo",
    "EventoAuditoria",
    "Fracao",
    "Laudo",
    "LancamentoTipo",
    "Mmv",
    "MmvStatus",
    "OrigemAquisicao",
    "Papel",
    "Peca",
    "PecaClassificacao",
    "PecaCondicao",
    "PecaDestino",
    "Pesagem",
    "TipoEmpresa",
    "TipoVeiculo",
    "UrvCredito",
    "UrvCreditoStatus",
    "UrvLancamento",
    "Usuario",
    "Veiculo",
    "Vinculo",
]
