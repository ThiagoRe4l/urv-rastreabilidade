"""Imutabilidade de certificado, laudo e crédito no banco e GET /auditoria/reconciliar.

RF-22, RNF-01, art. 20 V; art. 24 I. Achado A4 da revisão: a trilha íntegra não basta quando as
tabelas que ela descreve podem ser editadas.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.seed import EMAIL_AUDITOR, EMAIL_FABRICANTE
from tests.unit.fluxo.apoio import API, certificado, criar_veiculo, executar_passos

RECONCILIAR = f"{API}/auditoria/reconciliar"


@pytest.fixture
def cert(client, h) -> dict:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    r = certificado(client, h, v["id"])
    assert r.status_code == 201, r.text
    return r.json()


def _reconciliar(client, auth) -> dict:
    r = client.get(RECONCILIAR, headers=auth(EMAIL_AUDITOR))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE certificado SET fator = 1.00",
        "UPDATE certificado SET tipo_veiculo = 'LICENCIADO_RODAGEM'",
        "DELETE FROM certificado",
        "TRUNCATE certificado CASCADE",
        "UPDATE laudo SET responsavel_nome = 'Outro'",
        "DELETE FROM laudo",
        "TRUNCATE laudo",
        "UPDATE urv_credito SET quantidade = 1.00",
        "UPDATE urv_credito SET geradora_id = (SELECT id FROM empresa WHERE tipo = 'FABRICANTE' LIMIT 1)",
        "UPDATE urv_credito SET certificado_id = certificado_id, criado_em = now() - interval '1 day'",
        "DELETE FROM urv_credito",
        "TRUNCATE urv_credito CASCADE",
    ],
)
def test_certificado_laudo_e_credito_nao_se_alteram_no_banco(db_session, cert, sql: str) -> None:
    with (
        pytest.raises(DBAPIError, match="só de inserção|só status e titular_id mudam"),
        db_session.begin_nested(),
    ):
        db_session.execute(text(sql))


def test_no_credito_so_status_e_titular_mudam(db_session, cert, dados_demo) -> None:
    with db_session.begin_nested():
        db_session.execute(
            text("UPDATE urv_credito SET status = 'TRANSFERIDO', titular_id = :t WHERE id = :i"),
            {"t": dados_demo.montadora_id, "i": cert["credito"]["id"]},
        )


def test_reconciliacao_do_fluxo_normal_e_conciliada(client, auth, cert) -> None:
    r = _reconciliar(client, auth)
    assert r["conciliado"] is True, r["divergencias"]
    assert r["total_divergencias"] == 0
    assert r["verificados"]["certificados"] >= 1 and r["verificados"]["creditos"] >= 1


def test_credito_alterado_com_o_gatilho_desligado_e_acusado(client, auth, db_session, cert) -> None:
    db_session.execute(text("ALTER TABLE urv_credito DISABLE TRIGGER trg_urv_credito_imutavel"))
    db_session.execute(
        text("UPDATE urv_credito SET quantidade = 1.00 WHERE id = :i"), {"i": cert["credito"]["id"]}
    )
    db_session.execute(text("ALTER TABLE urv_credito ENABLE TRIGGER trg_urv_credito_imutavel"))
    # A trilha continua íntegra: ninguém mexeu nela.
    assert client.get(f"{API}/auditoria/verificar", headers=auth(EMAIL_AUDITOR)).json()["integra"] is True
    r = _reconciliar(client, auth)
    assert r["conciliado"] is False
    acusadas = {(d["verificacao"], d["entidade"]) for d in r["divergencias"]}
    assert ("CREDITO_FATOR", "urv_credito") in acusadas  # 1,00 contra o fator 0,94 do certificado
    assert ("LANCAMENTO", "urv_lancamento") in acusadas  # o CREDITO do livro tem 0,94
    assert ("SALDO", "empresa") in acusadas
    assert ("TRILHA", "urv_credito") in acusadas  # CREDITO_GERADO gravou 0,94


def test_transferencia_feita_direto_no_banco_e_acusada(client, auth, db_session, cert, dados_demo) -> None:
    # O gatilho deixa mudar status e titular, mas sem lançamentos nem evento a reconciliação acusa.
    db_session.execute(
        text("UPDATE urv_credito SET status = 'TRANSFERIDO', titular_id = :t WHERE id = :i"),
        {"t": dados_demo.montadora_id, "i": cert["credito"]["id"]},
    )
    r = _reconciliar(client, auth)
    detalhes = {(d["verificacao"], d["entidade"], d["entidade_id"]) for d in r["divergencias"]}
    assert ("LANCAMENTO", "urv_credito", cert["credito"]["id"]) in detalhes
    assert ("TRILHA", "urv_credito", cert["credito"]["id"]) in detalhes


def test_certificado_alterado_com_o_gatilho_desligado_e_acusado(client, auth, db_session, cert) -> None:
    db_session.execute(text("ALTER TABLE certificado DISABLE TRIGGER trg_certificado_imutavel"))
    db_session.execute(text("UPDATE certificado SET fator = 1.00 WHERE id = :i"), {"i": cert["id"]})
    db_session.execute(text("ALTER TABLE certificado ENABLE TRIGGER trg_certificado_imutavel"))
    acusadas = {(d["verificacao"], d["entidade"]) for d in _reconciliar(client, auth)["divergencias"]}
    assert {
        ("FATOR_VIGENTE", "certificado"),
        ("CREDITO_FATOR", "urv_credito"),
        ("TRILHA", "certificado"),
    } <= acusadas


def test_reconciliar_e_so_de_auditor_e_admin(client, auth, h) -> None:
    assert client.get(RECONCILIAR, headers=h).status_code == 403
    assert client.get(RECONCILIAR, headers=auth(EMAIL_FABRICANTE)).status_code == 403
