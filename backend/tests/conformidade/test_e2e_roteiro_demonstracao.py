"""Ponta a ponta: o roteiro de demonstração de `docs/04-plano-de-execucao.md`, passo a passo."""

from scripts.seed import CNPJ_DESMONTE
from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FISCAL,
    OPERADOR,
    adulterar,
    anexar,
    assinar_laudo,
    chassis,
    consumir,
    criar_peca,
    dados_veiculo,
    dec,
    emitir_certificado,
    emitir_dmr,
    erro,
    itens,
    ok,
    pesar,
    registrar_etapa,
    saldo,
    transferir,
)


def test_e2e_roteiro_de_demonstracao(api, demo, db_session) -> None:
    # 1. O administrador mostra a desmontadora credenciada, o fabricante e o vínculo.
    empresas = {e["id"]: e for e in itens(api.get("/empresas", ADMIN))}
    assert empresas[str(demo.desmonte_id)]["credenciamento_status"] == "ATIVO"
    assert empresas[str(demo.montadora_id)]["registro_compromissos"] is True
    vinculo = itens(api.get("/vinculos", ADMIN))[0]
    assert (vinculo["geradora_id"], vinculo["fabricante_id"], vinculo["ativo"]) == (
        str(demo.desmonte_id),
        str(demo.montadora_id),
        True,
    )

    # 2. O fabricante cadastra um MMV com nível e percentual de reciclabilidade.
    mmv = ok(
        api.post(
            "/mmvs",
            FISCAL,
            json={
                "codigo": "SEDAN-16-AT-2027",
                "ncm": "87032310",
                "nivel": 1,
                "percentual_reciclabilidade": "88.00",
                "ja_comercializado": False,
            },
        )
    )
    assert dec(mmv["rm"]) == 10

    # 3. A desmontadora recebe um veículo, anexa nota fiscal, certidão de baixa e fotos, e classifica.
    recepcao = dados_veiculo(tipo="SINISTRADO_PEQUENA_MEDIA", origem_aquisicao="LEILAO_SEGURADORA")
    v = ok(api.post("/veiculos", OPERADOR, json=recepcao))
    vid = v["id"]
    assert v["tipo"] == "SUCATA_INSERVIVEL"  # ainda sem evidência da classificação
    ok(anexar(api, OPERADOR, vid, "DOCUMENTO_ENTRADA", "RECEPCAO"))
    ok(anexar(api, OPERADOR, vid, "CERTIDAO_BAIXA", "RECEPCAO"))
    ok(anexar(api, OPERADOR, vid, "FOTO", "RECEPCAO"))
    ok(anexar(api, OPERADOR, vid, "EVIDENCIA_CLASSIFICACAO", "RECEPCAO"))
    ok(registrar_etapa(api, OPERADOR, vid, "RECEPCAO"))
    assert ok(api.get(f"/veiculos/{vid}", OPERADOR))["tipo"] == "SINISTRADO_PEQUENA_MEDIA"

    # 4. Descontaminação, desmontagem com peças etiquetadas, pesos por material e a DMR.
    ok(registrar_etapa(api, OPERADOR, vid, "DESCONTAMINACAO"))
    ok(anexar(api, OPERADOR, vid, "FOTO", "DESCONTAMINACAO"))
    ok(registrar_etapa(api, OPERADOR, vid, "DESMONTAGEM"))
    ok(anexar(api, OPERADOR, vid, "FOTO", "DESMONTAGEM"))
    motor = criar_peca(api, OPERADOR, vid, nome="Motor 1.6", destino="REVENDA")
    etiqueta = ok(api.get(f"/pecas/rastreio/{motor['codigo_rastreio']}"))  # leitura pública do QR Code
    etiqueta = etiqueta.get("etiqueta", etiqueta)
    assert etiqueta["chassi"] == recepcao["chassi"]
    assert "".join(c for c in etiqueta["cnpj"] if c.isdigit()) == CNPJ_DESMONTE
    airbag = criar_peca(
        api, OPERADOR, vid, nome="Airbag", classificacao="NAO_REUTILIZAVEL", destino="DESCARTE"
    )
    ok(api.patch(f"/pecas/{airbag['id']}", OPERADOR, json={"descaracterizada": True}))
    ok(registrar_etapa(api, OPERADOR, vid, "DESTRUICAO"))
    ok(anexar(api, OPERADOR, vid, "FOTO", "DESTRUICAO"))
    for fracao, destino, peso in (
        ("FERROSO", "RECICLAGEM", "780.000"),
        ("NAO_FERROSO", "RECICLAGEM", "95.000"),
        ("NAO_METALICO", "RECUPERACAO_ENERGETICA", "60.000"),
        ("NAO_METALICO", "REJEITO", "65.000"),
    ):
        ok(pesar(api, OPERADOR, vid, fracao, destino, peso))
    dmr = ok(emitir_dmr(api, OPERADOR, vid, tipo_material="Sucata ferrosa", peso_kg="780.000"))
    assert dmr["mtr_numero"]

    # 5. O responsável técnico assina o laudo; o certificado é emitido e o crédito entra no saldo.
    erro(emitir_certificado(api, OPERADOR, vid), 422, "PENDENCIAS_CERTIFICADO")  # falta o laudo
    ok(assinar_laudo(api, OPERADOR, vid))
    assert ok(api.get(f"/veiculos/{vid}", OPERADOR))["pendencias_certificado"] == []
    cert = ok(emitir_certificado(api, OPERADOR, vid))
    assert cert["tipo_veiculo"] == "SINISTRADO_PEQUENA_MEDIA"
    assert dec(cert["fator"]) == dec("0.94")
    assert dec(cert["percentual_aproveitado"]) == dec("93.5")
    assert saldo(api, OPERADOR) == dec("0.94")
    ok(registrar_etapa(api, OPERADOR, vid, "DESTINACAO"))
    assert ok(api.get(f"/veiculos/{vid}", OPERADOR))["estado"] == "ENCERRADO"

    # 6. A desmontadora transfere o crédito ao fabricante.
    credito = ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))
    assert credito["status"] == "TRANSFERIDO"
    assert saldo(api, OPERADOR) == 0
    assert saldo(api, FISCAL) == dec("0.94")

    # 7. O fabricante indica os chassis vendidos; o sistema calcula o débito e baixa o saldo.
    vendidos = chassis(6)
    consumo = ok(consumir(api, FISCAL, mmv["id"], vendidos, preco_medio="165000.00"))
    assert dec(consumo["urv_debito"]) == dec("0.66")  # (6 / 10) × (165.000 / 150.000)
    assert dec(consumo["saldo_apos"]) == dec("0.28")
    assert saldo(api, FISCAL) == dec("0.28")

    # 8. O auditor busca o chassi, vê a linha do tempo inteira e verifica a cadeia de hashes.
    achado = itens(api.get("/veiculos", AUDITOR, params={"chassi": recepcao["chassi"]}))
    assert [x["id"] for x in achado] == [vid]
    linha = ok(api.get(f"/veiculos/{vid}", AUDITOR))
    assert {e["tipo"] for e in linha["etapas"]} == {
        "RECEPCAO",
        "DESCONTAMINACAO",
        "DESMONTAGEM",
        "DESTRUICAO",
        "DESTINACAO",
    }
    assert len(linha["anexos"]) == 7
    assert ok(api.get(f"/certificados/{cert['id']}", AUDITOR))["laudo"]
    eventos = ok(api.get("/auditoria/eventos", AUDITOR, params={"entidade_id": vid, "tamanho": 100}))
    assert eventos["total"] >= 1
    relatorio = ok(api.get("/relatorios/mdic", AUDITOR))
    assert relatorio["certificados_emitidos"] == 1
    assert dec(relatorio["urv_gerada"]) == dec("0.94")
    assert dec(relatorio["urv_consumida"]) == dec("0.66")
    verificacao = ok(api.get("/auditoria/verificar", AUDITOR))
    assert verificacao["integra"] is True

    # 9. Duas tentativas barradas: o mesmo chassi de novo, e um evento adulterado.
    erro(api.post("/veiculos", OPERADOR, json=recepcao), 409, "CHASSI_DUPLICADO")
    erro(consumir(api, FISCAL, mmv["id"], vendidos[:1]), 409, "CHASSI_JA_CONSUMIDO")
    alvo = eventos["itens"][0]["sequencia"]
    adulterar(db_session, alvo)
    quebrada = ok(api.get("/auditoria/verificar", AUDITOR))
    assert quebrada["integra"] is False
    assert quebrada["primeira_quebra"] == alvo
