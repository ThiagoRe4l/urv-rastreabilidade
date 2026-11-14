"""RF-03 e RF-04 (art. 5º): cadastro de MMV e início dos efeitos. RF-05 está fora do MVP."""

from datetime import date

import pytest

from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FISCAL,
    OPERADOR,
    chassis,
    consumir,
    criar_mmv,
    dec,
    erro,
    hojes,
    itens,
    ok,
)

MMV = {
    "codigo": "HATCH-10-FLEX-2027",
    "ncm": "87032100",
    "nivel": 1,
    "percentual_reciclabilidade": "87.50",
    "ja_comercializado": False,
}


# --- RF-03 ----------------------------------------------------------------------------------


def test_rf03_cadastro_de_mmv_com_codigo_ncm_nivel_e_percentual(api, demo) -> None:
    """Art. 5º I a III."""
    mmv = ok(api.post("/mmvs", FISCAL, json=MMV))
    assert mmv["codigo"] == MMV["codigo"]
    assert mmv["ncm"] == MMV["ncm"]
    assert mmv["nivel"] == 1
    assert dec(mmv["percentual_reciclabilidade"]) == dec("87.50")
    assert mmv["fabricante_id"] == str(demo.montadora_id)
    assert mmv["id"] in {m["id"] for m in itens(api.get("/mmvs", FISCAL))}


@pytest.mark.parametrize(("nivel", "rm"), [(1, 10), (2, 5)])
def test_rf03_rm_por_nivel(api, nivel, rm) -> None:
    """Art. 3º §3º: RM 10 (item 18, nível 1) ou 5 (item 17, nível 2)."""
    assert dec(criar_mmv(api, nivel=nivel)["rm"]) == rm


@pytest.mark.parametrize(
    "alteracao",
    [
        {"nivel": 3},
        {"nivel": 0},
        {"percentual_reciclabilidade": "100.01"},
        {"percentual_reciclabilidade": "-1"},
        {"codigo": ""},
        {"ncm": ""},
    ],
    ids=lambda a: "-".join(f"{k}={v}" for k, v in a.items()),
)
def test_rf03_dados_invalidos_rejeitados(api, alteracao) -> None:
    erro(api.post("/mmvs", FISCAL, json=MMV | alteracao), 422)


@pytest.mark.parametrize("campo", ["codigo", "ncm", "nivel", "percentual_reciclabilidade"])
def test_rf03_campos_obrigatorios(api, campo) -> None:
    corpo = {k: v for k, v in MMV.items() if k != campo}
    erro(api.post("/mmvs", FISCAL, json=corpo), 422)


def test_rf03_codigo_unico_por_fabricante(api, demo, nova_empresa) -> None:
    ok(api.post("/mmvs", FISCAL, json=MMV))
    erro(api.post("/mmvs", FISCAL, json=MMV), 409)
    outro = nova_empresa("FABRICANTE")
    ok(api.post("/mmvs", outro.email, json=MMV))  # o mesmo código em outro fabricante é outro MMV


@pytest.mark.parametrize("quem", [OPERADOR, ADMIN])
def test_rf03_somente_fabricante_cadastra_mmv(api, quem) -> None:
    """Art. 5º: quem cadastra é o fabricante ou importador."""
    erro(api.post("/mmvs", quem, json=MMV), 403)


def test_rf03_lista_de_mmv_por_fabricante(api, nova_empresa) -> None:
    outro = nova_empresa("FABRICANTE")
    meu = criar_mmv(api, FISCAL)
    alheio = criar_mmv(api, outro.email)

    assert {m["id"] for m in itens(api.get("/mmvs", FISCAL))} == {meu["id"]}
    assert {m["id"] for m in itens(api.get("/mmvs", outro.email))} == {alheio["id"]}
    assert {m["id"] for m in itens(api.get("/mmvs", AUDITOR))} >= {meu["id"], alheio["id"]}
    erro(api.get("/mmvs", OPERADOR), 403)


# --- RF-04 ----------------------------------------------------------------------------------


def test_rf04_mmv_novo_tem_efeitos_na_data_do_cadastro(api) -> None:
    """Art. 5º §2º II."""
    mmv = criar_mmv(api, ja_comercializado=False)
    assert mmv["efeitos_a_partir_de"] in hojes()


def test_rf04_mmv_ja_comercializado_tem_efeitos_em_primeiro_de_janeiro(api) -> None:
    """Art. 5º §2º I: 1º de janeiro do ano-calendário seguinte ao do cadastro."""
    mmv = criar_mmv(api, ja_comercializado=True)
    assert mmv["efeitos_a_partir_de"] in {f"{date.fromisoformat(h).year + 1}-01-01" for h in hojes()}


def test_rf04_consumo_antes_do_inicio_dos_efeitos_e_rejeitado(api) -> None:
    mmv = criar_mmv(api, ja_comercializado=True)
    erro(consumir(api, FISCAL, mmv["id"], chassis(1)), 422, "MMV_SEM_EFEITOS")
    assert itens(api.get("/urv/consumos", FISCAL)) == []


def test_rf04_consumo_a_partir_dos_efeitos_e_aceito(api) -> None:
    mmv = criar_mmv(api, ja_comercializado=False)
    ok(consumir(api, FISCAL, mmv["id"], chassis(1)))
