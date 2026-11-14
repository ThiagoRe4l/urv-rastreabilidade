"""RF-21 (arts. 28 e 29): um chassi em fim de vida credita uma vez; um chassi novo consome uma vez."""

from tests.conformidade.apoio import (
    AUDITOR,
    FISCAL,
    OPERADOR,
    chassis,
    consumir,
    criar_mmv,
    dados_veiculo,
    dec,
    emitir_certificado,
    erro,
    gerar_credito,
    itens,
    ok,
    receber_veiculo,
    saldo,
)

# --- Chassi em fim de vida ------------------------------------------------------------------


def test_rf21_chassi_em_fim_de_vida_registrado_uma_vez(api) -> None:
    v = receber_veiculo(api)
    erro(api.post("/veiculos", OPERADOR, json=dados_veiculo(chassi=v["chassi"])), 409, "CHASSI_DUPLICADO")
    assert len(itens(api.get("/veiculos", OPERADOR, params={"chassi": v["chassi"]}))) == 1


def test_rf21_chassi_em_fim_de_vida_nao_se_repete_entre_empresas(api, nova_empresa) -> None:
    """Art. 29: usar mais de uma empresa (ou plataforma) não pode duplicar o registro."""
    outra = nova_empresa("RECICLADORA")
    v = receber_veiculo(api)
    erro(api.post("/veiculos", outra.email, json=dados_veiculo(chassi=v["chassi"])), 409, "CHASSI_DUPLICADO")
    assert itens(api.get("/veiculos", outra.email)) == []


def test_rf21_chassi_e_o_mesmo_com_caixa_ou_espacos_diferentes(api) -> None:
    v = receber_veiculo(api)
    disfarcado = f" {v['chassi'].lower()} "
    r = api.post("/veiculos", OPERADOR, json=dados_veiculo(chassi=disfarcado))
    erro(r, (409, 422))
    assert len(itens(api.get("/veiculos", AUDITOR, params={"tamanho": 100}))) == 1


def test_rf21_um_certificado_e_um_credito_por_chassi(api) -> None:
    v, cert = gerar_credito(api, tipo="LICENCIADO_RODAGEM")
    erro(emitir_certificado(api, OPERADOR, v["id"]), 409, "CERTIFICADO_JA_EMITIDO")  # PM-04
    assert [c["id"] for c in itens(api.get("/certificados", OPERADOR))] == [cert["id"]]
    assert [c["id"] for c in itens(api.get("/urv/creditos", OPERADOR))] == [cert["credito"]["id"]]
    assert saldo(api, OPERADOR) == dec("1.00")
    assert len(itens(api.get("/urv/extrato", OPERADOR))) == 1


def test_rf21_chassi_ja_certificado_nao_volta_a_ser_recebido(api, nova_empresa) -> None:
    outra = nova_empresa("DESMONTADORA")
    v, _ = gerar_credito(api)
    for quem in (OPERADOR, outra.email):
        erro(api.post("/veiculos", quem, json=dados_veiculo(chassi=v["chassi"])), 409, "CHASSI_DUPLICADO")


# --- Chassi de veículo novo -----------------------------------------------------------------


def test_rf21_chassi_novo_consome_uma_vez(api) -> None:
    mmv = criar_mmv(api)
    vendido = chassis(1)
    ok(consumir(api, FISCAL, mmv["id"], vendido))
    erro(consumir(api, FISCAL, mmv["id"], vendido), 409, "CHASSI_JA_CONSUMIDO")
    assert saldo(api, FISCAL) == dec("-0.10")
    assert len(itens(api.get("/urv/consumos", FISCAL))) == 1


def test_rf21_chassi_novo_nao_se_repete_entre_mmv_nem_entre_fabricantes(api, nova_empresa) -> None:
    outro = nova_empresa("FABRICANTE")
    vendido = chassis(1)
    ok(consumir(api, FISCAL, criar_mmv(api)["id"], vendido))
    erro(consumir(api, FISCAL, criar_mmv(api)["id"], vendido), 409, "CHASSI_JA_CONSUMIDO")
    erro(consumir(api, outro.email, criar_mmv(api, outro.email)["id"], vendido), 409, "CHASSI_JA_CONSUMIDO")
    assert saldo(api, outro.email) == 0


def test_rf21_chassi_repetido_no_mesmo_consumo(api) -> None:
    mmv = criar_mmv(api)
    repetido = chassis(1) * 2
    erro(consumir(api, FISCAL, mmv["id"], repetido), 422, "CHASSI_REPETIDO_NA_LISTA")  # PM-URV-04
    assert saldo(api, FISCAL) == 0


def test_rf21_consumo_com_um_chassi_repetido_e_rejeitado_inteiro(api) -> None:
    mmv = criar_mmv(api)
    primeiro, segundo, terceiro = chassis(3)
    ok(consumir(api, FISCAL, mmv["id"], [primeiro]))
    erro(consumir(api, FISCAL, mmv["id"], [segundo, primeiro, terceiro]), 409, "CHASSI_JA_CONSUMIDO")
    assert saldo(api, FISCAL) == dec("-0.10")
    # Os outros dois não ficaram consumidos pela tentativa rejeitada.
    ok(consumir(api, FISCAL, mmv["id"], [segundo, terceiro]))
    assert saldo(api, FISCAL) == dec("-0.30")
