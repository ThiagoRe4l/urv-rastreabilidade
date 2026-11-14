"""Defesa em profundidade do livro de URV (PM-URV-05).

- Índice único em `urv_lancamento (credito_id, tipo)`: um crédito tem no máximo um lançamento
  de cada tipo (um CREDITO, uma TRANSFERENCIA_SAIDA, uma TRANSFERENCIA_ENTRADA). Hoje a
  transferência única depende do `SELECT ... FOR UPDATE` no service; com o índice, o banco
  barra a segunda mesmo que o service falhe (RF-17, art. 3º §1º; RF-21, arts. 28 e 29).
  O DEBITO não tem `credito_id` e o PostgreSQL trata nulos como distintos, então os débitos
  não são afetados.
- `consumo` e `consumo_chassi` passam a ser só de inserção, como `urv_lancamento` e
  `evento_auditoria`: um consumo registrado não pode ser alterado nem apagado direto no banco
  (RF-18, RF-21; art. 20 V; art. 24 I). Reusa a função `rejeitar_alteracao()` da 0001.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14 09:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOVAS_TABELAS_SO_INSERCAO = ("consumo", "consumo_chassi")
INDICE = "uq_urv_lancamento_credito_id_tipo"


def upgrade() -> None:
    op.create_index(INDICE, "urv_lancamento", ["credito_id", "tipo"], unique=True)
    for tabela in NOVAS_TABELAS_SO_INSERCAO:
        # Mesmo padrão de nome da 0001.
        op.execute(
            f"CREATE TRIGGER trg_{tabela}_imutavel BEFORE UPDATE OR DELETE ON {tabela} "
            "FOR EACH ROW EXECUTE FUNCTION rejeitar_alteracao()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{tabela}_sem_truncate BEFORE TRUNCATE ON {tabela} "
            "FOR EACH STATEMENT EXECUTE FUNCTION rejeitar_alteracao()"
        )


def downgrade() -> None:
    for tabela in NOVAS_TABELAS_SO_INSERCAO:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabela}_sem_truncate ON {tabela}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabela}_imutavel ON {tabela}")
    op.drop_index(INDICE, table_name="urv_lancamento")
