"""Leitura de fatores e parâmetros com vigência, e a rota GET /configuracao/fatores.

Os fatores e o preço base podem ser revistos (art. 3º §6º), por isso nada aqui é
constante no código: sempre leia o valor vigente na data da operação.
"""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import usuario_atual
from app.core.erros import ErroNegocio
from app.core.relogio import agora, data_operacao
from app.models import ChaveParametro, ConfigFator, ConfigParametro, TipoVeiculo, Usuario
from app.modules.urv.calculo import RMS_DA_PORTARIA


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


RM_POR_CHAVE: dict[int, ChaveParametro] = {1: ChaveParametro.RM_NIVEL_1, 2: ChaveParametro.RM_NIVEL_2}


def rm_vigente(session: Session, nivel: int, em: date) -> int:
    """RM do nível do MMV na data. RF-18, art. 3º §3º: "(5 ou 10, respectivamente)".

    Decreto 12.435/2025, Anexo III, seção C: nível 2 = item 17 = cinco; nível 1 = item 18 = dez.
    """
    chave = RM_POR_CHAVE.get(nivel)
    if chave is None:
        raise ErroNegocio(
            422, "NIVEL_INVALIDO", f"Nível de reciclabilidade inválido: {nivel!r} (use 1 ou 2)."
        )
    valor = parametro_vigente(session, chave, em).valor
    rm = int(valor) if valor.isdigit() else None
    if rm not in RMS_DA_PORTARIA:
        raise ErroNegocio(
            422,
            "PARAMETRO_INVALIDO",
            f"{chave} vigente em {em} vale {valor!r}; o art. 3º §3º admite 5 ou 10.",
        )
    return rm


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
    momento: datetime = Depends(agora),
) -> FatoresSaida:
    em = data_operacao(momento)  # PM-URV-06: vigência na data de Brasília (art. 3º §6º)
    itens = [
        FatorSaida(tipo=f.tipo_veiculo, fator=f.fator, vigente_desde=f.vigente_desde)
        for f in fatores_vigentes(session, em)
    ]
    return FatoresSaida(itens=itens, total=len(itens), preco_base=preco_base_vigente(session, em))
