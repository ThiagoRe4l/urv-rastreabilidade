"""RF-11 (art. 18 §6º), RF-12 (art. 18 §5º) e RF-13 (art. 6º III d; Anexo III 14.d)."""

from datetime import date

import pytest

from tests.conformidade.apoio import (
    AUDITOR,
    FISCAL,
    OPERADOR,
    cnpj_aleatorio,
    dec,
    emitir_certificado,
    emitir_dmr,
    erro,
    itens,
    ok,
    pesar,
    processar_veiculo,
    receber_veiculo,
    registrar_etapa,
)

FRACOES = ["FERROSO", "NAO_FERROSO", "NAO_METALICO", "FLUIDOS", "BATERIAS", "PNEUS"]
DESTINOS = ["REAPROVEITAMENTO", "RECICLAGEM", "RECUPERACAO_ENERGETICA", "REJEITO"]


def meta_do_ano(ano: int) -> int | None:
    """Art. 18 §5º; em 2026 há só registro (§7º)."""
    if ano < 2027:
        return None
    return 80 if ano <= 2028 else 85 if ano <= 2030 else 90 if ano <= 2032 else 95


# --- RF-11 ----------------------------------------------------------------------------------


@pytest.mark.parametrize("fracao", FRACOES)
def test_rf11_peso_por_fracao_de_material(api, fracao) -> None:
    """Anexo III 14.c: ferrosos, não ferrosos e não metálicos; e os itens da descontaminação."""
    v = receber_veiculo(api)
    pesagem = ok(pesar(api, OPERADOR, v["id"], fracao, "RECICLAGEM", "123.456"))
    assert pesagem["fracao"] == fracao
    assert pesagem["destino"] == "RECICLAGEM"
    assert dec(pesagem["peso_kg"]) == dec("123.456")
    assert isinstance(pesagem["peso_kg"], str)  # Decimal trafega como string


def test_rf11_pesos_por_veiculo(api) -> None:
    """Art. 18 §6º: o registro é por veículo."""
    a = receber_veiculo(api)
    b = receber_veiculo(api)
    ok(pesar(api, OPERADOR, a["id"], "FERROSO", "RECICLAGEM", "700.500"))
    ok(pesar(api, OPERADOR, a["id"], "NAO_FERROSO", "REAPROVEITAMENTO", "90.250"))
    ok(pesar(api, OPERADOR, b["id"], "PNEUS", "RECUPERACAO_ENERGETICA", "40.000"))

    do_a = itens(api.get(f"/veiculos/{a['id']}/pesagens", OPERADOR))
    assert sorted(dec(p["peso_kg"]) for p in do_a) == [dec("90.250"), dec("700.500")]
    do_b = itens(api.get(f"/veiculos/{b['id']}/pesagens", AUDITOR))
    assert [(p["fracao"], dec(p["peso_kg"])) for p in do_b] == [("PNEUS", dec("40.000"))]


@pytest.mark.parametrize(
    "alteracao",
    [{"peso_kg": "0"}, {"peso_kg": "-5.000"}, {"fracao": "VIDRO_FUME"}, {"destino": "QUINTAL"}],
    ids=lambda a: "-".join(f"{k}={v}" for k, v in a.items()),
)
def test_rf11_pesagem_invalida_rejeitada(api, alteracao) -> None:
    v = receber_veiculo(api)
    corpo = {"fracao": "FERROSO", "destino": "RECICLAGEM", "peso_kg": "10.000"} | alteracao
    erro(api.post(f"/veiculos/{v['id']}/pesagens", OPERADOR, json=corpo), 422)
    assert itens(api.get(f"/veiculos/{v['id']}/pesagens", OPERADOR)) == []


def test_rf11_fabricante_nao_registra_pesagem(api) -> None:
    v = receber_veiculo(api)
    erro(pesar(api, FISCAL, v["id"], "FERROSO", "RECICLAGEM", "10.000"), (403, 404))


# --- RF-12 ----------------------------------------------------------------------------------


def test_rf12_percentual_aproveitado_e_o_peso_que_nao_e_rejeito(api) -> None:
    v = receber_veiculo(api)
    for i, destino in enumerate(DESTINOS):
        ok(pesar(api, OPERADOR, v["id"], FRACOES[i], destino, "250.000"))
    # Reaproveitamento, reciclagem e recuperação energética contam; rejeito não: 750 / 1000.
    pesagens = ok(api.get(f"/veiculos/{v['id']}/pesagens", OPERADOR))
    assert dec(pesagens["percentual_aproveitado"]) == dec("75")  # em pontos, de 0 a 100
    assert dec(ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["percentual_aproveitado"]) == dec("75")


def test_rf12_percentual_com_arredondamento_half_up(api) -> None:
    v = receber_veiculo(api)
    ok(pesar(api, OPERADOR, v["id"], "FERROSO", "RECICLAGEM", "2.000"))
    ok(pesar(api, OPERADOR, v["id"], "NAO_METALICO", "REJEITO", "1.000"))
    percentual = dec(ok(api.get(f"/veiculos/{v['id']}/pesagens", OPERADOR))["percentual_aproveitado"])
    assert percentual == dec("66.67")


