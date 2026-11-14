"""RF-09 (art. 18 V; Anexo III 6 a 8) e RF-10 (Anexo III 16): peças, etiqueta e consulta."""

import pytest

from scripts.seed import CNPJ_DESMONTE
from tests.conformidade.apoio import (
    AUDITOR,
    FISCAL,
    OPERADOR,
    criar_peca,
    erro,
    hojes,
    itens,
    ok,
    receber_veiculo,
)


def _so_digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


# --- RF-09 ----------------------------------------------------------------------------------


def test_rf09_peca_reutilizavel_recebe_etiqueta_com_nome_chassi_data_e_cnpj(api) -> None:
    """Art. 18 V: código de rastreio com nome da peça, chassi, data e CNPJ da desmontadora."""
    v = receber_veiculo(api)
    peca = criar_peca(api, OPERADOR, v["id"], nome="Alternador")
    assert peca["classificacao"] == "REUTILIZAVEL"
    assert peca["codigo_rastreio"]
    etiqueta = peca["etiqueta"]
    assert etiqueta["nome"] == "Alternador"
    assert etiqueta["chassi"] == v["chassi"]
    assert etiqueta["data"][:10] in hojes()
    assert _so_digitos(etiqueta["cnpj"]) == CNPJ_DESMONTE
    assert etiqueta["codigo"] == peca["codigo_rastreio"]


def test_rf09_cada_peca_e_etiquetada_individualmente(api) -> None:
    v = receber_veiculo(api)
    codigos = {
        criar_peca(api, OPERADOR, v["id"], nome="Roda de liga leve")["codigo_rastreio"] for _ in range(4)
    }
    assert len(codigos) == 4


@pytest.mark.parametrize("classificacao", ["REUTILIZAVEL", "NAO_REUTILIZAVEL"])
def test_rf09_peca_classificada_como_reutilizavel_ou_nao(api, classificacao) -> None:
    """Anexo III 6."""
    v = receber_veiculo(api)
    peca = criar_peca(api, OPERADOR, v["id"], classificacao=classificacao, destino="RECICLAGEM")
    assert peca["classificacao"] == classificacao


def test_rf09_classificacao_e_obrigatoria_e_fechada(api) -> None:
    v = receber_veiculo(api)
    corpo = {"nome": "Farol", "descricao": "Farol direito", "condicao": "USADA", "destino": "ESTOQUE"}
    erro(api.post(f"/veiculos/{v['id']}/pecas", OPERADOR, json=corpo), 422)
    erro(api.post(f"/veiculos/{v['id']}/pecas", OPERADOR, json=corpo | {"classificacao": "TALVEZ"}), 422)


def test_rf09_peca_nao_reutilizavel_nao_tem_etiqueta_e_e_descaracterizada(api) -> None:
    """Art. 18 V, parte final: as peças não reutilizáveis devem ser descaracterizadas."""
    v = receber_veiculo(api)
    peca = criar_peca(
        api, OPERADOR, v["id"], nome="Longarina", classificacao="NAO_REUTILIZAVEL", destino="RECICLAGEM"
    )
    assert not peca.get("codigo_rastreio")
    assert not peca.get("etiqueta")
    assert not peca["descaracterizada"]
    atualizada = ok(api.patch(f"/pecas/{peca['id']}", OPERADOR, json={"descaracterizada": True}))
    assert atualizada["descaracterizada"] is True


def test_rf09_consulta_publica_da_etiqueta(api) -> None:
    """A leitura do QR Code não exige login."""
    v = receber_veiculo(api)
    peca = criar_peca(api, OPERADOR, v["id"], nome="Caixa de câmbio", destino="REVENDA")
    corpo = ok(api.get(f"/pecas/rastreio/{peca['codigo_rastreio']}"))
    etiqueta = corpo.get("etiqueta", corpo)
    assert etiqueta["nome"] == "Caixa de câmbio"
    assert etiqueta["chassi"] == v["chassi"]
    assert _so_digitos(etiqueta["cnpj"]) == CNPJ_DESMONTE
    assert etiqueta["data"][:10] in hojes()
    assert corpo["destino"] == "REVENDA"


def test_rf09_codigo_de_rastreio_inexistente(api) -> None:
    erro(api.get("/pecas/rastreio/CODIGO-QUE-NAO-EXISTE"), 404)


