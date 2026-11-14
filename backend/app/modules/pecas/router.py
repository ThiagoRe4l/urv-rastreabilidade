"""Rotas de peças (seção "Fluxo do veículo" de docs/03-contrato-api.md).

Dono: backend-fluxo (agente 01). O router já está registrado em app/main.py.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.erros import Erro
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.models import PecaClassificacao, PecaCondicao, PecaDestino, Usuario
from app.modules.pecas import service
from app.modules.pecas.schemas import PecaAtualizar, PecaCriar, PecaSaida, RastreioSaida
from app.modules.veiculos.papeis import escreve_fluxo, le_fluxo

router = APIRouter(tags=["pecas"])

_erros = {404: {"model": Erro}, 409: {"model": Erro}, 422: {"model": Erro}}


@router.post(
    "/veiculos/{veiculo_id}/pecas",
    response_model=PecaSaida,
    status_code=status.HTTP_201_CREATED,
    responses=_erros,
)
def registrar_peca(
    veiculo_id: uuid.UUID,
    dados: PecaCriar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
) -> PecaSaida:
    peca = service.registrar_peca(session, usuario, veiculo_id, dados)  # RF-09
    session.commit()
    return service.para_saida(session, [peca])[0]


@router.get(
    "/pecas/rastreio/{codigo}",
    response_model=RastreioSaida,
    responses={404: {"model": Erro}},
    summary="Consulta pública da etiqueta (sem autenticação)",
)
def rastrear_peca(codigo: str, session: Session = Depends(obter_sessao)) -> RastreioSaida:
    return service.rastrear(session, codigo)  # RF-09: só etiqueta e destino


@router.patch("/pecas/{peca_id}", response_model=PecaSaida, responses=_erros)
def atualizar_peca(
    peca_id: uuid.UUID,
    dados: PecaAtualizar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
) -> PecaSaida:
    peca = service.atualizar_peca(session, usuario, peca_id, dados)
    session.commit()
    return service.para_saida(session, [peca])[0]


@router.get("/pecas", response_model=Pagina[PecaSaida])
def listar_pecas(
    chassi: str | None = Query(None),
    nome: str | None = Query(None),
    condicao: PecaCondicao | None = Query(None),
    destino: PecaDestino | None = Query(None),
    classificacao: PecaClassificacao | None = Query(None),
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_fluxo),
) -> Pagina[PecaSaida]:
    stmt = service.consulta_pecas(  # RF-10
        usuario, chassi=chassi, nome=nome, condicao=condicao, destino=destino, classificacao=classificacao
    )
    itens, total = paginar(session, stmt, pag)
    return Pagina[PecaSaida](itens=service.para_saida(session, itens), total=total)
