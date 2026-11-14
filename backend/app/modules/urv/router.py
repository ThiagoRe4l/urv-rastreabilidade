"""Rotas do módulo `urv` (seção "URV e MMV" de docs/03-contrato-api.md). Dono: backend-urv.

O router já está registrado em app/main.py com o prefixo /api/v1.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import exige_papel, usuario_atual
from app.core.erros import Erro
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.models import LancamentoTipo, Papel, UrvCreditoStatus, Usuario
from app.modules.urv import service
from app.modules.urv.acesso import empresa_consultada
from app.modules.urv.relogio import agora
from app.modules.urv.schemas import (
    ConsumoCriar,
    ConsumoSaida,
    ConsumoSimular,
    CreditoSaida,
    LancamentoSaida,
    SaldoSaida,
    SimulacaoSaida,
    TransferenciaCriar,
)

router = APIRouter(prefix="/urv", tags=["urv"])

_geradora = exige_papel(Papel.DESMONTADORA, Papel.RECICLADORA)
_fabricante = exige_papel(Papel.FABRICANTE)
_leitor_consumos = exige_papel(Papel.FABRICANTE, Papel.AUDITOR, Papel.ADMIN)

_EMPRESA_ID = Query(None, description="Só para AUDITOR e ADMIN: empresa consultada")
_erros = {404: {"model": Erro}, 409: {"model": Erro}, 422: {"model": Erro}}


@router.get("/saldo", response_model=SaldoSaida, responses=_erros, summary="Saldo de URV da empresa")
def saldo(
    empresa_id: uuid.UUID | None = _EMPRESA_ID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
) -> SaldoSaida:
    alvo = empresa_consultada(usuario, empresa_id, obrigatoria=True)
    assert alvo is not None
    return service.consultar_saldo(session, alvo)  # RF-19


@router.get("/extrato", response_model=Pagina[LancamentoSaida], summary="Lançamentos do livro de URV")
def extrato(
    empresa_id: uuid.UUID | None = _EMPRESA_ID,
    tipo: LancamentoTipo | None = Query(None),
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
) -> Pagina[LancamentoSaida]:
    alvo = empresa_consultada(usuario, empresa_id)
    itens, total = paginar(session, service.consulta_lancamentos(alvo, tipo), pag)
    return Pagina[LancamentoSaida](itens=service.montar_lancamentos(session, itens), total=total)


@router.get(
    "/creditos", response_model=Pagina[CreditoSaida], summary="Créditos gerados ou recebidos pela empresa"
)
def listar_creditos(
    status_credito: UrvCreditoStatus | None = Query(None, alias="status"),
    empresa_id: uuid.UUID | None = _EMPRESA_ID,
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
) -> Pagina[CreditoSaida]:
    alvo = empresa_consultada(usuario, empresa_id)
    itens, total = paginar(session, service.consulta_creditos(alvo, status_credito), pag)
    return Pagina[CreditoSaida](itens=service.montar_creditos(session, itens), total=total)


@router.post(
    "/creditos/{credito_id}/transferir",
    response_model=CreditoSaida,
    responses=_erros,
    summary="Transfere o crédito, inteiro e uma única vez, a um fabricante com vínculo",
)
def transferir(
    credito_id: uuid.UUID,
    dados: TransferenciaCriar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_geradora),
    momento: datetime = Depends(agora),
) -> CreditoSaida:
    credito = service.transferir_credito(  # RF-17, art. 8º II e §3º
        session, usuario, credito_id, dados.fabricante_id, agora=momento
    )
    session.commit()
    return service.montar_creditos(session, [credito])[0]


@router.post(
    "/consumos/simular",
    response_model=SimulacaoSaida,
    responses=_erros,
    summary="Calcula o débito de URV sem gravar",
)
def simular(
    dados: ConsumoSimular,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_fabricante),
    momento: datetime = Depends(agora),
) -> SimulacaoSaida:
    return service.simular_consumo(session, usuario, dados, agora=momento)  # RF-18


@router.post(
    "/consumos",
    response_model=ConsumoSaida,
    status_code=status.HTTP_201_CREATED,
    responses=_erros,
    summary="Registra o consumo de URV pelos chassis de veículos novos",
)
def registrar_consumo(
    dados: ConsumoCriar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_fabricante),
    momento: datetime = Depends(agora),
) -> ConsumoSaida:
    consumo = service.registrar_consumo(session, usuario, dados, agora=momento)  # RF-18 a RF-21
    session.commit()
    return service.montar_consumos(session, [consumo])[0]


@router.get("/consumos", response_model=Pagina[ConsumoSaida], summary="Consumos, com `fora_do_prazo`")
def listar_consumos(
    empresa_id: uuid.UUID | None = _EMPRESA_ID,
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_leitor_consumos),
) -> Pagina[ConsumoSaida]:
    alvo = empresa_consultada(usuario, empresa_id)
    itens, total = paginar(session, service.consulta_consumos(alvo), pag)
    return Pagina[ConsumoSaida](itens=service.montar_consumos(session, itens), total=total)
