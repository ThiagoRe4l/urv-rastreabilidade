"""RF-14 (art. 18 VII), RF-15 (art. 18 VIII; art. 8º I) e RF-16 (art. 3º §§1º e 2º; art. 18 §3º)."""

import re

import pytest

from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FATORES,
    FISCAL,
    OPERADOR,
    assinar_laudo,
    dec,
    emitir_certificado,
    erro,
    gerar_credito,
    itens,
    ok,
    processar_veiculo,
    receber_veiculo,
    saldo,
)

HEX64 = re.compile(r"[0-9a-f]{64}")


# --- RF-14 ----------------------------------------------------------------------------------


def test_rf14_laudo_assinado_pelo_responsavel_tecnico(api) -> None:
    v = processar_veiculo(api, omitir={"laudo"})
    laudo = ok(assinar_laudo(api, OPERADOR, v["id"]))
    assert laudo["responsavel_nome"] == "Eng. Marina Duarte"
    assert laudo["responsavel_registro"] == "CREA-PR 123456"
    assert laudo["assinado_em"]
    assert HEX64.fullmatch(laudo["hash_conteudo"])
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["estado"] == "LAUDO_EMITIDO"


@pytest.mark.parametrize("etapa", ["etapa_descontaminacao", "etapa_destruicao"])
def test_rf14_laudo_atesta_etapas_ja_executadas(api, etapa) -> None:
    """O laudo atesta descontaminação e destruição: sem a etapa concluída, não há o que atestar."""
    v = processar_veiculo(api, omitir={etapa, "laudo"})
    erro(assinar_laudo(api, OPERADOR, v["id"]), (409, 422))
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["estado"] != "LAUDO_EMITIDO"


@pytest.mark.parametrize("campo", ["responsavel_nome", "responsavel_registro"])
def test_rf14_laudo_exige_identificacao_do_responsavel(api, campo) -> None:
    v = processar_veiculo(api, omitir={"laudo"})
    corpo = {"responsavel_nome": "Eng. Marina Duarte", "responsavel_registro": "CREA-PR 123456"}
    del corpo[campo]
    erro(api.post(f"/veiculos/{v['id']}/laudo", OPERADOR, json=corpo), 422)


def test_rf14_um_laudo_por_veiculo(api) -> None:
    v = processar_veiculo(api)
    erro(assinar_laudo(api, OPERADOR, v["id"]), (409, 422))


@pytest.mark.parametrize("quem", [FISCAL, ADMIN])
def test_rf14_laudo_emitido_so_pela_empresa_do_veiculo(api, quem) -> None:
    """Art. 18 VII: emitido por empresa de desmontagem ou reciclagem credenciada."""
    v = processar_veiculo(api, omitir={"laudo"})
    erro(assinar_laudo(api, quem, v["id"]), (403, 404))


# --- RF-15 ----------------------------------------------------------------------------------


def test_rf15_certificado_emitido_com_etapas_e_evidencias_completas(api, demo) -> None:
    v = processar_veiculo(api)
    assert v["pendencias_certificado"] == []
    cert = ok(emitir_certificado(api, OPERADOR, v["id"]))
    assert cert["numero"]
    assert cert["veiculo_id"] == v["id"]
    assert cert["empresa_id"] == str(demo.desmonte_id)
    assert cert["emitido_em"]
    assert HEX64.fullmatch(cert["hash_conteudo"])
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["estado"] == "CERTIFICADO"


def test_rf15_veiculo_recem_recebido_lista_as_pendencias(api) -> None:
    v = receber_veiculo(api)
    pendencias = ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["pendencias_certificado"]
    assert len(pendencias) >= 6  # recepção, descontaminação, desmontagem, destruição, pesagem e laudo
    assert all(isinstance(p, str) and p for p in pendencias)


def test_rf15_certificado_bloqueado_devolve_as_pendencias(api) -> None:
    v = receber_veiculo(api)
    corpo = erro(emitir_certificado(api, OPERADOR, v["id"]), 422, "PENDENCIAS_CERTIFICADO")
    assert corpo["pendencias"] == ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["pendencias_certificado"]
    assert itens(api.get("/certificados", OPERADOR)) == []
    assert saldo(api, OPERADOR) == 0


def test_rf15_pendencias_diminuem_a_cada_etapa(api) -> None:
    sem_nada = receber_veiculo(api)
    antes = ok(api.get(f"/veiculos/{sem_nada['id']}", OPERADOR))["pendencias_certificado"]
    quase = processar_veiculo(api, omitir={"laudo"})
    assert 1 <= len(quase["pendencias_certificado"]) < len(antes)


