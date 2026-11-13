import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ComId, coluna_enum
from app.models.enums import CredenciamentoStatus, Papel, TipoEmpresa


class Empresa(ComId, Base):
    """RF-01, arts. 11 e 16. Fabricante não tem credenciamento; usa `registro_compromissos` (art. 8º II)."""

    __tablename__ = "empresa"

    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    razao_social: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[TipoEmpresa] = mapped_column(coluna_enum(TipoEmpresa, "tipo"))
    credenciamento_status: Mapped[CredenciamentoStatus | None] = mapped_column(
        coluna_enum(CredenciamentoStatus, "credenciamento_status")
    )
    credenciamento_validade: Mapped[date | None] = mapped_column(Date)
    registro_compromissos: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    __table_args__ = (
        CheckConstraint("cnpj ~ '^[0-9]{14}$'", name="cnpj_digitos"),
        CheckConstraint(
            "(tipo = 'FABRICANTE') = (credenciamento_status IS NULL)",
            name="credenciamento_so_geradora",
        ),
        CheckConstraint(
            "tipo = 'FABRICANTE' OR registro_compromissos = false",
            name="registro_compromissos_so_fabricante",
        ),
    )


class Usuario(ComId, Base):
    __tablename__ = "usuario"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    nome: Mapped[str] = mapped_column(String(200))
    papel: Mapped[Papel] = mapped_column(coluna_enum(Papel, "papel"))
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("empresa.id"), index=True)

    empresa: Mapped[Empresa | None] = relationship(lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "(papel IN ('ADMIN', 'AUDITOR')) = (empresa_id IS NULL)",
            name="empresa_conforme_papel",
        ),
        CheckConstraint("email = lower(email)", name="email_minusculo"),
    )


class Vinculo(ComId, Base):
    """RF-02, art. 13 §1º VI e §2º: vínculo comercial geradora × fabricante."""

    __tablename__ = "vinculo"

    geradora_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    fabricante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    geradora: Mapped[Empresa] = relationship(foreign_keys=[geradora_id], lazy="joined")
    fabricante: Mapped[Empresa] = relationship(foreign_keys=[fabricante_id], lazy="joined")

    __table_args__ = (
        UniqueConstraint("geradora_id", "fabricante_id"),
        CheckConstraint("geradora_id <> fabricante_id", name="partes_distintas"),
    )
