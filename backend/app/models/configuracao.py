from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ComId, coluna_enum
from app.models.enums import ChaveParametro, TipoVeiculo


class ConfigFator(ComId, Base):
    """Fator de equivalência com vigência (art. 3º §§2º e 6º)."""

    __tablename__ = "config_fator"

    tipo_veiculo: Mapped[TipoVeiculo] = mapped_column(coluna_enum(TipoVeiculo, "tipo_veiculo"))
    fator: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    vigente_desde: Mapped[date] = mapped_column(Date)

    __table_args__ = (
        UniqueConstraint("tipo_veiculo", "vigente_desde"),
        CheckConstraint("fator > 0 AND fator <= 1", name="fator_intervalo"),
    )


class ConfigParametro(ComId, Base):
    """Parâmetros com vigência: PRECO_BASE (art. 3º §5º), FIM_SALDO_NEGATIVO (art. 8º §1º),
    RM_NIVEL_1 e RM_NIVEL_2 (art. 3º §3º; lacuna L-01).

    `valor` é texto; quem lê converte (Decimal ou date). Use app.core.configuracao.
    """

    __tablename__ = "config_parametro"

    chave: Mapped[ChaveParametro] = mapped_column(coluna_enum(ChaveParametro, "chave"))
    valor: Mapped[str] = mapped_column(String(100))
    vigente_desde: Mapped[date] = mapped_column(Date)

    __table_args__ = (UniqueConstraint("chave", "vigente_desde"),)
