import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ComId, coluna_enum
from app.models.enums import MmvStatus


class Mmv(ComId, Base):
    """RF-03 e RF-04, art. 5º: Marca/Modelo/Versão cadastrada pelo fabricante."""

    __tablename__ = "mmv"

    fabricante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(60))
    ncm: Mapped[str] = mapped_column(String(10))
    nivel: Mapped[int] = mapped_column(SmallInteger)
    percentual_reciclabilidade: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    ja_comercializado: Mapped[bool] = mapped_column(Boolean)
    efeitos_a_partir_de: Mapped[date] = mapped_column(Date)
    status: Mapped[MmvStatus] = mapped_column(
        coluna_enum(MmvStatus, "status"), default=MmvStatus.ATIVO, server_default=MmvStatus.ATIVO.value
    )

    __table_args__ = (
        UniqueConstraint("fabricante_id", "codigo"),
        CheckConstraint("nivel IN (1, 2)", name="nivel"),
        CheckConstraint(
            "percentual_reciclabilidade >= 0 AND percentual_reciclabilidade <= 100", name="percentual"
        ),
    )
