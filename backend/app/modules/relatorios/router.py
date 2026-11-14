"""Rotas do módulo `relatorios` (seção "URV e MMV" de docs/03-contrato-api.md). Dono: backend-urv.

O router já está registrado em app/main.py com o prefixo /api/v1.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import exige_papel
from app.models import Papel, Usuario
from app.modules.relatorios import service
from app.modules.relatorios.schemas import RelatorioMdicSaida
from app.modules.urv.relogio import agora, data_operacao

router = APIRouter(prefix="/relatorios", tags=["relatorios"])

_leitor = exige_papel(Papel.AUDITOR, Papel.ADMIN)  # RF-23, art. 9º; art. 24 V


@router.get("/mdic", response_model=RelatorioMdicSaida, summary="Relatório anual ao MDIC (art. 27 I e II)")
def relatorio_mdic(
    ano: int | None = Query(None, ge=2000, le=2100, description="Ano-calendário; por padrão, o corrente"),
    session: Session = Depends(obter_sessao),
    _: Usuario = Depends(_leitor),
    momento: datetime = Depends(agora),
) -> RelatorioMdicSaida:
    return service.relatorio_mdic(session, ano or data_operacao(momento).year)  # RF-24
