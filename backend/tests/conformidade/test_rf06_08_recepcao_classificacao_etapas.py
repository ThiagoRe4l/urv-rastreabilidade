"""RF-06 (art. 6º I; art. 18 III), RF-07 (art. 2º §§2º a 5º; art. 6º I c) e RF-08 (art. 6º III c)."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FATORES,
    FISCAL,
    OPERADOR,
    PDF,
    PNG,
    anexar,
    dados_veiculo,
    dec,
    emitir_certificado,
    erro,
    itens,
    ok,
    processar_veiculo,
    receber_veiculo,
    registrar_etapa,
)

TIPOS_COM_EVIDENCIA = [t for t in FATORES if t != "SUCATA_INSERVIVEL"]


# --- RF-06 ----------------------------------------------------------------------------------


def test_rf06_recepcao_registra_os_dados_do_veiculo(api, demo) -> None:
    """Anexo III 14.a: chassi, placa, Renavam, data de entrada e classificação."""
    corpo = dados_veiculo(origem_aquisicao="LEILAO_SEGURADORA")
    v = ok(api.post("/veiculos", OPERADOR, json=corpo))
    for campo in (
        "chassi",
        "placa",
        "renavam",
        "data_entrada",
        "origem_aquisicao",
        "documento_entrada_tipo",
        "documento_entrada_numero",
        "certidao_baixa_numero",
        "sem_viabilidade_desmontagem",
    ):
        assert v[campo] == corpo[campo], campo
    assert dec(v["peso_entrada_kg"]) == dec(corpo["peso_entrada_kg"])
    assert v["empresa_id"] == str(demo.desmonte_id)
    assert v["estado"] == "RECEBIDO"
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["chassi"] == corpo["chassi"]


@pytest.mark.parametrize("documento", ["NF_ENTRADA", "AUTO_ARREMATACAO"])
def test_rf06_nota_fiscal_de_entrada_ou_auto_de_arrematacao(api, documento) -> None:
    """Art. 6º I a."""
    v = receber_veiculo(api, documento_entrada_tipo=documento, documento_entrada_numero="2026/000123")
    assert v["documento_entrada_tipo"] == documento
    assert v["documento_entrada_numero"] == "2026/000123"


@pytest.mark.parametrize("origem", ["COMPRA_DIRETA", "LEILAO_ORGAO_PUBLICO", "LEILAO_SEGURADORA"])
def test_rf06_origem_da_aquisicao(api, origem) -> None:
    """Art. 18 I."""
    assert receber_veiculo(api, origem_aquisicao=origem)["origem_aquisicao"] == origem


@pytest.mark.parametrize(
    "campo", ["chassi", "data_entrada", "tipo", "documento_entrada_tipo", "documento_entrada_numero"]
)
def test_rf06_campos_obrigatorios_da_recepcao(api, campo) -> None:
    corpo = dados_veiculo()
    del corpo[campo]
    erro(api.post("/veiculos", OPERADOR, json=corpo), 422)


@pytest.mark.parametrize(
    "alteracao",
    [
        {"chassi": "CURTO"},
        {"documento_entrada_tipo": "RECIBO"},
        {"origem_aquisicao": "DOACAO"},
        {"tipo": "NOVO"},
    ],
    ids=lambda a: next(iter(a)),
)
def test_rf06_valores_invalidos_rejeitados(api, alteracao) -> None:
    erro(api.post("/veiculos", OPERADOR, json=dados_veiculo(**alteracao)), 422)


def test_rf06_recicladora_tambem_recebe_veiculo(api, nova_empresa) -> None:
    recicladora = nova_empresa("RECICLADORA")
    v = receber_veiculo(api, recicladora.email)
    assert v["empresa_id"] == recicladora.id


@pytest.mark.parametrize("quem", [FISCAL, ADMIN])
def test_rf06_somente_desmontadora_ou_recicladora_recebe(api, quem) -> None:
    erro(api.post("/veiculos", quem, json=dados_veiculo()), 403)


def test_rf06_consulta_por_chassi_e_estado(api) -> None:
    a = receber_veiculo(api)
    b = receber_veiculo(api)
    por_chassi = itens(api.get("/veiculos", OPERADOR, params={"chassi": a["chassi"]}))
    assert [v["id"] for v in por_chassi] == [a["id"]]
    recebidos = itens(api.get("/veiculos", OPERADOR, params={"estado": "RECEBIDO"}))
    assert {v["id"] for v in recebidos} == {a["id"], b["id"]}
    assert itens(api.get("/veiculos", OPERADOR, params={"estado": "ENCERRADO"})) == []


# --- RF-07 ----------------------------------------------------------------------------------


@pytest.mark.parametrize("tipo", TIPOS_COM_EVIDENCIA)
def test_rf07_sem_evidencia_o_veiculo_e_sucata_inservivel(api, tipo) -> None:
    """Art. 2º §5º, estendido a todo tipo diferente de sucata inservível (art. 6º I c)."""
    v = receber_veiculo(api, tipo=tipo)
    assert v["tipo"] == "SUCATA_INSERVIVEL"
    assert v["tipo_declarado"] == tipo


@pytest.mark.parametrize("tipo", TIPOS_COM_EVIDENCIA)
def test_rf07_evidencia_de_classificacao_aplica_o_tipo_declarado(api, tipo) -> None:
    v = receber_veiculo(api, tipo=tipo)
    anexo = ok(anexar(api, OPERADOR, v["id"], "EVIDENCIA_CLASSIFICACAO", "RECEPCAO"))
    assert anexo["tipo"] == "EVIDENCIA_CLASSIFICACAO"
    depois = ok(api.get(f"/veiculos/{v['id']}", OPERADOR))
    assert depois["tipo"] == tipo
    assert depois["tipo_declarado"] == tipo


def test_rf07_outros_anexos_nao_valem_como_evidencia_de_classificacao(api) -> None:
    v = receber_veiculo(api, tipo="LICENCIADO_RODAGEM")
    ok(anexar(api, OPERADOR, v["id"], "DOCUMENTO_ENTRADA", "RECEPCAO"))
    ok(anexar(api, OPERADOR, v["id"], "CERTIDAO_BAIXA", "RECEPCAO"))
    ok(anexar(api, OPERADOR, v["id"], "FOTO", "RECEPCAO"))
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["tipo"] == "SUCATA_INSERVIVEL"


def test_rf07_sucata_inservivel_dispensa_evidencia(api) -> None:
    v = receber_veiculo(api, tipo="SUCATA_INSERVIVEL")
    assert v["tipo"] == v["tipo_declarado"] == "SUCATA_INSERVIVEL"


def test_rf07_sem_evidencia_o_certificado_usa_o_fator_de_sucata_inservivel(api) -> None:
    """O fator segue o tipo efetivo, não o declarado: 0,38 em vez de 1,00."""
    v = processar_veiculo(api, tipo="LICENCIADO_RODAGEM", omitir={"evidencia_classificacao"})
    cert = ok(emitir_certificado(api, OPERADOR, v["id"]))
    assert cert["tipo_veiculo"] == "SUCATA_INSERVIVEL"
    assert dec(cert["fator"]) == dec("0.38")
    assert dec(cert["credito"]["quantidade"]) == dec("0.38")


# --- RF-08 ----------------------------------------------------------------------------------


def test_rf08_cada_etapa_registrada_com_foto(api) -> None:
    """Art. 6º III c: recepção, descontaminação, desmontagem e separação dos materiais."""
    v = receber_veiculo(api)
    etapas = ["RECEPCAO", "DESCONTAMINACAO", "DESMONTAGEM", "DESTRUICAO"]
    for etapa in etapas:
        registrada = ok(registrar_etapa(api, OPERADOR, v["id"], etapa))
        assert registrada["tipo"] == etapa
        assert registrada["iniciada_em"] and registrada["concluida_em"]
        foto = ok(anexar(api, OPERADOR, v["id"], "FOTO", etapa))
        assert foto["tipo"] == "FOTO"
        assert foto["etapa_tipo"] == etapa
        assert foto["sha256"] == hashlib.sha256(PNG).hexdigest()

    detalhe = ok(api.get(f"/veiculos/{v['id']}", OPERADOR))
    assert {e["tipo"] for e in detalhe["etapas"]} == set(etapas)
    assert all(e["concluida_em"] for e in detalhe["etapas"])
    assert sorted(a["etapa_tipo"] for a in detalhe["anexos"]) == sorted(etapas)
    assert detalhe["estado"] == "EM_PROCESSO"


def test_rf08_etapa_iniciada_e_depois_concluida(api) -> None:
    v = receber_veiculo(api)
    aberta = ok(registrar_etapa(api, OPERADOR, v["id"], "DESMONTAGEM", concluir=False))
    assert aberta["concluida_em"] is None
    ok(registrar_etapa(api, OPERADOR, v["id"], "DESMONTAGEM"))
    etapas = ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["etapas"]
    assert [e["tipo"] for e in etapas] == ["DESMONTAGEM"]  # (veiculo, tipo) único
    assert etapas[0]["concluida_em"]


def test_rf08_descontaminacao_pode_anteceder_a_recepcao(api) -> None:
    """Art. 18 IV."""
    v = receber_veiculo(api)
    agora = datetime.now(UTC).replace(microsecond=0)
    antes = {
        "iniciada_em": (agora - timedelta(days=3)).isoformat(),
        "concluida_em": (agora - timedelta(days=2)).isoformat(),
    }
    ok(api.put(f"/veiculos/{v['id']}/etapas/DESCONTAMINACAO", OPERADOR, json=antes))
    ok(registrar_etapa(api, OPERADOR, v["id"], "RECEPCAO"))
    etapas = {e["tipo"] for e in ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["etapas"]}
    assert etapas == {"DESCONTAMINACAO", "RECEPCAO"}


def test_rf08_etapa_desconhecida_rejeitada(api) -> None:
    v = receber_veiculo(api)
    erro(registrar_etapa(api, OPERADOR, v["id"], "PINTURA"), 422)


def test_rf08_arquivo_anexado_pode_ser_recuperado(api) -> None:
    v = receber_veiculo(api)
    doc = ok(anexar(api, OPERADOR, v["id"], "DOCUMENTO_ENTRADA", "RECEPCAO"))
    assert doc["sha256"] == hashlib.sha256(PDF).hexdigest()
    for quem in (OPERADOR, AUDITOR):
        r = api.get(f"/anexos/{doc['id']}/arquivo", quem)
        assert r.status_code == 200
        assert r.content == PDF


def test_rf08_so_imagem_e_pdf_sao_aceitos(api) -> None:
    v = receber_veiculo(api)
    r = anexar(
        api,
        OPERADOR,
        v["id"],
        "FOTO",
        "RECEPCAO",
        conteudo=b"MZ\x90\x00",
        nome="foto.exe",
        mime="application/x-msdownload",
    )
    erro(r, (400, 413, 415, 422))
    assert ok(api.get(f"/veiculos/{v['id']}", OPERADOR))["anexos"] == []


def test_rf08_arquivo_acima_de_10_mb_rejeitado(api) -> None:
    v = receber_veiculo(api)
    grande = PNG + b"\0" * (10 * 1024 * 1024 + 1)
    erro(anexar(api, OPERADOR, v["id"], "FOTO", "RECEPCAO", conteudo=grande), (400, 413, 422))
