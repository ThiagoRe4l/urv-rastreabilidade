"""RF-24 (art. 27), RF-25 (art. 22), RNF-04 (arts. 22, 28 e 29) e RNF-05 (art. 19 §2º; art. 24 X)."""

import json
from datetime import date
from decimal import Decimal

import pytest

from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FISCAL,
    OPERADOR,
    Api,
    chassis,
    consumir,
    criar_mmv,
    dec,
    emitir_dmr,
    erro,
    gerar_credito,
    itens,
    ok,
    receber_veiculo,
    saldo,
    transferir,
)


def _relatorio(api: Api, quem: str = AUDITOR, **params) -> dict:
    return ok(api.get("/relatorios/mdic", quem, params=params))


def _exportar(api: Api, quem: str) -> dict:
    r = api.get("/portabilidade/exportar", quem)
    assert r.status_code == 200, r.text
    return r.json()


def _importar(api: Api, quem: str, arquivo: dict):
    """O contrato fixa o documento exportado no corpo, como `application/json` (PM-URV-03 b)."""
    return api.post("/portabilidade/importar", quem, json=arquivo)


def _pesos(materiais) -> Decimal:
    """Soma os pesos de `materiais`, seja lista de linhas, seja dicionário aninhado."""
    if isinstance(materiais, dict):
        if "peso_kg" in materiais:
            return dec(materiais["peso_kg"])
        return sum((_pesos(v) for v in materiais.values()), Decimal(0))
    if isinstance(materiais, list):
        return sum((_pesos(v) for v in materiais), Decimal(0))
    try:
        return dec(materiais)
    except ArithmeticError:
        return Decimal(0)


# --- RF-24 ----------------------------------------------------------------------------------


def test_rf24_relatorio_de_registros_certificados_e_urv(api, demo) -> None:
    """Art. 27 I: número de registros e de certificados emitidos."""
    vazio = _relatorio(api)
    assert vazio["registros"] == 0
    assert vazio["certificados_emitidos"] == 0
    assert dec(vazio["urv_gerada"]) == 0

    _, primeiro = gerar_credito(api, tipo="LICENCIADO_RODAGEM")  # 1,00
    gerar_credito(api, tipo="SUCATA_APROVEITAVEL")  # 0,85
    receber_veiculo(api)  # registrado, ainda sem certificado
    ok(transferir(api, OPERADOR, primeiro["credito"]["id"], demo.montadora_id))
    ok(consumir(api, FISCAL, criar_mmv(api)["id"], chassis(4)))  # 0,40

    relatorio = _relatorio(api)
    assert relatorio["registros"] == 3
    assert relatorio["certificados_emitidos"] == 2
    assert dec(relatorio["urv_gerada"]) == dec("1.85")
    assert dec(relatorio["urv_transferida"]) == dec("1.00")
    assert dec(relatorio["urv_consumida"]) == dec("0.40")


def test_rf24_relatorio_de_volume_de_materiais(api) -> None:
    """Art. 27 II: volume de materiais rastreados e destinados, por fração e destino."""
    assert _pesos(_relatorio(api)["materiais"]) == 0
    gerar_credito(api)  # 800 + 100 + 100 kg
    gerar_credito(api, pesagens=[("PNEUS", "RECUPERACAO_ENERGETICA", "35.500")])
    materiais = _relatorio(api)["materiais"]
    assert _pesos(materiais) == dec("1035.500")
    texto = json.dumps(materiais)
    for termo in ("FERROSO", "NAO_METALICO", "PNEUS", "RECICLAGEM", "REJEITO", "RECUPERACAO_ENERGETICA"):
        assert termo in texto


def test_rf24_relatorio_por_ano(api) -> None:
    gerar_credito(api)
    ano = date.today().year
    assert _relatorio(api, ano=ano)["certificados_emitidos"] == 1
    anterior = _relatorio(api, ano=ano - 1)
    assert anterior["certificados_emitidos"] == 0
    assert dec(anterior["urv_gerada"]) == 0


def test_rf24_relatorio_disponivel_ao_mdic_e_ao_admin(api) -> None:
    assert _relatorio(api, ADMIN) == _relatorio(api, AUDITOR)


