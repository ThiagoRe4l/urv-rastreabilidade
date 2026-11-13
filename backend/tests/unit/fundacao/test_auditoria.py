"""Trilha de auditoria. RF-22, RNF-01, art. 20 V e art. 24 I."""

import hashlib
import json
import threading
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import (
    Certificado,
    DocumentoEntradaTipo,
    EventoAuditoria,
    LancamentoTipo,
    OrigemAquisicao,
    TipoVeiculo,
    UrvCredito,
    UrvLancamento,
    Veiculo,
)
from app.modules.auditoria.service import HASH_INICIAL, registrar_evento, verificar_cadeia
from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA
from tests.banco import apagar_banco, recriar_banco, url_banco_teste


def _adulterar(session: Session, sequencia: int) -> None:
    """O que scripts/adulterar.py faz, dentro da transação do teste."""
    session.execute(text("ALTER TABLE evento_auditoria DISABLE TRIGGER trg_evento_auditoria_imutavel"))
    session.execute(
        text(
            "UPDATE evento_auditoria SET payload = payload || '{\"_adulterado\": true}' WHERE sequencia = :s"
        ),
        {"s": sequencia},
    )
    session.execute(text("ALTER TABLE evento_auditoria ENABLE TRIGGER trg_evento_auditoria_imutavel"))


def test_evento_registrado_com_hash_da_formula(db_session: Session) -> None:
    ev = registrar_evento(
        db_session, None, "TESTE_CRIADO", "teste", uuid.uuid4(), {"valor": Decimal("0.94"), "n": 1}
    )

    assert ev.sequencia is not None
    assert ev.payload == {"valor": "0.94", "n": 1}  # Decimal vira string, sem float
    anterior = db_session.scalar(
        select(EventoAuditoria.hash)
        .where(EventoAuditoria.sequencia < ev.sequencia)
        .order_by(EventoAuditoria.sequencia.desc())
        .limit(1)
    )
    assert ev.hash_anterior == (anterior or HASH_INICIAL)

    # Fórmula de docs/02-arquitetura.md, recalculada à parte.
    conteudo = json.dumps(
        {
            "ocorrido_em": ev.ocorrido_em.isoformat(),
            "usuario_id": None,
            "empresa_id": None,
            "tipo": "TESTE_CRIADO",
            "entidade": "teste",
            "entidade_id": str(ev.entidade_id),
            "payload": {"n": 1, "valor": "0.94"},
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert ev.hash == hashlib.sha256((ev.hash_anterior + conteudo).encode()).hexdigest()


def test_eventos_encadeados(db_session: Session) -> None:
    a = registrar_evento(db_session, None, "A", "teste", None, {})
    b = registrar_evento(db_session, None, "B", "teste", None, {"x": "y"})
    assert b.hash_anterior == a.hash
    assert b.sequencia > a.sequencia


def test_cadeia_integra(db_session: Session, dados_demo) -> None:
    registrar_evento(db_session, None, "TESTE", "teste", None, {"acentuação": "ção"})
    r = verificar_cadeia(db_session)
    assert r.integra is True
    assert r.total >= 1
    assert r.primeira_quebra is None


def test_cadeia_quebrada_apos_adulteracao(db_session: Session, dados_demo) -> None:
    alvo = registrar_evento(db_session, None, "ALVO", "teste", None, {"quantidade": "1.00"})
    registrar_evento(db_session, None, "DEPOIS", "teste", None, {})
    assert verificar_cadeia(db_session).integra

    _adulterar(db_session, alvo.sequencia)

    r = verificar_cadeia(db_session)
    assert r.integra is False
    assert r.primeira_quebra == alvo.sequencia


def test_alterar_empresa_do_evento_quebra_a_cadeia(db_session: Session, dados_demo) -> None:
    """Decisão 1 da fundação: empresa_id entra no hash."""
    alvo = registrar_evento(db_session, None, "ALVO", "teste", None, {}, empresa_id=dados_demo.desmonte_id)
    db_session.execute(text("ALTER TABLE evento_auditoria DISABLE TRIGGER trg_evento_auditoria_imutavel"))
    db_session.execute(
        text("UPDATE evento_auditoria SET empresa_id = :e WHERE sequencia = :s"),
        {"e": dados_demo.montadora_id, "s": alvo.sequencia},
    )
    db_session.execute(text("ALTER TABLE evento_auditoria ENABLE TRIGGER trg_evento_auditoria_imutavel"))
    assert verificar_cadeia(db_session).primeira_quebra == alvo.sequencia


def test_remover_evento_do_meio_quebra_a_cadeia(db_session: Session) -> None:
    registrar_evento(db_session, None, "A", "teste", None, {})
    meio = registrar_evento(db_session, None, "B", "teste", None, {})
    c = registrar_evento(db_session, None, "C", "teste", None, {})
    db_session.execute(text("ALTER TABLE evento_auditoria DISABLE TRIGGER trg_evento_auditoria_imutavel"))
    db_session.execute(text("DELETE FROM evento_auditoria WHERE sequencia = :s"), {"s": meio.sequencia})
    db_session.execute(text("ALTER TABLE evento_auditoria ENABLE TRIGGER trg_evento_auditoria_imutavel"))
    db_session.expunge(meio)
    assert verificar_cadeia(db_session).primeira_quebra == c.sequencia


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE evento_auditoria SET tipo = 'X'",
        "DELETE FROM evento_auditoria",
        "TRUNCATE evento_auditoria",
    ],
)
def test_banco_rejeita_alteracao_em_evento_auditoria(db_session: Session, sql: str) -> None:
    registrar_evento(db_session, None, "A", "teste", None, {})
    with pytest.raises(DBAPIError, match="só de inserção"), db_session.begin_nested():
        db_session.execute(text(sql))


