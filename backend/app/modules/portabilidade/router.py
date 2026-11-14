"""Rotas do módulo `portabilidade` (seção "URV e MMV" de docs/03-contrato-api.md). Dono: backend-urv.

O router já está registrado em app/main.py com o prefixo /api/v1.
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import exige_papel, usuario_atual
from app.core.erros import Erro
from app.models import Papel, Usuario
from app.modules.portabilidade import service
from app.modules.portabilidade.schemas import ArquivoPortabilidade, ResultadoImportacao
from app.modules.urv.acesso import empresa_consultada
from app.modules.urv.relogio import agora, data_operacao

router = APIRouter(prefix="/portabilidade", tags=["portabilidade"])

_admin = exige_papel(Papel.ADMIN)
_erros = {404: {"model": Erro}, 422: {"model": Erro}}


async def corpo_bruto(request: Request) -> bytes:
    """O JSON como chegou, para conferir `hash_conteudo` sobre o documento original."""
    return await request.body()


@router.get(
    "/exportar",
    response_model=ArquivoPortabilidade,
    responses=_erros,
    summary="Baixa todo o histórico da empresa em JSON versionado",
)
def exportar(
    empresa_id: uuid.UUID | None = Query(None, description="Só para AUDITOR e ADMIN: empresa exportada"),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
    momento: datetime = Depends(agora),
) -> JSONResponse:
    # RF-25, RNF-05, art. 22 II e IV: a própria empresa exporta, sem pedir a ninguém.
    alvo = empresa_consultada(usuario, empresa_id, obrigatoria=True)
    assert alvo is not None
    documento = service.exportar(session, alvo, momento)
    nome = f"urv-portabilidade-{documento['empresa']['cnpj']}-{data_operacao(momento).isoformat()}.json"
    return JSONResponse(documento, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.post(
    "/importar",
    response_model=ResultadoImportacao,
    responses=_erros,
    summary="Importa o histórico de uma empresa vindo de outra plataforma",
)
def importar(
    arquivo: ArquivoPortabilidade,
    corpo: bytes = Depends(corpo_bruto),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_admin),
) -> ResultadoImportacao:
    # RF-25, RNF-04, arts. 22, 28 e 29: rejeita o que já existe aqui e diz o motivo por item.
    resultado = service.importar(session, usuario, arquivo, documento=json.loads(corpo))
    session.commit()
    return resultado