@pytest.mark.parametrize("quem", [OPERADOR, FISCAL])
def test_rf24_relatorio_nao_e_aberto_as_empresas(api, quem) -> None:
    erro(api.get("/relatorios/mdic", quem), 403)


# --- RF-25, RNF-05 --------------------------------------------------------------------------


def test_rf25_exportacao_em_json_versionado(api) -> None:
    arquivo = _exportar(api, OPERADOR)
    assert isinstance(arquivo, dict)
    versoes = [k for k in arquivo if "versao" in k.lower()]
    assert versoes and arquivo[versoes[0]], arquivo.keys()


def test_rnf05_historico_completo_exportavel_pela_propria_geradora(api, demo) -> None:
    """Art. 22 I: registros operacionais, certificados, laudos, saldos e transferências."""
    v, cert = gerar_credito(api, tipo="SINISTRADO_PEQUENA_MEDIA")
    dmr = ok(emitir_dmr(api, OPERADOR, v["id"]))
    em_aberto = receber_veiculo(api)
    ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))

    texto = json.dumps(_exportar(api, OPERADOR), ensure_ascii=False)
    for esperado in (
        v["chassi"],
        em_aberto["chassi"],
        cert["numero"],
        dmr["numero"],
        "Eng. Marina Duarte",  # laudo
        "TRANSFERENCIA_SAIDA",  # transferência
        "0.94",  # crédito
        "Porta dianteira esquerda",  # peça
    ):
        assert esperado in texto, esperado


def test_rnf05_historico_completo_exportavel_pelo_fabricante(api, demo) -> None:
    """Art. 22 I: saldos de URV, transferências e consumos."""
    _, cert = gerar_credito(api)
    ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))
    mmv = criar_mmv(api)
    vendidos = chassis(2)
    ok(consumir(api, FISCAL, mmv["id"], vendidos))

    texto = json.dumps(_exportar(api, FISCAL), ensure_ascii=False)
    for esperado in (mmv["codigo"], *vendidos, "TRANSFERENCIA_ENTRADA", "DEBITO"):
        assert esperado in texto, esperado


def test_rf25_exportacao_traz_so_os_dados_da_propria_empresa(api, demo, nova_empresa) -> None:
    outra = nova_empresa("DESMONTADORA", vinculo_com=demo.montadora_id)
    meu, _ = gerar_credito(api, OPERADOR)
    alheio, cert_alheio = gerar_credito(api, outra.email)

    minha = json.dumps(_exportar(api, OPERADOR))
    assert meu["chassi"] in minha
    assert alheio["chassi"] not in minha and cert_alheio["numero"] not in minha
    da_outra = json.dumps(_exportar(api, outra.email))
    assert alheio["chassi"] in da_outra and meu["chassi"] not in da_outra


def test_rf25_exportacao_exige_login(api) -> None:
    erro(api.get("/portabilidade/exportar"), 401)


# --- RNF-04 ---------------------------------------------------------------------------------


def test_rnf04_importacao_rejeita_chassi_ja_creditado(api) -> None:
    """Arts. 28 e 29: a reconciliação impede duplicidade de registro e de crédito."""
    v, _ = gerar_credito(api, tipo="LICENCIADO_RODAGEM")
    arquivo = _exportar(api, OPERADOR)

    resultado = ok(_importar(api, ADMIN, arquivo))
    assert set(resultado) >= {"importados", "rejeitados"}
    rejeitados = json.dumps(resultado["rejeitados"])
    assert "CHASSI_JA_CREDITADO" in rejeitados
    assert v["chassi"] in rejeitados
    # Nada foi creditado de novo.
    assert saldo(api, OPERADOR) == dec("1.00")
    assert len(itens(api.get("/certificados", AUDITOR))) == 1
    assert len(itens(api.get("/urv/creditos", OPERADOR))) == 1


def test_rnf04_importacao_de_arquivo_invalido_e_rejeitada(api) -> None:
    r = _importar(api, ADMIN, {"qualquer": "coisa"})
    erro(r, (400, 422))


@pytest.mark.parametrize("quem", [OPERADOR, FISCAL])
def test_rnf04_importacao_restrita_ao_admin(api, quem) -> None:
    erro(_importar(api, quem, {"versao": "1"}), 403)