@pytest.fixture
def lancamento(db_session: Session, dados_demo) -> UrvLancamento:
    """Um lançamento real: UPDATE/DELETE sem linhas não disparariam o gatilho de linha."""
    v = Veiculo(
        empresa_id=dados_demo.desmonte_id,
        chassi="9BWZZZ377VT004251",
        data_entrada=date(2026, 11, 10),
        tipo_declarado=TipoVeiculo.SUCATA_INSERVIVEL,
        tipo=TipoVeiculo.SUCATA_INSERVIVEL,
        origem_aquisicao=OrigemAquisicao.COMPRA_DIRETA,
        documento_entrada_tipo=DocumentoEntradaTipo.NF_ENTRADA,
        documento_entrada_numero="1",
    )
    db_session.add(v)
    db_session.flush()
    cert = Certificado(
        veiculo_id=v.id,
        numero="CRV-TESTE-1",
        empresa_id=dados_demo.desmonte_id,
        tipo_veiculo=TipoVeiculo.SUCATA_INSERVIVEL,
        fator=Decimal("0.38"),
        emitido_em=datetime.now(UTC),
        hash_conteudo="0" * 64,
    )
    db_session.add(cert)
    db_session.flush()
    cred = UrvCredito(
        certificado_id=cert.id,
        geradora_id=dados_demo.desmonte_id,
        titular_id=dados_demo.desmonte_id,
        quantidade=Decimal("0.38"),
    )
    db_session.add(cred)
    db_session.flush()
    lanc = UrvLancamento(
        empresa_id=dados_demo.desmonte_id,
        tipo=LancamentoTipo.CREDITO,
        quantidade=Decimal("0.38"),
        credito_id=cred.id,
    )
    db_session.add(lanc)
    db_session.flush()
    return lanc


@pytest.mark.parametrize(
    "sql",
    ["UPDATE urv_lancamento SET quantidade = 1", "DELETE FROM urv_lancamento", "TRUNCATE urv_lancamento"],
)
def test_banco_rejeita_alteracao_em_urv_lancamento(db_session: Session, lancamento, sql: str) -> None:
    with pytest.raises(DBAPIError, match="só de inserção"), db_session.begin_nested():
        db_session.execute(text(sql))


# --- Rotas --------------------------------------------------------------------------------------


def test_rota_verificar(client, auth) -> None:
    r = client.get("/api/v1/auditoria/verificar", headers=auth(EMAIL_AUDITOR))
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["integra"] is True
    assert corpo["total"] > 0
    assert corpo["primeira_quebra"] is None


def test_rota_verificar_acusa_quebra(client, auth, db_session: Session) -> None:
    alvo = registrar_evento(db_session, None, "ALVO", "teste", None, {})
    _adulterar(db_session, alvo.sequencia)
    r = client.get("/api/v1/auditoria/verificar", headers=auth(EMAIL_ADMIN))
    assert r.json()["integra"] is False
    assert r.json()["primeira_quebra"] == alvo.sequencia


def test_rota_eventos_filtra_e_pagina(client, auth, dados_demo) -> None:
    r = client.get(
        "/api/v1/auditoria/eventos",
        params={"entidade": "empresa", "entidade_id": str(dados_demo.desmonte_id), "tamanho": 1},
        headers=auth(EMAIL_AUDITOR),
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total"] == 2  # criada e credenciada
    assert len(corpo["itens"]) == 1
    assert corpo["itens"][0]["tipo"] == "EMPRESA_CRIADA"

    r = client.get("/api/v1/auditoria/eventos", params={"tipo": "VINCULO_CRIADO"}, headers=auth(EMAIL_ADMIN))
    assert r.json()["total"] == 1


def test_rota_eventos_proibida_para_empresa(client, auth) -> None:
    r = client.get("/api/v1/auditoria/eventos", headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 403
    assert r.json()["codigo"] == "PAPEL_NAO_PERMITIDO"


def test_cadeia_serializada_entre_transacoes_concorrentes() -> None:
    """Duas transações gravando ao mesmo tempo não bifurcam a cadeia (pg_advisory_xact_lock).

    Usa um banco próprio, porque precisa de commits reais.
    """
    url = url_banco_teste("_concorrencia")
    recriar_banco(url)
    eng = create_engine(url, pool_size=4)
    erros: list[BaseException] = []
    barreira = threading.Barrier(4)

    def gravar(n: int) -> None:
        try:
            barreira.wait()
            for i in range(10):
                with Session(eng) as s:
                    registrar_evento(s, None, "CONCORRENTE", "teste", None, {"thread": n, "i": i})
                    s.commit()
        except BaseException as exc:  # noqa: BLE001
            erros.append(exc)

    threads = [threading.Thread(target=gravar, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        assert not erros
        with Session(eng) as s:
            r = verificar_cadeia(s)
            anteriores = s.scalars(select(EventoAuditoria.hash_anterior)).all()
        assert r.integra and r.total == 40
        assert len(set(anteriores)) == 40  # nenhum hash anterior repetido: sem bifurcação
    finally:
        eng.dispose()
        apagar_banco(url)
