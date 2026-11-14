"""Correções da revisão independente (docs/revisao-independente.md).

- A1: `config_parametro.chave` aceita `RM_NIVEL_1` e `RM_NIVEL_2`. O RM por nível deixa de ser
  constante no código e passa a ser parâmetro com vigência (art. 3º §3º; lacuna L-01). Os
  valores são gravados pelo seed, com evento na trilha, e não por esta migração.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14 15:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHAVES_ANTES = ("PRECO_BASE", "FIM_SALDO_NEGATIVO")
CHAVES_DEPOIS = (*CHAVES_ANTES, "RM_NIVEL_1", "RM_NIVEL_2")


def _check_chave(chaves: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_config_parametro_chave"), "config_parametro", type_="check")
    lista = ", ".join(f"'{c}'" for c in chaves)
    op.create_check_constraint(op.f("ck_config_parametro_chave"), "config_parametro", f"chave IN ({lista})")


def upgrade() -> None:
    _check_chave(CHAVES_DEPOIS)  # A1, RF-18, art. 3º §3º


def downgrade() -> None:
    op.execute("DELETE FROM config_parametro WHERE chave IN ('RM_NIVEL_1', 'RM_NIVEL_2')")
    _check_chave(CHAVES_ANTES)
