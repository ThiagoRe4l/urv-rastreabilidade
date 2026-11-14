"""RNF-07 (art. 21 III; art. 25 VI): casos negativos de antifraude.

Os oito casos pedidos em `agents/04-qa-conformidade.md`, na mesma ordem.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    EVIDENCIAS,
    FISCAL,
    OPERADOR,
    adulterar,
    anexar,
    assinar_laudo,
    chassis,
    cnpj_aleatorio,
    consumir,
    criar_mmv,
    criar_peca,
    dados_veiculo,
    dec,
    emitir_certificado,
    emitir_dmr,
    erro,
    gerar_credito,
    itens,
    ok,
    pesar,
    processar_veiculo,
    registrar_etapa,
    saldo,
    transferir,
)

# --- 1. Certificado sem cada uma das evidências ---------------------------------------------


@pytest.mark.parametrize("faltando", EVIDENCIAS)
def test_rnf07_certificado_sem_evidencia(api, faltando) -> None:
    """RF-15: cada etapa e cada evidência é condição do certificado e, portanto, do crédito."""
    v = processar_veiculo(api, omitir={faltando})
    assert v["pendencias_certificado"], f"sem {faltando}, deveria haver pendência"

    corpo = erro(emitir_certificado(api, OPERADOR, v["id"]), 422, "PENDENCIAS_CERTIFICADO")
    assert corpo["pendencias"]
    assert itens(api.get("/certificados", AUDITOR)) == []
    assert itens(api.get("/urv/creditos", OPERADOR)) == []
    assert saldo(api, OPERADOR) == 0


def test_rnf07_certificado_sai_quando_a_evidencia_que_faltava_e_anexada(api) -> None:
    """O bloqueio é pela evidência, não pelo veículo: suprida a falta, o certificado sai."""
    v = processar_veiculo(api, omitir={"foto_destruicao"})
    erro(emitir_certificado(api, OPERADOR, v["id"]), 422, "PENDENCIAS_CERTIFICADO")
    ok(anexar(api, OPERADOR, v["id"], "FOTO", "DESTRUICAO"))
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["pendencias_certificado"] == []
    ok(emitir_certificado(api, OPERADOR, v["id"]))


def test_rnf07_foto_de_outra_etapa_nao_supre_a_que_falta(api) -> None:
    v = processar_veiculo(api, omitir={"foto_descontaminacao"})
    ok(anexar(api, OPERADOR, v["id"], "FOTO", "RECEPCAO"))
    ok(anexar(api, OPERADOR, v["id"], "FOTO", "DESTRUICAO"))
    erro(emitir_certificado(api, OPERADOR, v["id"]), 422, "PENDENCIAS_CERTIFICADO")


def test_rnf07_etapa_so_iniciada_nao_conta_como_concluida(api) -> None:
    v = processar_veiculo(api, omitir={"etapa_desmontagem"})
    ok(registrar_etapa(api, OPERADOR, v["id"], "DESMONTAGEM", concluir=False))
    erro(emitir_certificado(api, OPERADOR, v["id"]), 422, "PENDENCIAS_CERTIFICADO")


# --- 2. Mesmo chassi em fim de vida em dois certificados ------------------------------------


def test_rnf07_mesmo_chassi_em_fim_de_vida_em_dois_certificados(api, demo, nova_empresa) -> None:
    """RF-21, arts. 28 e 29."""
    outra = nova_empresa("DESMONTADORA", vinculo_com=demo.montadora_id)
    v, cert = gerar_credito(api, tipo="LICENCIADO_RODAGEM")

    # Segunda emissão para o mesmo veículo.
    erro(emitir_certificado(api, OPERADOR, v["id"]), (409, 422))
    # O mesmo chassi registrado de novo, pela mesma empresa e por outra.
    for quem in (OPERADOR, outra.email):
        erro(api.post("/veiculos", quem, json=dados_veiculo(chassi=v["chassi"])), 409, "CHASSI_DUPLICADO")

    assert [c["id"] for c in itens(api.get("/certificados", AUDITOR))] == [cert["id"]]
    assert saldo(api, OPERADOR) == dec("1.00")
    assert saldo(api, outra.email) == 0


# --- 3. Mesmo chassi novo em dois consumos --------------------------------------------------


def test_rnf07_mesmo_chassi_novo_em_dois_consumos(api, nova_empresa) -> None:
    """RF-21: o mesmo veículo novo não justifica dois benefícios."""
    outro = nova_empresa("FABRICANTE")
    mmv = criar_mmv(api)
    vendidos = chassis(2)
    ok(consumir(api, FISCAL, mmv["id"], vendidos))

    erro(consumir(api, FISCAL, mmv["id"], [vendidos[0]]), 409, "CHASSI_JA_CONSUMIDO")
    erro(consumir(api, FISCAL, mmv["id"], [*chassis(1), vendidos[1]]), 409, "CHASSI_JA_CONSUMIDO")
    mmv_outro = criar_mmv(api, outro.email)
    erro(consumir(api, outro.email, mmv_outro["id"], [vendidos[0]]), 409, "CHASSI_JA_CONSUMIDO")

    assert len(itens(api.get("/urv/consumos", AUDITOR))) == 1
    assert saldo(api, FISCAL) == dec("-0.20")
    assert saldo(api, outro.email) == 0


# --- 4. Crédito transferido duas vezes ------------------------------------------------------


def test_rnf07_credito_transferido_duas_vezes(api, demo, nova_empresa) -> None:
    """RF-17: transferência única; o mesmo crédito não vai a dois fabricantes."""
    outro = nova_empresa("FABRICANTE", vinculo_com=demo.desmonte_id)
    _, cert = gerar_credito(api, tipo="SUCATA_APROVEITAVEL")  # 0,85
    credito_id = cert["credito"]["id"]
    ok(transferir(api, OPERADOR, credito_id, demo.montadora_id))

    erro(transferir(api, OPERADOR, credito_id, demo.montadora_id), 409, "CREDITO_JA_TRANSFERIDO")
    erro(transferir(api, OPERADOR, credito_id, outro.id), 409, "CREDITO_JA_TRANSFERIDO")

    assert saldo(api, OPERADOR) == 0
    assert saldo(api, FISCAL) == dec("0.85")
    assert saldo(api, outro.email) == 0
    assert len(itens(api.get("/urv/extrato", OPERADOR))) == 2  # crédito e uma única saída


# --- 5. Transferência para fabricante sem vínculo -------------------------------------------


def test_rnf07_transferencia_para_fabricante_sem_vinculo(api, demo, nova_empresa) -> None:
    """RF-17, art. 8º II; art. 13 §2º: vínculo atestado antes da transferência."""
    sem_vinculo = nova_empresa("FABRICANTE")
    _, cert = gerar_credito(api)
    credito_id = cert["credito"]["id"]

    erro(transferir(api, OPERADOR, credito_id, sem_vinculo.id), 422, "SEM_VINCULO")
    erro(transferir(api, OPERADOR, credito_id, uuid.uuid4()), (404, 422))  # fabricante inexistente
    assert saldo(api, sem_vinculo.email) == 0
    assert saldo(api, OPERADOR) == dec("0.38")

    # Lançado o vínculo, a mesma transferência passa.
    ok(
        api.post(
            "/vinculos", ADMIN, json={"geradora_id": str(demo.desmonte_id), "fabricante_id": sem_vinculo.id}
        )
    )
    ok(transferir(api, OPERADOR, credito_id, sem_vinculo.id))
    assert saldo(api, sem_vinculo.email) == dec("0.38")


# --- 6. Desmontadora lendo dados de outra empresa -------------------------------------------


def test_rnf07_desmontadora_nao_le_dados_de_outra_empresa(api, demo, nova_empresa) -> None:
    """RNF-01: confidencialidade. Registro de outra empresa responde como inexistente."""
    intrusa = nova_empresa("DESMONTADORA", vinculo_com=demo.montadora_id)
    v, cert = gerar_credito(api)
    ok(emitir_dmr(api, OPERADOR, v["id"]))
    detalhe = ok(api.get(f"/veiculos/{v['id']}", OPERADOR))
    peca = itens(api.get("/pecas", OPERADOR))[0]

    for rota in (
        f"/veiculos/{v['id']}",
        f"/veiculos/{v['id']}/pesagens",
        f"/veiculos/{v['id']}/dmrs",
        f"/anexos/{detalhe['anexos'][0]['id']}/arquivo",
        f"/certificados/{cert['id']}",
    ):
        erro(api.get(rota, intrusa.email), (403, 404))

    for rota, filtro in (
        ("/veiculos", {"chassi": v["chassi"]}),
        ("/pecas", {"chassi": v["chassi"]}),
        ("/certificados", {"empresa_id": str(demo.desmonte_id)}),
        ("/urv/creditos", {}),
        ("/urv/extrato", {"empresa_id": str(demo.desmonte_id)}),
    ):
        r = api.get(rota, intrusa.email, params=filtro)
        assert r.status_code in (200, 403), r.text
        if r.status_code == 200:
            assert r.json()["itens"] == [], rota
    assert saldo(api, intrusa.email) == 0
    assert v["chassi"] not in str(ok(api.get("/portabilidade/exportar", intrusa.email)))

    # E também não escreve no que não é dela.
    erro(anexar(api, intrusa.email, v["id"], "FOTO", "RECEPCAO"), (403, 404))
    erro(registrar_etapa(api, intrusa.email, v["id"], "DESTINACAO"), (403, 404))
    erro(pesar(api, intrusa.email, v["id"], "FERROSO", "RECICLAGEM", "1.000"), (403, 404))
    erro(emitir_dmr(api, intrusa.email, v["id"]), (403, 404))
    erro(api.patch(f"/pecas/{peca['id']}", intrusa.email, json={"destino": "REVENDA"}), (403, 404))
    erro(transferir(api, intrusa.email, cert["credito"]["id"], demo.montadora_id), (403, 404))


def test_rnf07_empresa_nao_emite_laudo_nem_certificado_de_veiculo_alheio(api, nova_empresa) -> None:
    intrusa = nova_empresa("RECICLADORA")
    v = processar_veiculo(api, omitir={"laudo"})
    erro(assinar_laudo(api, intrusa.email, v["id"]), (403, 404))
    ok(assinar_laudo(api, OPERADOR, v["id"]))
    erro(emitir_certificado(api, intrusa.email, v["id"]), (403, 404))
    assert saldo(api, intrusa.email) == 0
    erro(
        api.post(
            f"/veiculos/{v['id']}/pecas",
            intrusa.email,
            json={
                "nome": "Peça plantada",
                "descricao": "",
                "classificacao": "REUTILIZAVEL",
                "condicao": "USADA",
                "destino": "REVENDA",
            },
        ),
        (403, 404),
    )


def test_rnf07_fabricante_nao_le_o_fluxo_da_desmontadora(api) -> None:
    v, cert = gerar_credito(api)
    erro(api.get(f"/veiculos/{v['id']}", FISCAL), (403, 404))
    r = api.get("/veiculos", FISCAL)
    assert r.status_code in (200, 403)
    if r.status_code == 200:
        assert r.json()["itens"] == []


# --- 7. Auditor tentando escrever -----------------------------------------------------------


def test_rnf07_auditor_tentando_escrever(api, demo) -> None:
    """RNF-06: o auditor lê tudo e não altera nada, nem com dados válidos."""
    v = processar_veiculo(api, omitir={"laudo"})
    peca = criar_peca(api, OPERADOR, v["id"])
    mmv = criar_mmv(api)
    antes = ok(api.get("/auditoria/eventos", AUDITOR, params={"tamanho": 1}))["total"]

    tentativas = [
        api.post(
            "/empresas", AUDITOR, json={"cnpj": cnpj_aleatorio(), "razao_social": "X", "tipo": "RECICLADORA"}
        ),
        api.patch(
            f"/empresas/{demo.desmonte_id}/credenciamento",
            AUDITOR,
            json={"status": "CANCELADO", "validade": "2030-01-01"},
        ),
        api.patch(f"/vinculos/{demo.vinculo_id}", AUDITOR, json={"ativo": False}),
        api.post("/veiculos", AUDITOR, json=dados_veiculo()),
        anexar(api, AUDITOR, v["id"], "FOTO", "RECEPCAO"),
        registrar_etapa(api, AUDITOR, v["id"], "DESTINACAO"),
        api.patch(f"/pecas/{peca['id']}", AUDITOR, json={"destino": "REVENDA"}),
        pesar(api, AUDITOR, v["id"], "FERROSO", "RECICLAGEM", "1.000"),
        emitir_dmr(api, AUDITOR, v["id"]),
        assinar_laudo(api, AUDITOR, v["id"]),
        emitir_certificado(api, AUDITOR, v["id"]),
        consumir(api, AUDITOR, mmv["id"], chassis(1)),
    ]
    for r in tentativas:
        erro(r, 403, "AUDITOR_SOMENTE_LEITURA")

    assert ok(api.get("/auditoria/eventos", AUDITOR, params={"tamanho": 1}))["total"] == antes
    assert ok(api.get(f"/veiculos/{v['id']}", AUDITOR))["estado"] != "LAUDO_EMITIDO"


# --- 8. Evento de auditoria alterado direto no banco ----------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE evento_auditoria SET payload = '{}'",
        "UPDATE evento_auditoria SET hash = repeat('0', 64)",
        "DELETE FROM evento_auditoria",
    ],
)
def test_rnf07_evento_de_auditoria_alterado_direto_no_banco_e_barrado(api, db_session, sql) -> None:
    """RF-22: a tabela é só de inserção, por gatilho."""
    with pytest.raises(DBAPIError), db_session.begin_nested():
        db_session.execute(text(sql))
    assert ok(api.get("/auditoria/verificar", AUDITOR))["integra"] is True


def test_rnf07_evento_de_auditoria_adulterado_com_o_gatilho_desligado_e_acusado(api, db_session) -> None:
    """Quem tem acesso ao banco e desliga o gatilho ainda quebra a cadeia de hashes."""
    eventos = ok(api.get("/auditoria/eventos", AUDITOR, params={"tamanho": 100}))["itens"]
    alvo = sorted(e["sequencia"] for e in eventos)[len(eventos) // 2]

    adulterar(db_session, alvo)

    resultado = ok(api.get("/auditoria/verificar", AUDITOR))
    assert resultado["integra"] is False
    assert resultado["primeira_quebra"] == alvo


def test_rnf07_evento_de_auditoria_do_fluxo_adulterado_e_acusado(api, db_session) -> None:
    """O mesmo, sobre o evento de um certificado: reescrever o que gerou crédito aparece."""
    _, cert = gerar_credito(api)
    eventos = ok(api.get("/auditoria/eventos", AUDITOR, params={"entidade_id": cert["id"]}))["itens"]
    alvo = eventos[0]["sequencia"]
    adulterar(db_session, alvo)
    resultado = ok(api.get("/auditoria/verificar", AUDITOR))
    assert resultado["integra"] is False
    assert resultado["primeira_quebra"] == alvo
