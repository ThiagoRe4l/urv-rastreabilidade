"""Leitura de fatores e parâmetros com vigência, e a rota GET /configuracao/fatores.

Os fatores e o preço base podem ser revistos (art. 3º §6º), por isso nada aqui é
constante no código: sempre leia o valor vigente na data da operação.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import usuario_atual
from app.core.erros import ErroNegocio
from app.models import ChaveParametro, ConfigFator, ConfigParametro, TipoVeiculo, Usuario


def fator_vigente(session: Session, tipo: TipoVeiculo, em: date) -> Decimal:
    """Fator de equivalência do tipo na data. RF-16, art. 3º §2º."""
    fator = session.scalar(
        select(ConfigFator.fator)
        .where(ConfigFator.tipo_veiculo == tipo, ConfigFator.vigente_desde <= em)
        .order_by(ConfigFator.vigente_desde.desc())
        .limit(1)
    )
    if fator is None:
        raise ErroNegocio(422, "FATOR_NAO_CONFIGURADO", f"Sem fator vigente para {tipo} em {em}.")
    return fator


def fatores_vigentes(session: Session, em: date) -> list[ConfigFator]:
    """Um registro por tipo de veículo: o mais recente com vigência até `em`."""
    linhas = session.scalars(
        select(ConfigFator)
        .where(ConfigFator.vigente_desde <= em)
        .order_by(ConfigFator.tipo_veiculo, ConfigFator.vigente_desde.desc())
        .distinct(ConfigFator.tipo_veiculo)
    ).all()
    ordem = list(TipoVeiculo)
    return sorted(linhas, key=lambda f: ordem.index(f.tipo_veiculo))


def parametro_vigente(session: Session, chave: ChaveParametro, em: date) -> ConfigParametro:
    param = session.scalar(
        select(ConfigParametro)
        .where(ConfigParametro.chave == chave, ConfigParametro.vigente_desde <= em)
        .order_by(ConfigParametro.vigente_desde.desc())
        .limit(1)
    )
    if param is None:
        raise ErroNegocio(422, "PARAMETRO_NAO_CONFIGURADO", f"Sem parâmetro {chave} vigente em {em}.")
    return param


def preco_base_vigente(session: Session, em: date) -> Decimal:
    """Pb, art. 3º §5º."""
    return Decimal(parametro_vigente(session, ChaveParametro.PRECO_BASE, em).valor)


def fim_saldo_negativo(session: Session, em: date) -> date:
    """Último dia em que se aceita saldo negativo, art. 8º §1º."""
    return date.fromisoformat(parametro_vigente(session, ChaveParametro.FIM_SALDO_NEGATIVO, em).valor)


# --- Rota -----------------------------------------------------------------------------------

router = APIRouter(prefix="/configuracao", tags=["configuracao"])


class FatorSaida(BaseModel):
    tipo: TipoVeiculo
    fator: Decimal
    vigente_desde: date


class FatoresSaida(BaseModel):
    itens: list[FatorSaida]
    total: int
    preco_base: Decimal


@router.get("/fatores", response_model=FatoresSaida, summary="Fatores de equivalência e preço base vigentes")
def listar_fatores(
    session: Session = Depends(obter_sessao),
    _: Usuario = Depends(usuario_atual),
) -> FatoresSaida:
    em = date.today()
    itens = [
        FatorSaida(tipo=f.tipo_veiculo, fator=f.fator, vigente_desde=f.vigente_desde)
        for f in fatores_vigentes(session, em)
    ]
    return FatoresSaida(itens=itens, total=len(itens), preco_base=preco_base_vigente(session, em))