def test_rf12_certificado_grava_percentual_e_meta_do_ano(api) -> None:
    v = processar_veiculo(api)  # 900 kg aproveitados de 1000 kg
    cert = ok(emitir_certificado(api, OPERADOR, v["id"]))
    assert dec(cert["percentual_aproveitado"]) == dec("90")
    meta = meta_do_ano(date.fromisoformat(cert["emitido_em"][:10]).year)
    if meta is None:
        assert cert["meta_ano"] is None  # 2026: só registro (art. 18 §7º)
    else:
        assert dec(cert["meta_ano"]) == meta
        assert cert["atende_meta"] is (meta <= 90)


def test_rf12_aproveitamento_baixo_gera_alerta_e_nao_bloqueia(api) -> None:
    """Premissa: o descumprimento da meta é apurado pelo MDIC (art. 17 §2º)."""
    pesagens = [("FERROSO", "RECICLAGEM", "100.000"), ("NAO_METALICO", "REJEITO", "900.000")]
    v = processar_veiculo(api, pesagens=pesagens)
    cert = ok(emitir_certificado(api, OPERADOR, v["id"]))
    assert dec(cert["percentual_aproveitado"]) == dec("10")
    if cert["meta_ano"] is not None:
        assert cert["atende_meta"] is False
    assert cert["credito"]


# --- RF-13 ----------------------------------------------------------------------------------


def test_rf13_dmr_com_nome_e_cnpj_do_destinatario_por_material(api) -> None:
    v = receber_veiculo(api)
    cnpj = cnpj_aleatorio()
    r = emitir_dmr(
        api,
        OPERADOR,
        v["id"],
        numero="DMR-2026-0001",
        destinatario_nome="Aços Curitiba S.A.",
        destinatario_cnpj=cnpj,
        tipo_material="Sucata ferrosa",
        peso_kg="812.300",
    )
    dmr = ok(r)
    assert dmr["numero"] == "DMR-2026-0001"
    assert dmr["destinatario_nome"] == "Aços Curitiba S.A."
    assert "".join(c for c in dmr["destinatario_cnpj"] if c.isdigit()) == cnpj
    assert dmr["tipo_material"] == "Sucata ferrosa"
    assert dec(dmr["peso_kg"]) == dec("812.300")
    assert dmr["mtr_numero"]  # MTR do SINIR, simulado (Anexo III 13)
    assert dmr["emitida_em"]


def test_rf13_uma_dmr_por_tipo_de_material(api) -> None:
    v = receber_veiculo(api)
    for material in ("Sucata ferrosa", "Alumínio", "Plásticos"):
        ok(emitir_dmr(api, OPERADOR, v["id"], tipo_material=material))
    dmrs = itens(api.get(f"/veiculos/{v['id']}/dmrs", OPERADOR))
    assert {d["tipo_material"] for d in dmrs} == {"Sucata ferrosa", "Alumínio", "Plásticos"}
    assert len({d["mtr_numero"] for d in dmrs}) == 3


@pytest.mark.parametrize("campo", ["destinatario_nome", "destinatario_cnpj", "tipo_material", "peso_kg"])
def test_rf13_dmr_exige_destinatario_material_e_peso(api, campo) -> None:
    v = receber_veiculo(api)
    corpo = {
        "numero": "DMR-1",
        "destinatario_nome": "Aços Curitiba S.A.",
        "destinatario_cnpj": cnpj_aleatorio(),
        "tipo_material": "Sucata ferrosa",
        "peso_kg": "10.000",
    }
    del corpo[campo]
    erro(api.post(f"/veiculos/{v['id']}/dmrs", OPERADOR, json=corpo), 422)


def test_rf13_cnpj_do_destinatario_invalido(api) -> None:
    v = receber_veiculo(api)
    erro(emitir_dmr(api, OPERADOR, v["id"], destinatario_cnpj="12345678000100"), 422)


def test_rf13_veiculo_encerrado_com_destinacao_e_dmr(api) -> None:
    """Art. 18 IX: a destinação fecha o fluxo, com o controle da DMR."""
    v = processar_veiculo(api)
    ok(emitir_certificado(api, OPERADOR, v["id"]))
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["estado"] == "CERTIFICADO"
    ok(emitir_dmr(api, OPERADOR, v["id"]))
    ok(registrar_etapa(api, OPERADOR, v["id"], "DESTINACAO"))
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["estado"] == "ENCERRADO"


def test_rf13_sem_dmr_a_destinacao_nao_encerra_o_veiculo(api) -> None:
    v = processar_veiculo(api)
    ok(emitir_certificado(api, OPERADOR, v["id"]))
    r = registrar_etapa(api, OPERADOR, v["id"], "DESTINACAO")
    assert r.status_code in (200, 201, 409, 422)
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["estado"] == "CERTIFICADO"
