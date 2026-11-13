"""Trilha de auditoria encadeada por hash. RF-22, RNF-01, art. 20 V e art. 24 I.

hash = sha256(hash_anterior + json_canonico({ocorrido_em, usuario_id, empresa_id, tipo,
                                              entidade, entidade_id, payload}))

JSON canônico: chaves ordenadas, sem espaços, UTF-8. O primeiro evento usa 64 zeros
como hash anterior. Um bloqueio consultivo da transação serializa a cadeia.
"""

import enum
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import EventoAuditoria, Usuario

HASH_INICIAL = "0" * 64

# Chave do pg_advisory_xact_lock que serializa a cadeia (qualquer bigint fixo serve).
CHAVE_BLOQUEIO_CADEIA = 3_252_026

_PADRAO: Any = object()


def normalizar(valor: Any) -> Any:
    """Converte para tipos JSON que voltam idênticos do JSONB.

    Decimal, UUID, datas e enums viram string; float vira string (nada de float no hash).
    """
    if valor is None or isinstance(valor, bool | int | str):
        return valor
    if isinstance(valor, enum.Enum):
        return normalizar(valor.value)
    if isinstance(valor, Decimal | float | uuid.UUID):
        return str(valor)
    if isinstance(valor, datetime):
        return _iso(valor)
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {str(k): normalizar(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple | set | frozenset):
        itens = [normalizar(v) for v in valor]
        return sorted(itens, key=json_canonico) if isinstance(valor, set | frozenset) else itens
    raise TypeError(f"Tipo não serializável no payload de auditoria: {type(valor).__name__}")


def json_canonico(valor: Any) -> str:
    return json.dumps(valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _iso(momento: datetime) -> str:
    if momento.tzinfo is None:
        raise ValueError("Datas da trilha precisam de fuso horário.")
    return momento.astimezone(UTC).isoformat()


def calcular_hash(
    hash_anterior: str,
    ocorrido_em: datetime,
    usuario_id: uuid.UUID | None,
    empresa_id: uuid.UUID | None,
    tipo: str,
    entidade: str,
    entidade_id: uuid.UUID | None,
    payload: dict[str, Any],
) -> str:
    conteudo = json_canonico(
        {
            "ocorrido_em": _iso(ocorrido_em),
            "usuario_id": str(usuario_id) if usuario_id else None,
            "empresa_id": str(empresa_id) if empresa_id else None,
            "tipo": tipo,
            "entidade": entidade,
            "entidade_id": str(entidade_id) if entidade_id else None,
            "payload": payload,
        }
    )
    return hashlib.sha256((hash_anterior + conteudo).encode("utf-8")).hexdigest()


def registrar_evento(
    session: Session,
    usuario: Usuario | None,
    tipo: str,
    entidade: str,
    entidade_id: uuid.UUID | None,
    payload: dict[str, Any] | None = None,
    *,
    empresa_id: uuid.UUID | None = _PADRAO,
) -> EventoAuditoria:
    """Registra um evento na mesma transação da operação de negócio. Não faz commit.

    - `tipo`: verbo no particípio, maiúsculo, ex.: "VEICULO_RECEBIDO", "CREDITO_TRANSFERIDO".
    - `entidade`: nome da tabela, ex.: "veiculo".
    - `empresa_id`: por padrão, a empresa do usuário. Passe a empresa afetada quando
      quem age é ADMIN (sem empresa), para o evento aparecer no histórico dela.
    """
    session.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": CHAVE_BLOQUEIO_CADEIA})
    session.flush()
    anterior = session.scalar(
        select(EventoAuditoria.hash).order_by(EventoAuditoria.sequencia.desc()).limit(1)
    )
    hash_anterior = anterior or HASH_INICIAL

    if empresa_id is _PADRAO:
        empresa_id = usuario.empresa_id if usuario is not None else None
    usuario_id = usuario.id if usuario is not None else None
    ocorrido_em = datetime.now(UTC)
    payload_normal = normalizar(payload or {})

    evento = EventoAuditoria(
        ocorrido_em=ocorrido_em,
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        tipo=tipo,
        entidade=entidade,
        entidade_id=entidade_id,
        payload=payload_normal,
        hash_anterior=hash_anterior,
        hash=calcular_hash(
            hash_anterior, ocorrido_em, usuario_id, empresa_id, tipo, entidade, entidade_id, payload_normal
        ),
    )
    session.add(evento)
    session.flush()
    return evento


@dataclass(frozen=True)
class ResultadoVerificacao:
    integra: bool
    total: int
    primeira_quebra: int | None  # `sequencia` do primeiro evento que não confere


def verificar_cadeia(session: Session) -> ResultadoVerificacao:
    """Percorre a cadeia em ordem e recalcula cada hash. GET /auditoria/verificar."""
    total = session.scalar(select(func.count()).select_from(EventoAuditoria)) or 0
    stmt = (
        select(EventoAuditoria)
        .order_by(EventoAuditoria.sequencia)
        .execution_options(yield_per=500, populate_existing=True)
    )
    esperado_anterior = HASH_INICIAL
    for ev in session.scalars(stmt):
        recalculado = calcular_hash(
            ev.hash_anterior,
            ev.ocorrido_em,
            ev.usuario_id,
            ev.empresa_id,
            ev.tipo,
            ev.entidade,
            ev.entidade_id,
            ev.payload,
        )
        if ev.hash_anterior != esperado_anterior or recalculado != ev.hash:
            return ResultadoVerificacao(integra=False, total=total, primeira_quebra=ev.sequencia)
        esperado_anterior = ev.hash
    return ResultadoVerificacao(integra=True, total=total, primeira_quebra=None)
