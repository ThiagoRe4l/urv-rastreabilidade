"""Correções da revisão independente (docs/revisao-independente.md).

- A1: `config_parametro.chave` aceita `RM_NIVEL_1` e `RM_NIVEL_2`. O RM por nível deixa de ser
  constante no código e passa a ser parâmetro com vigência (art. 3º §3º; lacuna L-01). Os
  valores são gravados pelo seed, com evento na trilha, e não por esta migração.
- A4: `certificado` e `laudo` passam a rejeitar UPDATE, DELETE e TRUNCATE (reusa
  `rejeitar_alteracao()` da 0001). Em `urv_credito`, só `status` e `titular_id` mudam: o gatilho
  compara a linha inteira, menos essas duas colunas, e rejeita DELETE e TRUNCATE (RF-22,
  RNF-01, art. 20 V; art. 24 I).
- A5: `certificado.importado` e `urv_credito.importado` marcam o que veio de outra plataforma
  pela portabilidade (art. 22).
- A7: `veiculo.renavam` e `veiculo.certidao_baixa_numero` únicos (art. 18 II; art. 21 III). Um
  banco com veículos repetidos nessas colunas não migra: a duplicidade precisa ser resolvida à mão,
  porque não há como saber qual dos registros é o legítimo.
- R10: `peca.item_seguranca`; item de segurança só com classificação `NAO_REUTILIZAVEL`
  (Anexo III 7).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHAVES_ANTES = ("PRECO_BASE", "FIM_SALDO_NEGATIVO")
CHAVES_DEPOIS = (*CHAVES_ANTES, "RM_NIVEL_1", "RM_NIVEL_2")

TABELAS_IMUTAVEIS = ("certificado", "laudo")

FUNCAO_CREDITO = """
CREATE FUNCTION rejeitar_alteracao_credito() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND (to_jsonb(NEW) - 'status' - 'titular_id') = (to_jsonb(OLD) - 'status' - 'titular_id') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Tabela urv_credito: só status e titular_id mudam; % rejeitado (RF-22, art. 20 V)', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$;
"""


def _check_chave(chaves: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_config_parametro_chave"), "config_parametro", type_="check")
    lista = ", ".join(f"'{c}'" for c in chaves)
    op.create_check_constraint(op.f("ck_config_parametro_chave"), "config_parametro", f"chave IN ({lista})")


def upgrade() -> None:
    _check_chave(CHAVES_DEPOIS)  # A1, RF-18, art. 3º §3º

    # A5, RF-25, art. 22: o que veio de outra plataforma fica marcado.
    for tabela in ("certificado", "urv_credito"):
        op.add_column(tabela, sa.Column("importado", sa.Boolean(), server_default="false", nullable=False))

    # A7, RF-06 e RF-21, art. 18 II; art. 21 III: Renavam e certidão de baixa são de um veículo só.
    op.create_unique_constraint(op.f("uq_veiculo_renavam"), "veiculo", ["renavam"])
    op.create_unique_constraint(op.f("uq_veiculo_certidao_baixa_numero"), "veiculo", ["certidao_baixa_numero"])

    # R10, Anexo III 7: item de segurança é obrigatoriamente não reutilizável.
    op.add_column("peca", sa.Column("item_seguranca", sa.Boolean(), server_default="false", nullable=False))
    op.create_check_constraint(
        op.f("ck_peca_item_seguranca_nao_reutilizavel"),
        "peca",
        "NOT item_seguranca OR classificacao = 'NAO_REUTILIZAVEL'",
    )

    # A4, RF-22, art. 20 V: o que o certificado e o laudo atestam não muda depois de gravado.
    for tabela in TABELAS_IMUTAVEIS:
        op.execute(
            f"CREATE TRIGGER trg_{tabela}_imutavel BEFORE UPDATE OR DELETE ON {tabela} "
            "FOR EACH ROW EXECUTE FUNCTION rejeitar_alteracao()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{tabela}_sem_truncate BEFORE TRUNCATE ON {tabela} "
            "FOR EACH STATEMENT EXECUTE FUNCTION rejeitar_alteracao()"
        )
    # A4, RF-16 e RF-17: a quantidade, a geradora e o certificado do crédito não mudam; a
    # transferência muda só o status e o titular.
    op.execute(FUNCAO_CREDITO)
    op.execute(
        "CREATE TRIGGER trg_urv_credito_imutavel BEFORE UPDATE OR DELETE ON urv_credito "
        "FOR EACH ROW EXECUTE FUNCTION rejeitar_alteracao_credito()"
    )
    op.execute(
        "CREATE TRIGGER trg_urv_credito_sem_truncate BEFORE TRUNCATE ON urv_credito "
        "FOR EACH STATEMENT EXECUTE FUNCTION rejeitar_alteracao()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_urv_credito_sem_truncate ON urv_credito")
    op.execute("DROP TRIGGER IF EXISTS trg_urv_credito_imutavel ON urv_credito")
    op.execute("DROP FUNCTION IF EXISTS rejeitar_alteracao_credito()")
    for tabela in TABELAS_IMUTAVEIS:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabela}_sem_truncate ON {tabela}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabela}_imutavel ON {tabela}")
    op.drop_constraint(op.f("ck_peca_item_seguranca_nao_reutilizavel"), "peca", type_="check")
    op.drop_column("peca", "item_seguranca")
    op.drop_constraint(op.f("uq_veiculo_certidao_baixa_numero"), "veiculo", type_="unique")
    op.drop_constraint(op.f("uq_veiculo_renavam"), "veiculo", type_="unique")
    for tabela in ("certificado", "urv_credito"):
        op.drop_column(tabela, "importado")
    op.execute("DELETE FROM config_parametro WHERE chave IN ('RM_NIVEL_1', 'RM_NIVEL_2')")
    _check_chave(CHAVES_ANTES)
