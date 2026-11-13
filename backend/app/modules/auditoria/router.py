import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import exige_papel
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.models import EventoAuditoria, Papel, Usuario
from app.modules.auditoria import service
from app.modules.auditoria.schemas import EventoSaida, VerificacaoSaida

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

_leitor = exige_papel(Papel.AUDITOR, Papel.ADMIN)  # RF-23, art. 9º; art. 24 V


@router.get(
    "/eventos", response_model=Pagina[EventoSaida], summary="Eventos da trilha, em ordem de sequência"
)
def listar_eventos(
    entidade: str | None = Query(None),
    entidade_id: uuid.UUID | None = Query(None),
    tipo: str | None = Query(None),
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    _: Usuario = Depends(_leitor),
) -> Pagina[EventoSaida]:
    stmt = select(EventoAuditoria).order_by(EventoAuditoria.sequencia)
    if entidade:
        stmt = stmt.where(EventoAuditoria.entidade == entidade)
    if entidade_id:
        stmt = stmt.where(EventoAuditoria.entidade_id == entidade_id)
    if tipo:
        stmt = stmt.where(EventoAuditoria.tipo == tipo)
    itens, total = paginar(session, stmt, pag)
    return Pagina[EventoSaida](itens=[EventoSaida.model_validate(e) for e in itens], total=total)


@router.get("/verificar", response_model=VerificacaoSaida, summary="Recalcula a cadeia de hashes")
def verificar(session: Session = Depends(obter_sessao), _: Usuario = Depends(_leitor)) -> VerificacaoSaida:
    r = service.verificar_cadeia(session)  # RF-22, art. 20 V
    return VerificacaoSaida(integra=r.integra, total=r.total, primeira_quebra=r.primeira_quebra)
