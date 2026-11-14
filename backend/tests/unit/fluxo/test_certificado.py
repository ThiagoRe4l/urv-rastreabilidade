"""Laudo, pré-condições do certificado e fluxo completo por HTTP. RF-14 a RF-16, RF-21."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core import relogio
from app.models import Certificado, UrvCredito, UrvLancamento, Usuario
from app.modules.documentos import service as documentos
from app.modules.documentos.service import (
    P_CERTIDAO_BAIXA,
    P_CREDENCIAMENTO,
    P_DESCONTAMINACAO,
    P_DESMONTAGEM,
    P_DESTRUICAO,
    P_DOCUMENTO_ENTRADA,
    P_FOTO_DESCONTAMINACAO,
    P_FOTO_DESMONTAGEM,
    P_FOTO_DESTRUICAO,
    P_FOTO_RECEPCAO,
    P_LAUDO,
    P_PECA_NAO_DESCARACTERIZADA,
    P_PESAGEM,
    P_RECEPCAO,
)
from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA
from tests.unit.fluxo.apoio import (
    API,
    CHASSI,
    CNPJ_DESTINATARIO,
    PDF,
    VEICULOS,
    anexar,
    certificado,
    criar_veiculo,
    etapa,
    eventos,
    executar_passos,
    laudo,
    peca,
    pesagem,
)

TODAS_AS_PENDENCIAS = [
    P_RECEPCAO,
    P_DOCUMENTO_ENTRADA,
    P_CERTIDAO_BAIXA,
    P_FOTO_RECEPCAO,
    P_DESCONTAMINACAO,
    P_FOTO_DESCONTAMINACAO,
    P_DESMONTAGEM,
    P_FOTO_DESMONTAGEM,
    P_DESTRUICAO,
    P_PESAGEM,
    P_FOTO_DESTRUICAO,
    P_LAUDO,
]


def _dmr(client, h, veiculo_id, numero="DMR-0001"):
    return client.post(
        f"{VEICULOS}/{veiculo_id}/dmrs",
        json={
            "numero": numero,
            "destinatario_nome": "Recicla Metais Ltda.",
            "destinatario_cnpj": CNPJ_DESTINATARIO,
            "tipo_material": "Sucata ferrosa",
            "peso_kg": "700",
        },
        headers=h,
    )


def _estado(client, h, veiculo_id) -> str:
    return client.get(f"{VEICULOS}/{veiculo_id}", headers=h).json()["estado"]


# --- Laudo (RF-14) ------------------------------------------------------------------------------


def test_laudo_exige_descontaminacao_e_destruicao_concluidas(client, h) -> None:
    v = criar_veiculo(client, h)
    etapa(client, h, v["id"], "DESCONTAMINACAO", fim=None)  # iniciada, não concluída
    r = laudo(client, h, v["id"])
    assert r.status_code == 422
    assert r.json()["codigo"] == "PENDENCIAS_LAUDO"
    assert r.json()["pendencias"] == [P_DESCONTAMINACAO, P_DESTRUICAO]

    etapa(client, h, v["id"], "DESCONTAMINACAO")
    assert laudo(client, h, v["id"]).json()["pendencias"] == [P_DESTRUICAO]


def test_laudo_assinado_uma_unica_vez(client, h, db_session) -> None:
    v = criar_veiculo(client, h)
    etapa(client, h, v["id"], "DESCONTAMINACAO")
    etapa(client, h, v["id"], "DESTRUICAO")
    r = laudo(client, h, v["id"])
    assert r.status_code == 201, r.text
    dados = r.json()
    assert dados["responsavel_registro"] == "CREA-PR 12345"
    assert len(dados["hash_conteudo"]) == 64
    assert dados["assinatura"]["algoritmo"].startswith("SIMULADA")  # lacuna L-07
    assert _estado(client, h, v["id"]) == "LAUDO_EMITIDO"
    assert client.get(f"{VEICULOS}/{v['id']}", headers=h).json()["laudo_id"] == dados["id"]
    assert (
        eventos(db_session, "LAUDO_ASSINADO", dados["id"])[0].payload["hash_conteudo"]
        == dados["hash_conteudo"]
    )

    r = laudo(client, h, v["id"])
    assert r.status_code == 409
    assert r.json()["codigo"] == "LAUDO_JA_EMITIDO"


# --- Pré-condições do certificado (RF-15) -------------------------------------------------------


def test_422_lista_todas_as_pendencias_de_uma_vez(client, h) -> None:
    v = criar_veiculo(client, h)
    r = certificado(client, h, v["id"])
    assert r.status_code == 422
    assert r.json()["codigo"] == "PENDENCIAS_CERTIFICADO"
    assert r.json()["pendencias"] == TODAS_AS_PENDENCIAS
    assert (
        client.get(f"{VEICULOS}/{v['id']}", headers=h).json()["pendencias_certificado"] == TODAS_AS_PENDENCIAS
    )


@pytest.mark.parametrize(
    ("passo_pulado", "pendencias"),
    [
        ("etapa_recepcao", [P_RECEPCAO]),
        ("documento_entrada", [P_DOCUMENTO_ENTRADA]),
        ("certidao_baixa", [P_CERTIDAO_BAIXA]),
        ("foto_recepcao", [P_FOTO_RECEPCAO]),
        # O laudo exige descontaminação e destruição: sem a etapa, ele também fica pendente.
        ("etapa_descontaminacao", [P_DESCONTAMINACAO, P_LAUDO]),
        ("foto_descontaminacao", [P_FOTO_DESCONTAMINACAO]),
        ("etapa_desmontagem", [P_DESMONTAGEM]),
        ("foto_desmontagem", [P_FOTO_DESMONTAGEM]),
        ("etapa_destruicao", [P_DESTRUICAO, P_LAUDO]),
        ("pesagens", [P_PESAGEM]),
        ("foto_destruicao", [P_FOTO_DESTRUICAO]),
        ("laudo", [P_LAUDO]),
    ],
)
def test_cada_pendencia_bloqueia_o_certificado(client, h, db_session, passo_pulado, pendencias) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"], pular=(passo_pulado,))
    r = certificado(client, h, v["id"])
    assert r.status_code == 422, r.text
    assert r.json()["pendencias"] == pendencias
    assert db_session.scalar(select(Certificado.id)) is None


def test_etapa_iniciada_mas_nao_concluida_e_pendencia(client, h) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    etapa(client, h, v["id"], "DESMONTAGEM", fim=None)  # reabre a etapa
    assert certificado(client, h, v["id"]).json()["pendencias"] == [P_DESMONTAGEM]


def test_peca_nao_reutilizavel_sem_descaracterizacao_e_pendencia(client, h) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"], pular=("laudo",))
    p = peca(client, h, v["id"], classificacao="NAO_REUTILIZAVEL", condicao=None, destino="RECICLAGEM").json()
    laudo(client, h, v["id"])
    assert certificado(client, h, v["id"]).json()["pendencias"] == [P_PECA_NAO_DESCARACTERIZADA]

    client.patch(f"{API}/pecas/{p['id']}", json={"descaracterizada": True}, headers=h)
    assert certificado(client, h, v["id"]).status_code == 201


@pytest.mark.parametrize("credenciamento", [{"status": "SUSPENSO"}, {"status": "PENDENTE"}])
def test_empresa_sem_credenciamento_ativo_e_pendencia(client, h, auth, dados_demo, credenciamento) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    r = client.patch(
        f"{API}/empresas/{dados_demo.desmonte_id}/credenciamento",
        json=credenciamento,
        headers=auth(EMAIL_ADMIN),
    )
    assert r.status_code == 200, r.text
    assert certificado(client, h, v["id"]).json()["pendencias"] == [P_CREDENCIAMENTO]


def test_credenciamento_vencido_na_data_da_emissao_e_pendencia(client, h, db_session, dados_demo) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    operador = db_session.get(Usuario, dados_demo.operador_id)
    with pytest.raises(documentos.ErroNegocio) as erro:  # o seed credencia por 2 anos
        documentos.emitir_certificado(
            db_session, operador, uuid.UUID(v["id"]), agora=datetime(2029, 1, 1, tzinfo=UTC)
        )
    assert erro.value.pendencias == [P_CREDENCIAMENTO]


def test_sem_viabilidade_de_desmontagem_dispensa_a_etapa(client, h) -> None:
    v = criar_veiculo(client, h, sem_viabilidade_desmontagem=True)
    executar_passos(client, h, v["id"], pular=("etapa_desmontagem", "foto_desmontagem", "pecas"))
    assert client.get(f"{VEICULOS}/{v['id']}", headers=h).json()["pendencias_certificado"] == []
    assert certificado(client, h, v["id"]).status_code == 201


# --- Emissão (RF-15, RF-16, RF-21) --------------------------------------------------------------


def test_fluxo_completo_por_http_ate_o_certificado(
    client, h, auth, db_session, dados_demo, credito_substituto
) -> None:
    # Recepção (art. 18 III): veículo declarado como sinistrado, ainda sem evidência.
    v = criar_veiculo(client, h)
    vid = v["id"]
    assert (v["estado"], v["tipo"]) == ("RECEBIDO", "SUCATA_INSERVIVEL")
    assert etapa(client, h, vid, "RECEPCAO").status_code == 200
    assert anexar(client, h, vid, "DOCUMENTO_ENTRADA", conteudo=PDF, nome="nf.pdf").status_code == 201
    assert anexar(client, h, vid, "CERTIDAO_BAIXA", conteudo=PDF, nome="baixa.pdf").status_code == 201
    assert anexar(client, h, vid, "FOTO", "RECEPCAO").status_code == 201
    assert (
        anexar(client, h, vid, "EVIDENCIA_CLASSIFICACAO", conteudo=PDF, nome="vistoria.pdf").status_code
        == 201
    )
    assert _estado(client, h, vid) == "RECEBIDO"

    # Descontaminação (IV) e desmontagem com peças (V).
    assert etapa(client, h, vid, "DESCONTAMINACAO").status_code == 200
    assert anexar(client, h, vid, "FOTO", "DESCONTAMINACAO").status_code == 201
    assert _estado(client, h, vid) == "EM_PROCESSO"
    assert etapa(client, h, vid, "DESMONTAGEM").status_code == 200
    assert anexar(client, h, vid, "FOTO", "DESMONTAGEM").status_code == 201
    porta = peca(client, h, vid).json()
    airbag = peca(
        client, h, vid, nome="Airbag", classificacao="NAO_REUTILIZAVEL", condicao=None, destino="DESCARTE"
    ).json()
    assert (
        client.patch(f"{API}/pecas/{airbag['id']}", json={"descaracterizada": True}, headers=h).status_code
        == 200
    )

    # Destruição com separação e pesagem dos materiais (VI).
    assert etapa(client, h, vid, "DESTRUICAO").status_code == 200
    assert pesagem(client, h, vid, "FERROSO", "RECICLAGEM", "700").status_code == 201
    assert pesagem(client, h, vid, "NAO_FERROSO", "REAPROVEITAMENTO", "150").status_code == 201
    assert pesagem(client, h, vid, "NAO_METALICO", "REJEITO", "150").status_code == 201
    assert anexar(client, h, vid, "FOTO", "DESTRUICAO").status_code == 201

    # Laudo (VII).
    detalhe = client.get(f"{VEICULOS}/{vid}", headers=h).json()
    assert detalhe["pendencias_certificado"] == [documentos.P_LAUDO]
    laudo_emitido = laudo(client, h, vid)
    assert laudo_emitido.status_code == 201, laudo_emitido.text
    detalhe = client.get(f"{VEICULOS}/{vid}", headers=h).json()
    assert detalhe["pendencias_certificado"] == []
    assert detalhe["estado"] == "LAUDO_EMITIDO"

    # Certificado (VIII) com o crédito de URV.
    r = certificado(client, h, vid)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["numero"].startswith("CRV-")
    assert c["chassi"] == CHASSI
    assert c["empresa_id"] == str(dados_demo.desmonte_id)
    assert c["tipo_veiculo"] == "SINISTRADO_PEQUENA_MEDIA"
    assert c["fator"] == "0.94"
    assert c["percentual_aproveitado"] == "85.00"
    assert len(c["hash_conteudo"]) == 64
    assert c["credito"]["quantidade"] == "0.94"
    assert c["credito"]["status"] == "DISPONIVEL"
    assert c["credito"]["titular_id"] == str(dados_demo.desmonte_id)

    # `gerar_credito` foi chamado uma vez, com o certificado, na mesma transação.
    assert [cert.id for cert in credito_substituto] == [db_session.scalar(select(Certificado.id))]
    # PM-URV-02: o fluxo informa o autor, e o evento CREDITO_GERADO não fica sem usuário.
    assert [u.email for u in credito_substituto.usuarios] == [EMAIL_DESMONTADORA]
    credito_id = db_session.scalar(select(UrvCredito.id))
    assert eventos(db_session, "CREDITO_GERADO", credito_id)[0].usuario_id is not None
    assert db_session.scalar(select(UrvCredito.quantidade)) == Decimal("0.94")
    assert db_session.scalar(select(UrvLancamento.quantidade)) == Decimal("0.94")
    ev = eventos(db_session, "CERTIFICADO_EMITIDO", c["id"])
    assert len(ev) == 1 and ev[0].payload["fator"] == "0.94"

    detalhe = client.get(f"{VEICULOS}/{vid}", headers=h).json()
    assert detalhe["estado"] == "CERTIFICADO"
    assert detalhe["certificado_id"] == c["id"]
    assert detalhe["pendencias_certificado"] == []

    # Consulta do certificado, com laudo, veículo e crédito.
    completo = client.get(f"{API}/certificados/{c['id']}", headers=h).json()
    assert completo["laudo"]["id"] == laudo_emitido.json()["id"]
    assert completo["veiculo"]["chassi"] == CHASSI
    assert completo["credito"] == c["credito"]
    lista = client.get(f"{API}/certificados", headers=auth(EMAIL_AUDITOR)).json()
    assert [i["id"] for i in lista["itens"]] == [c["id"]]

    # Destinação (IX): concluída e com DMR, o veículo é encerrado.
    assert etapa(client, h, vid, "DESTINACAO").status_code == 200
    assert _estado(client, h, vid) == "CERTIFICADO"  # ainda sem DMR
    assert _dmr(client, h, vid).status_code == 201
    assert _estado(client, h, vid) == "ENCERRADO"
    assert len(eventos(db_session, "VEICULO_ENCERRADO", vid)) == 1

    # A peça em estoque ainda pode ser vendida, e a etiqueta pública acompanha.
    assert (
        client.patch(f"{API}/pecas/{porta['id']}", json={"destino": "REVENDA"}, headers=h).status_code == 200
    )
    assert client.get(f"{API}/pecas/rastreio/{porta['codigo_rastreio']}").json()["destino"] == "REVENDA"

    # A trilha continua íntegra depois do fluxo inteiro.
    assert client.get(f"{API}/auditoria/verificar", headers=auth(EMAIL_AUDITOR)).json()["integra"] is True


def test_sem_evidencia_o_certificado_sai_com_fator_de_sucata_inservivel(client, h) -> None:
    v = criar_veiculo(client, h, tipo="LICENCIADO_RODAGEM")
    executar_passos(client, h, v["id"], pular=("evidencia_classificacao",))
    c = certificado(client, h, v["id"]).json()
    assert c["tipo_veiculo"] == "SUCATA_INSERVIVEL"
    assert c["fator"] == "0.38"


def test_um_chassi_recebe_um_unico_certificado(client, h, db_session) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    assert certificado(client, h, v["id"]).status_code == 201

    r = certificado(client, h, v["id"])
    assert r.status_code == 409  # PM-04: conflito, fora da lista de pendências
    assert r.json()["codigo"] == "CERTIFICADO_JA_EMITIDO"
    assert "pendencias" not in r.json() or not r.json()["pendencias"]
    assert len(db_session.scalars(select(Certificado)).all()) == 1
    assert len(db_session.scalars(select(UrvCredito)).all()) == 1


def test_depois_do_certificado_o_que_ele_atesta_nao_muda(client, h) -> None:
    v = criar_veiculo(client, h, tipo="SUCATA_APROVEITAVEL")
    executar_passos(client, h, v["id"], pular=("evidencia_classificacao",))
    assert certificado(client, h, v["id"]).status_code == 201

    # RF-07: o tipo não muda mais, mesmo com a evidência chegando depois.
    r = anexar(client, h, v["id"], "EVIDENCIA_CLASSIFICACAO", conteudo=PDF, nome="tarde.pdf")
    assert r.status_code == 409
    assert r.json()["codigo"] == "TIPO_IMUTAVEL_APOS_CERTIFICADO"
    detalhe = client.get(f"{VEICULOS}/{v['id']}", headers=h).json()
    assert (detalhe["tipo"], detalhe["tipo_declarado"]) == ("SUCATA_INSERVIVEL", "SUCATA_APROVEITAVEL")

    bloqueadas = [
        pesagem(client, h, v["id"]),
        peca(client, h, v["id"]),
        etapa(client, h, v["id"], "DESTRUICAO"),
        etapa(client, h, v["id"], "RECEPCAO"),
    ]
    for r in bloqueadas:
        assert r.status_code == 409
        assert r.json()["codigo"] == "VEICULO_CERTIFICADO"
    # Fotos e a etapa de destinação continuam aceitas.
    assert anexar(client, h, v["id"], "FOTO", "DESTINACAO").status_code == 201
    assert etapa(client, h, v["id"], "DESTINACAO", fim=None).status_code == 200


def test_destinacao_concluida_antes_do_certificado_encerra_na_emissao(client, h) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    etapa(client, h, v["id"], "DESTINACAO")
    _dmr(client, h, v["id"])
    assert _estado(client, h, v["id"]) == "LAUDO_EMITIDO"
    assert certificado(client, h, v["id"]).status_code == 201
    assert _estado(client, h, v["id"]) == "ENCERRADO"


def test_abaixo_da_meta_e_alerta_e_nao_bloqueio(client, h, db_session, dados_demo) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])  # 700 kg reciclados, 300 kg de rejeito: 70%
    operador = db_session.get(Usuario, dados_demo.operador_id)
    cert, _ = documentos.emitir_certificado(
        db_session, operador, uuid.UUID(v["id"]), agora=datetime(2027, 3, 1, tzinfo=UTC)
    )
    assert cert.percentual_aproveitado == Decimal("70.00")
    assert cert.meta_ano == Decimal("80.00")
    assert cert.atende_meta is False


def test_em_2026_nao_ha_meta_so_registro(client, h, db_session, dados_demo) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    operador = db_session.get(Usuario, dados_demo.operador_id)
    cert, _ = documentos.emitir_certificado(
        db_session, operador, uuid.UUID(v["id"]), agora=datetime(2026, 12, 1, tzinfo=UTC)
    )
    assert cert.percentual_aproveitado == Decimal("70.00")
    assert cert.meta_ano is None and cert.atende_meta is None


def test_certificados_filtrados_por_empresa(client, h, h_outra, auth, dados_demo) -> None:
    a = criar_veiculo(client, h)
    executar_passos(client, h, a["id"])
    ca = certificado(client, h, a["id"]).json()
    b = criar_veiculo(client, h_outra, chassi="8AFZZZ54ABJ123456")
    executar_passos(client, h_outra, b["id"])
    cb = certificado(client, h_outra, b["id"]).json()

    url = f"{API}/certificados"
    assert [c["id"] for c in client.get(url, headers=h).json()["itens"]] == [ca["id"]]
    assert [c["id"] for c in client.get(url, headers=h_outra).json()["itens"]] == [cb["id"]]
    assert client.get(url, headers=auth(EMAIL_AUDITOR)).json()["total"] == 2
    filtrado = client.get(
        url, params={"empresa_id": str(dados_demo.desmonte_id)}, headers=auth(EMAIL_AUDITOR)
    )
    assert [c["id"] for c in filtrado.json()["itens"]] == [ca["id"]]
    # O filtro não fura o isolamento: a empresa só enxerga os próprios certificados.
    alheio = client.get(url, params={"empresa_id": str(dados_demo.desmonte_id)}, headers=h_outra)
    assert alheio.json()["total"] == 0
    assert client.get(f"{url}/{ca['id']}", headers=h_outra).status_code == 404
    assert client.get(f"{url}/{ca['id']}", headers=auth(EMAIL_ADMIN)).status_code == 200


def test_laudo_pode_ser_lido_antes_do_certificado(client, h, h_outra, auth) -> None:
    """PM-WEB-03, RF-14 e RF-23: GET /veiculos/{id}/laudo."""
    v = criar_veiculo(client, h)
    r = client.get(f"{VEICULOS}/{v['id']}/laudo", headers=h)
    assert (r.status_code, r.json()["codigo"]) == (404, "NAO_ENCONTRADO")

    etapa(client, h, v["id"], "DESCONTAMINACAO")
    etapa(client, h, v["id"], "DESTRUICAO")
    assinado = laudo(client, h, v["id"]).json()
    for cabecalho in (h, auth(EMAIL_AUDITOR), auth(EMAIL_ADMIN)):
        r = client.get(f"{VEICULOS}/{v['id']}/laudo", headers=cabecalho)
        assert r.status_code == 200, r.text
        assert r.json() == assinado
    # Outra empresa não descobre que o veículo existe.
    assert client.get(f"{VEICULOS}/{v['id']}/laudo", headers=h_outra).status_code == 404
    assert client.get(f"{VEICULOS}/{uuid.uuid4()}/laudo", headers=h).status_code == 404


def test_certificado_usa_a_data_de_brasilia(client, h) -> None:
    """PM-URV-06: às 22h de 31/12/2026 em Brasília já é 2027 em UTC, mas a emissão é de 2026.

    Em 2026 não há meta (art. 18 §7º); em 2027 a meta é de 80%. O número leva o ano da emissão.
    """
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    client.app.dependency_overrides[relogio.agora] = lambda: datetime(2027, 1, 1, 1, 0, tzinfo=UTC)
    try:
        c = certificado(client, h, v["id"])
    finally:
        client.app.dependency_overrides.pop(relogio.agora)
    assert c.status_code == 201, c.text
    assert c.json()["meta_ano"] is None
    assert c.json()["numero"].startswith("CRV-2026-")