def test_rf09_fabricante_nao_registra_pecas(api) -> None:
    v = receber_veiculo(api)
    corpo = {
        "nome": "Farol",
        "descricao": "",
        "classificacao": "REUTILIZAVEL",
        "condicao": "USADA",
        "destino": "ESTOQUE",
    }
    erro(api.post(f"/veiculos/{v['id']}/pecas", FISCAL, json=corpo), (403, 404))


# --- RF-10 ----------------------------------------------------------------------------------


@pytest.fixture
def estoque(api) -> dict:
    a = receber_veiculo(api)
    b = receber_veiculo(api)
    pecas = {
        "motor": criar_peca(
            api, OPERADOR, a["id"], nome="Motor 1.0", condicao="REMANUFATURADA", destino="REMANUFATURA"
        ),
        "porta": criar_peca(api, OPERADOR, a["id"], nome="Porta traseira", destino="REVENDA"),
        "banco": criar_peca(api, OPERADOR, b["id"], nome="Banco do motorista", destino="ESTOQUE"),
        "airbag": criar_peca(
            api, OPERADOR, b["id"], nome="Airbag", classificacao="NAO_REUTILIZAVEL", destino="DESCARTE"
        ),
    }
    return {"a": a, "b": b, "ids": {nome: p["id"] for nome, p in pecas.items()}}


@pytest.mark.parametrize(
    ("filtro", "esperadas"),
    [
        ({"condicao": "REMANUFATURADA"}, {"motor"}),
        ({"destino": "REVENDA"}, {"porta"}),
        ({"destino": "ESTOQUE"}, {"banco"}),
        ({"classificacao": "NAO_REUTILIZAVEL"}, {"airbag"}),
        ({"classificacao": "REUTILIZAVEL"}, {"motor", "porta", "banco"}),
        ({"nome": "Porta"}, {"porta"}),
        ({"condicao": "USADA", "destino": "REVENDA"}, {"porta"}),
        ({}, {"motor", "porta", "banco", "airbag"}),
    ],
    ids=lambda x: "-".join(f"{k}={v}" for k, v in x.items()) if isinstance(x, dict) else None,
)
def test_rf10_consulta_de_pecas_por_tipo_condicao_e_destino(api, estoque, filtro, esperadas) -> None:
    """Anexo III 16 b, c e d."""
    achadas = {p["id"] for p in itens(api.get("/pecas", OPERADOR, params=filtro | {"tamanho": 100}))}
    assert achadas == {estoque["ids"][nome] for nome in esperadas}


def test_rf10_consulta_de_pecas_por_origem(api, estoque) -> None:
    """Anexo III 16 a: origem (chassi do veículo)."""
    achadas = {p["id"] for p in itens(api.get("/pecas", OPERADOR, params={"chassi": estoque["a"]["chassi"]}))}
    assert achadas == {estoque["ids"]["motor"], estoque["ids"]["porta"]}
    do_auditor = {
        p["id"] for p in itens(api.get("/pecas", AUDITOR, params={"chassi": estoque["b"]["chassi"]}))
    }
    assert do_auditor == {estoque["ids"]["banco"], estoque["ids"]["airbag"]}


@pytest.mark.parametrize("destino", ["ESTOQUE", "REVENDA", "EXPORTACAO", "REMANUFATURA", "RECONDICIONAMENTO"])
def test_rf10_destinos_da_peca(api, destino) -> None:
    """Anexo III 16 d: estoque, revenda, exportação, remanufatura ou recondicionamento."""
    v = receber_veiculo(api)
    assert criar_peca(api, OPERADOR, v["id"], destino=destino)["destino"] == destino


def test_rf10_mudanca_de_destino_aparece_na_consulta(api) -> None:
    v = receber_veiculo(api)
    peca = criar_peca(api, OPERADOR, v["id"], destino="ESTOQUE")
    assert (
        ok(api.patch(f"/pecas/{peca['id']}", OPERADOR, json={"destino": "EXPORTACAO"}))["destino"]
        == "EXPORTACAO"
    )
    exportadas = itens(api.get("/pecas", OPERADOR, params={"destino": "EXPORTACAO"}))
    assert [p["id"] for p in exportadas] == [peca["id"]]
    assert ok(api.get(f"/pecas/rastreio/{peca['codigo_rastreio']}"))["destino"] == "EXPORTACAO"
