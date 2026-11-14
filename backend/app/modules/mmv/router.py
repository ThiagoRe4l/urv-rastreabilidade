"""Rotas do módulo `mmv` (seção "URV e MMV" de docs/03-contrato-api.md). Dono: backend-urv.

O router já está registrado em app/main.py com o prefixo /api/v1.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import exige_papel
from app.core.erros import Erro
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.models import Papel, Usuario
from app.modules.mmv import service
from app.modules.mmv.schemas import MmvCriar, MmvSaida
from app.modules.urv.acesso import empresa_consultada
from app.modules.urv.relogio import agora, data_operacao

router = APIRouter(tags=["mmv"])

_fabricante = exige_papel(Papel.FABRICANTE)
_leitor = exige_papel(Papel.FABRICANTE, Papel.AUDITOR, Papel.ADMIN)
_erros = {409: {"model": Erro}, 422: {"model": Erro}}


@router.post(
    "/mmvs",
    response_model=MmvSaida,
    status_code=status.HTTP_201_CREATED,
    responses=_erros,
    summary="Cadastra um MMV e calcula o início de efeitos",
)
def cadastrar_mmv(
    dados: MmvCriar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_fabricante),
    momento: datetime = Depends(agora),
) -> MmvSaida:
    mmv = service.cadastrar_mmv(session, usuario, dados, data_operacao(momento))  # RF-03, RF-04
    session.commit()
    return MmvSaida.model_validate(mmv)


@router.get(
    "/mmvs", response_model=Pagina[MmvSaida], summary="MMVs do fabricante (todos, para AUDITOR e ADMIN)"
)
def listar_mmvs(
    empresa_id: uuid.UUID | None = Query(None, description="Só para AUDITOR e ADMIN: fabricante consultado"),
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_leitor),
) -> Pagina[MmvSaida]:
    alvo = empresa_consultada(usuario, empresa_id)
    itens, total = paginar(session, service.consulta_mmvs(alvo), pag)
    return Pagina[MmvSaida](itens=[MmvSaida.model_validate(m) for m in itens], total=total)
