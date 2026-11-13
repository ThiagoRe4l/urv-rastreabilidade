import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ComId, coluna_enum
from app.models.documentos import Certificado
from app.models.enums import LancamentoTipo, UrvCreditoStatus


class UrvCredito(ComId, Base):
    """Crédito indivisível gerado por um certificado. RF-16, art. 3º §§1º e 2º; art. 18 §3º."""

    __tablename__ = "urv_credito"

    certificado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("certificado.id"), unique=True)
    geradora_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    titular_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[UrvCreditoStatus] = mapped_column(
        coluna_enum(UrvCreditoStatus, "status"),
        default=UrvCreditoStatus.DISPONIVEL,
        server_default=UrvCreditoStatus.DISPONIVEL.value,
    )

    certificado: Mapped[Certificado] = relationship()

    __table_args__ = (CheckConstraint("quantidade > 0", name="quantidade_positiva"),)


class UrvLancamento(ComId, Base):
    """Livro-razão só de inserção (gatilho no banco). Saldo = soma de `quantidade`."""

    __tablename__ = "urv_lancamento"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    tipo: Mapped[LancamentoTipo] = mapped_column(coluna_enum(LancamentoTipo, "tipo"))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # com sinal
    credito_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("urv_credito.id"), index=True)
    consumo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("consumo.id"), index=True)
    contraparte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("empresa.id"))

    __table_args__ = (
        CheckConstraint(
            "(tipo IN ('CREDITO', 'TRANSFERENCIA_ENTRADA') AND quantidade > 0)"
            " OR (tipo IN ('TRANSFERENCIA_SAIDA', 'DEBITO') AND quantidade < 0)",
            name="sinal_conforme_tipo",
        ),
        CheckConstraint("tipo <> 'DEBITO' OR consumo_id IS NOT NULL", name="debito_com_consumo"),
        CheckConstraint("tipo = 'DEBITO' OR credito_id IS NOT NULL", name="credito_referenciado"),
    )


class Consumo(ComId, Base):
    """Débito de URV por MMV. RF-18 a RF-20, art. 3º §3º; art. 7º; art. 8º III e §1º."""

    __tablename__ = "consumo"

    fabricante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    mmv_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mmv.id"), index=True)
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    qv: Mapped[int] = mapped_column(Integer)
    rm: Mapped[int] = mapped_column(Integer)
    pm: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    pb: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    urv_debito: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    saldo_apos: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    regularizar_ate: Mapped[date | None] = mapped_column(Date)
    prazo_reporte: Mapped[date] = mapped_column(Date)
    registrado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chassis: Mapped[list["ConsumoChassi"]] = relationship(back_populates="consumo")

    __table_args__ = (
        CheckConstraint("periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name="periodo_formato"),
        CheckConstraint("qv > 0", name="qv_positivo"),
        CheckConstraint("rm IN (5, 10)", name="rm_valido"),
        CheckConstraint("pm > 0 AND pb > 0", name="precos_positivos"),
        CheckConstraint("urv_debito >= 0", name="debito_nao_negativo"),
    )


class ConsumoChassi(ComId, Base):
    """Chassi de veículo novo: consumido uma única vez (RF-21, arts. 28 e 29)."""

    __tablename__ = "consumo_chassi"

    consumo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("consumo.id"), index=True)
    chassi: Mapped[str] = mapped_column(String(30), unique=True)

    consumo: Mapped[Consumo] = relationship(back_populates="chassis")
