import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ComId


class EventoAuditoria(ComId, Base):
    """Evento da trilha encadeada por hash. Só inserção (gatilho no banco). RF-22, art. 20 V."""

    __tablename__ = "evento_auditoria"

    sequencia: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("empresa.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(60), index=True)
    entidade: Mapped[str] = mapped_column(String(60))
    entidade_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    hash_anterior: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)

    __table_args__ = (
        CheckConstraint("hash ~ '^[0-9a-f]{64}$'", name="hash_hex"),
        CheckConstraint("hash_anterior ~ '^[0-9a-f]{64}$'", name="hash_anterior_hex"),
    )
