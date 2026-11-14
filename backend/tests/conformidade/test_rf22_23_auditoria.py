"""RF-22 (art. 20 V; art. 24 I) e RF-23 (art. 9º; art. 24 V): trilha imutável e visão de auditoria."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FISCAL,
    OPERADOR,
    adulterar,
    chassis,
    cnpj_aleatorio,
    consumir,
    criar_mmv,
    emitir_dmr,
    erro,
    gerar_credito,
    itens,
    ok,
    transferir,
)


def _eventos(api, **filtros) -> dict:
    return ok(api.get("/auditoria/eventos", AUDITOR, params=filtros))


# --- RF-22 ----------------------------------------------------------------------------------


def test_rf22_escrita_de_negocio_gera_evento(api) -> None:
    antes = _eventos(api, tamanho=1)["total"]
    corpo = {"cnpj": cnpj_aleatorio(), "razao_social": "Recicla Sul Ltda.", "tipo": "RECICLADORA"}
    empresa = ok(api.post("/empresas", ADMIN, json=corpo))

    da_empresa = _eventos(api, entidade="empresa", entidade_id=empresa["id"])
    assert da_empresa["total"] == 1
    evento = da_empresa["itens"][0]
    assert evento["entidade_id"] == empresa["id"]
    assert evento["tipo"]
    assert evento["ocorrido_em"]
    assert _eventos(api, tamanho=1)["total"] == antes + 1


def test_rf22_leitura_e_escrita_rejeitada_nao_geram_evento(api) -> None:
    antes = _eventos(api, tamanho=1)["total"]
    api.get("/empresas", ADMIN)
    erro(
        api.post(
            "/empresas", OPERADOR, json={"cnpj": cnpj_aleatorio(), "razao_social": "X", "tipo": "RECICLADORA"}
        ),
        403,
    )
    assert _eventos(api, tamanho=1)["total"] == antes


def test_rf22_eventos_encadeados_por_hash(api) -> None:
    for _ in range(3):
        corpo = {"cnpj": cnpj_aleatorio(), "razao_social": "Encadeada Ltda.", "tipo": "DESMONTADORA"}
        ok(api.post("/empresas", ADMIN, json=corpo))
    eventos = sorted(_eventos(api, tamanho=100)["itens"], key=lambda e: e["sequencia"])
    assert len(eventos) >= 4
    for anterior, atual in zip(eventos, eventos[1:], strict=False):
        assert atual["hash_anterior"] == anterior["hash"]
        assert len(atual["hash"]) == 64
    assert len({e["hash"] for e in eventos}) == len(eventos)


def test_rf22_cadeia_integra(api) -> None:
    resultado = ok(api.get("/auditoria/verificar", AUDITOR))
    assert resultado["integra"] is True
    assert resultado["total"] > 0
    assert resultado["primeira_quebra"] is None


@pytest.mark.parametrize(
    "sql",
    ["UPDATE evento_auditoria SET tipo = 'X'", "DELETE FROM evento_auditoria", "TRUNCATE evento_auditoria"],
)
def test_rf22_banco_rejeita_alteracao_da_trilha(api, db_session, sql) -> None:
    with pytest.raises(DBAPIError), db_session.begin_nested():
        db_session.execute(text(sql))
    assert ok(api.get("/auditoria/verificar", AUDITOR))["integra"] is True


def test_rf22_adulteracao_e_acusada_na_verificacao(api, db_session) -> None:
    for _ in range(2):
        corpo = {"cnpj": cnpj_aleatorio(), "razao_social": "Alvo Ltda.", "tipo": "DESMONTADORA"}
        alvo = ok(api.post("/empresas", ADMIN, json=corpo))
    sequencia = _eventos(api, entidade="empresa", entidade_id=alvo["id"])["itens"][0]["sequencia"]
    ok(
        api.post(
            "/empresas",
            ADMIN,
            json={"cnpj": cnpj_aleatorio(), "razao_social": "Depois", "tipo": "RECICLADORA"},
        )
    )

    adulterar(db_session, sequencia)

    resultado = ok(api.get("/auditoria/verificar", AUDITOR))
    assert resultado["integra"] is False
    assert resultado["primeira_quebra"] == sequencia


@pytest.mark.parametrize("quem", [OPERADOR, FISCAL])
@pytest.mark.parametrize("rota", ["/auditoria/eventos", "/auditoria/verificar"])
def test_rf22_trilha_restrita_a_auditor_e_admin(api, quem, rota) -> None:
    erro(api.get(rota, quem), 403)


def test_rf22_fluxo_completo_fica_na_trilha(api, demo) -> None:
    """Todos os eventos: recepção, certificado, crédito, transferência e consumo."""
    v, cert = gerar_credito(api)
    credito = cert["credito"]
    ok(transferir(api, OPERADOR, credito["id"], demo.montadora_id))
    mmv = criar_mmv(api)
    consumo = ok(consumir(api, FISCAL, mmv["id"], chassis(2)))

    for nome, entidade_id in [
        ("veiculo", v["id"]),
        ("certificado", cert["id"]),
        ("credito", credito["id"]),
        ("mmv", mmv["id"]),
        ("consumo", consumo["id"]),
    ]:
        assert _eventos(api, entidade_id=entidade_id)["total"] >= 1, f"sem evento para {nome}"
    # Recepção, anexos, etapas, peças, pesagens e laudo: mais de um evento ligado ao fluxo.
    assert ok(api.get("/auditoria/verificar", AUDITOR))["integra"] is True


# --- RF-23 ----------------------------------------------------------------------------------


def test_rf23_auditor_le_cadastros_e_trilha(api, demo) -> None:
    empresas = {e["id"] for e in itens(api.get("/empresas", AUDITOR, params={"tamanho": 100}))}
    assert empresas >= {str(demo.desmonte_id), str(demo.montadora_id)}
    assert itens(api.get("/vinculos", AUDITOR))
    assert _eventos(api)["total"] > 0
    assert itens(api.get("/configuracao/fatores", AUDITOR))


def test_rf23_auditor_le_todos_os_registros_do_fluxo(api, demo, nova_empresa) -> None:
    """Art. 24 V: acesso supervisionado a tudo, de qualquer empresa."""
    outra = nova_empresa("RECICLADORA", vinculo_com=demo.montadora_id)
    registros = []
    for quem in (OPERADOR, outra.email):
        v, cert = gerar_credito(api, quem)
        ok(emitir_dmr(api, quem, v["id"]))
        registros.append((v, cert))
    ok(transferir(api, OPERADOR, registros[0][1]["credito"]["id"], demo.montadora_id))
    mmv = criar_mmv(api)
    consumo = ok(consumir(api, FISCAL, mmv["id"], chassis(1)))

    todos_chassis = {x["chassi"] for x in itens(api.get("/veiculos", AUDITOR, params={"tamanho": 100}))}
    assert todos_chassis >= {v["chassi"] for v, _ in registros}
    certificados = {c["id"] for c in itens(api.get("/certificados", AUDITOR, params={"tamanho": 100}))}
    assert certificados >= {c["id"] for _, c in registros}

    for v, cert in registros:
        detalhe = ok(api.get(f"/veiculos/{v['id']}", AUDITOR))
        assert detalhe["etapas"] and detalhe["anexos"]
        ok(api.get(f"/anexos/{detalhe['anexos'][0]['id']}/arquivo", AUDITOR))
        assert itens(api.get("/pecas", AUDITOR, params={"chassi": v["chassi"]}))
        assert itens(api.get(f"/veiculos/{v['id']}/pesagens", AUDITOR))
        assert itens(api.get(f"/veiculos/{v['id']}/dmrs", AUDITOR))
        completo = ok(api.get(f"/certificados/{cert['id']}", AUDITOR))
        assert completo["laudo"] and completo["veiculo"] and completo["credito"]

    do_emissor = itens(api.get("/certificados", AUDITOR, params={"empresa_id": outra.id}))
    assert [c["id"] for c in do_emissor] == [registros[1][1]["id"]]

    for empresa_id in (str(demo.desmonte_id), outra.id, str(demo.montadora_id)):
        assert itens(api.get("/urv/extrato", AUDITOR, params={"empresa_id": empresa_id}))
    assert mmv["id"] in {m["id"] for m in itens(api.get("/mmvs", AUDITOR))}
    assert consumo["id"] in {c["id"] for c in itens(api.get("/urv/consumos", AUDITOR))}


def test_rf23_linha_do_tempo_do_chassi(api) -> None:
    """Roteiro, passo 8: o auditor busca o chassi e vê a linha do tempo."""
    v, cert = gerar_credito(api)
    achados = itens(api.get("/veiculos", AUDITOR, params={"chassi": v["chassi"]}))
    assert [x["id"] for x in achados] == [v["id"]]
    eventos = _eventos(api, entidade_id=v["id"], tamanho=100)
    assert eventos["total"] >= 1
    assert _eventos(api, entidade_id=cert["id"])["total"] >= 1
