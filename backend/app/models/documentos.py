import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ComId, coluna_enum
from app.models.enums import TipoVeiculo
from app.models.veiculo import Veiculo


class Laudo(ComId, Base):
    """Laudo de Reciclagem assinado pelo responsável técnico. RF-14, art. 18 VII; Anexo III 15.b."""

    __tablename__ = "laudo"

    veiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("veiculo.id"), unique=True)
    responsavel_nome: Mapped[str] = mapped_column(String(200))
    responsavel_registro: Mapped[str] = mapped_column(String(60))
    assinado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hash_conteudo: Mapped[str] = mapped_column(String(64))
    # Assinatura devolvida por AssinadorDigital (simulada no MVP).
    assinatura: Mapped[str | None] = mapped_column(Text)

    veiculo: Mapped[Veiculo] = relationship()


class Certificado(ComId, Base):
    """Certificado de Reciclagem Veicular. RF-15, art. 18 VIII; art. 8º I. Um por chassi."""

    __tablename__ = "certificado"

    veiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("veiculo.id"), unique=True)
    numero: Mapped[str] = mapped_column(String(40), unique=True)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    tipo_veiculo: Mapped[TipoVeiculo] = mapped_column(coluna_enum(TipoVeiculo, "tipo_veiculo"))
    fator: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Percentual em pontos (0 a 100), duas casas.
    percentual_aproveitado: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    meta_ano: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # nula em 2026 (art. 18 §7º)
    atende_meta: Mapped[bool | None] = mapped_column(Boolean)
    emitido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hash_conteudo: Mapped[str] = mapped_column(String(64))

    veiculo: Mapped[Veiculo] = relationship()