def test_rf15_veiculo_sem_viabilidade_dispensa_a_desmontagem(api) -> None:
    """Anexo III 11: direto à trituração."""
    v = processar_veiculo(api, sem_viabilidade_desmontagem=True)
    assert "DESMONTAGEM" not in {e["tipo"] for e in v["etapas"]}
    ok(emitir_certificado(api, OPERADOR, v["id"]))


def test_rf15_certificado_acompanha_laudo_veiculo_e_credito(api) -> None:
    """Art. 18 VIII: documento eletrônico acompanhado do Laudo de Reciclagem."""
    v, cert = gerar_credito(api)
    completo = ok(api.get(f"/certificados/{cert['id']}", OPERADOR))
    assert completo["numero"] == cert["numero"]
    assert completo["laudo"]["responsavel_nome"] == "Eng. Marina Duarte"
    assert completo["veiculo"]["chassi"] == v["chassi"]
    assert completo["credito"]["id"] == cert["credito"]["id"]
    assert [c["id"] for c in itens(api.get("/certificados", OPERADOR))] == [cert["id"]]


def test_rf15_numero_do_certificado_e_unico(api) -> None:
    numeros = {gerar_credito(api)[1]["numero"] for _ in range(3)}
    assert len(numeros) == 3


@pytest.mark.parametrize("quem", [FISCAL, ADMIN])
def test_rf15_certificado_emitido_so_pela_empresa_do_veiculo(api, quem) -> None:
    """Art. 8º I: crédito gerado exclusivamente pela desmontadora ou recicladora."""
    v = processar_veiculo(api)
    erro(emitir_certificado(api, quem, v["id"]), (403, 404))
    assert itens(api.get("/certificados", AUDITOR)) == []


# --- RF-16 ----------------------------------------------------------------------------------


def test_rf16_fatores_de_equivalencia_da_portaria(api) -> None:
    """Art. 3º §2º e §5º."""
    corpo = ok(api.get("/configuracao/fatores", OPERADOR))
    assert {f["tipo"]: dec(f["fator"]) for f in corpo["itens"]} == FATORES
    assert all(isinstance(f["fator"], str) for f in corpo["itens"])
    assert dec(corpo["preco_base"]) == dec("150000.00")


@pytest.mark.parametrize(("tipo", "fator"), FATORES.items())
def test_rf16_credito_no_valor_do_fator_do_veiculo(api, tipo, fator) -> None:
    """Art. 3º §1º: URV = Σ Qi × Feqi; um veículo gera o seu fator."""
    _, cert = gerar_credito(api, tipo=tipo)
    assert cert["tipo_veiculo"] == tipo
    assert dec(cert["fator"]) == fator
    credito = cert["credito"]
    assert dec(credito["quantidade"]) == fator
    assert credito["status"] == "DISPONIVEL"
    assert isinstance(cert["fator"], str) and isinstance(credito["quantidade"], str)
    assert saldo(api, OPERADOR) == fator


def test_rf16_titular_do_credito_e_quem_emite_o_certificado(api, demo) -> None:
    _, cert = gerar_credito(api)
    assert cert["credito"]["geradora_id"] == str(demo.desmonte_id)
    assert cert["credito"]["titular_id"] == str(demo.desmonte_id)


def test_rf16_saldo_e_a_soma_dos_creditos(api) -> None:
    """Σ Qi × Feqi com tipos diferentes: 1,00 + 0,94 + 0,38."""
    assert saldo(api, OPERADOR) == 0
    for tipo in ("LICENCIADO_RODAGEM", "SINISTRADO_PEQUENA_MEDIA", "SUCATA_INSERVIVEL"):
        gerar_credito(api, tipo=tipo)
    assert saldo(api, OPERADOR) == dec("2.32")
    lancamentos = itens(api.get("/urv/extrato", OPERADOR))
    assert {lanc["tipo"] for lanc in lancamentos} == {"CREDITO"}
    assert sorted(dec(lanc["quantidade"]) for lanc in lancamentos) == [dec("0.38"), dec("0.94"), dec("1.00")]


def test_rf16_credito_listado_com_certificado_e_chassi(api) -> None:
    v, cert = gerar_credito(api)
    creditos = itens(api.get("/urv/creditos", OPERADOR, params={"status": "DISPONIVEL"}))
    assert [c["id"] for c in creditos] == [cert["credito"]["id"]]
    texto = str(creditos[0])
    assert v["chassi"] in texto and cert["numero"] in texto
    assert itens(api.get("/urv/creditos", OPERADOR, params={"status": "TRANSFERIDO"})) == []
