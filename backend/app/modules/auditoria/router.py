import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import exige_papel
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.models import EventoAuditoria, Papel, Usuario
from app.modules.auditoria import reconciliacao, service
from app.modules.auditoria.schemas import DivergenciaSaida, EventoSaida, ReconciliacaoSaida, VerificacaoSaida

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

_leitor = exige_papel(Papel.AUDITOR, Papel.ADMIN)  # RF-23, art. 9º; art. 24 V


@router.get(
    "/eventos", response_model=Pagina[EventoSaida], summary="Eventos da trilha, em ordem de sequência"
)
def listar_eventos(
    entidade: str | None = Query(None),
    entidade_id: uuid.UUID | None = Query(None),
    tipo: str | None = Query(None),
    veiculo_id: uuid.UUID | None = Query(
        None,
        description="Eventos do veículo e dos registros ligados a ele: etapas, anexos, peças, pesagens, "
        "DMR, laudo, certificado e crédito gerado",
    ),
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
    if veiculo_id:
        # RF-23, art. 24 V: o dossiê do veículo na trilha. Os eventos dos registros ligados a ele
        # têm entidade própria e levam o `veiculo_id` no payload (lacuna L-13, resolvida).
        stmt = stmt.where(
            or_(
                and_(EventoAuditoria.entidade == "veiculo", EventoAuditoria.entidade_id == veiculo_id),
                EventoAuditoria.payload["veiculo_id"].astext == str(veiculo_id),
            )
        )
    itens, total = paginar(session, stmt, pag)
    return Pagina[EventoSaida](itens=[EventoSaida.model_validate(e) for e in itens], total=total)


@router.get("/verificar", response_model=VerificacaoSaida, summary="Recalcula a cadeia de hashes")
def verificar(session: Session = Depends(obter_sessao), _: Usuario = Depends(_leitor)) -> VerificacaoSaida:
    r = service.verificar_cadeia(session)  # RF-22, art. 20 V
    return VerificacaoSaida(integra=r.integra, total=r.total, primeira_quebra=r.primeira_quebra)


@router.get(
    "/reconciliar",
    response_model=ReconciliacaoSaida,
    summary="Confere créditos, saldos e registros contra certificados, lançamentos e a trilha",
)
def reconciliar(
    session: Session = Depends(obter_sessao), _: Usuario = Depends(_leitor)
) -> ReconciliacaoSaida:
    # RF-22, RNF-01, art. 20 V; art. 24 I: a trilha íntegra não basta se as tabelas que ela
    # descreve foram alteradas (achado A4 da revisão).
    r = reconciliacao.reconciliar(session)
    divergencias = [DivergenciaSaida(**vars(d)) for d in r.divergencias]
    return ReconciliacaoSaida(
        conciliado=r.conciliado,
        verificados=r.verificados,
        divergencias=divergencias,
        total_divergencias=len(divergencias),
    )
