"""Recepção, classificação, etapas, anexos e isolamento entre empresas. RF-06 a RF-08, RF-21."""

import hashlib

import pytest

from app.core.config import get_settings
from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_FABRICANTE
from tests.unit.fluxo.apoio import (
    API,
    CHASSI,
    JPEG,
    PDF,
    PNG,
    VEICULOS,
    anexar,
    certificado,
    criar_veiculo,
    dados_veiculo,
    etapa,
    eventos,
    executar_passos,
    peca,
)

# --- Recepção e classificação (RF-06, RF-07) --------------------------------------------------


def test_recepcao_grava_veiculo_e_evento(client, h, dados_demo, db_session) -> None:
    v = criar_veiculo(client, h, chassi="9bwzzz377vt004251")
    assert v["chassi"] == CHASSI  # gravado em maiúsculas
    assert v["empresa_id"] == str(dados_demo.desmonte_id)
    assert v["estado"] == "RECEBIDO"
    assert v["peso_entrada_kg"] == "1180.500"  # Decimal trafega como string

    ev = eventos(db_session, "VEICULO_RECEBIDO", v["id"])
    assert len(ev) == 1
    assert ev[0].payload["chassi"] == CHASSI
    assert ev[0].empresa_id == dados_demo.desmonte_id


@pytest.mark.parametrize(
    "tipo",
    [
        "LICENCIADO_RODAGEM",
        "SINISTRADO_PEQUENA_MEDIA",
        "SUCATA_APROVEITAVEL",
        "SINISTRADO_GRANDE",
        "SUCATA_MOTOR_INSERVIVEL",
    ],
)
def test_sem_evidencia_o_veiculo_e_rebaixado_para_sucata_inservivel(client, h, tipo) -> None:
    v = criar_veiculo(client, h, tipo=tipo)
    assert v["tipo"] == "SUCATA_INSERVIVEL"
    assert v["tipo_declarado"] == tipo
    assert v["rebaixado"] is True


def test_sucata_inservivel_nao_e_rebaixamento(client, h) -> None:
    v = criar_veiculo(client, h, tipo="SUCATA_INSERVIVEL")
    assert v["tipo"] == v["tipo_declarado"] == "SUCATA_INSERVIVEL"
    assert v["rebaixado"] is False


def test_evidencia_de_classificacao_aplica_o_tipo_declarado(client, h, db_session) -> None:
    v = criar_veiculo(client, h, tipo="LICENCIADO_RODAGEM")
    # Outros anexos não mexem no tipo.
    assert anexar(client, h, v["id"], "FOTO", "RECEPCAO").status_code == 201
    assert client.get(f"{VEICULOS}/{v['id']}", headers=h).json()["tipo"] == "SUCATA_INSERVIVEL"

    r = anexar(client, h, v["id"], "EVIDENCIA_CLASSIFICACAO", conteudo=PDF, nome="crlv.pdf")
    assert r.status_code == 201, r.text
    assert r.json()["etapa_tipo"] == "RECEPCAO"

    detalhe = client.get(f"{VEICULOS}/{v['id']}", headers=h).json()
    assert detalhe["tipo"] == "LICENCIADO_RODAGEM"
    assert detalhe["rebaixado"] is False
    ev = eventos(db_session, "VEICULO_CLASSIFICADO", v["id"])
    assert ev[0].payload["tipo"] == {"antes": "SUCATA_INSERVIVEL", "depois": "LICENCIADO_RODAGEM"}


def test_chassi_duplicado(client, h, h_outra) -> None:
    criar_veiculo(client, h)
    for headers, chassi in ((h, CHASSI), (h, CHASSI.lower()), (h_outra, CHASSI)):
        r = client.post(VEICULOS, json=dados_veiculo(chassi=chassi, placa="XYZ9A88"), headers=headers)
        assert r.status_code == 409
        assert r.json()["codigo"] == "CHASSI_DUPLICADO"


def test_renavam_e_certidao_de_baixa_sao_de_um_veiculo_so(client, h, h_outra) -> None:
    """RF-06 e RF-21, art. 18 II; art. 21 III: dois chassis não dividem a identidade (A7 da revisão)."""
    v = criar_veiculo(client, h)
    for headers in (h, h_outra):
        for campo, codigo in (
            ("renavam", "RENAVAM_DUPLICADO"),
            ("certidao_baixa_numero", "CERTIDAO_BAIXA_DUPLICADA"),
        ):
            corpo = dados_veiculo(chassi="9BWZZZ377VT009999", **{campo: v[campo]})
            r = client.post(VEICULOS, json=corpo, headers=headers)
            assert (r.status_code, r.json()["codigo"]) == (409, codigo)


def test_evidencia_de_classificacao_nao_serve_a_dois_veiculos(client, h, pasta_uploads) -> None:
    """RF-07, RNF-07, art. 21 III: o mesmo arquivo como evidência de outro chassi é recusado (A7)."""
    evidencia = PDF + b"%vistoria-unica\n"
    a = criar_veiculo(client, h)
    b = criar_veiculo(client, h, chassi="9BWZZZ377VT009999")
    assert (
        anexar(client, h, a["id"], "EVIDENCIA_CLASSIFICACAO", conteudo=evidencia, nome="v.pdf").status_code
        == 201
    )
    # No mesmo veículo, reenviar o arquivo é permitido.
    assert (
        anexar(client, h, a["id"], "EVIDENCIA_CLASSIFICACAO", conteudo=evidencia, nome="v.pdf").status_code
        == 201
    )
    r = anexar(client, h, b["id"], "EVIDENCIA_CLASSIFICACAO", conteudo=evidencia, nome="v.pdf")
    assert (r.status_code, r.json()["codigo"]) == (409, "EVIDENCIA_REUTILIZADA")
    assert client.get(f"{VEICULOS}/{b['id']}", headers=h).json()["tipo"] == "SUCATA_INSERVIVEL"
    assert len(list(pasta_uploads.rglob("*.pdf"))) == 2  # o recusado não fica em disco


@pytest.mark.parametrize(
    "mudanca",
    [
        {"chassi": "abc"},
        {"chassi": "9BWZZZ377VT0042510"},  # 18 caracteres (A7: chassi é VIN)
        {"chassi": "9BWZZZ377VT00425"},  # 16
        {"chassi": "9BWZZZ377VT00425I"},  # VIN não tem I, O nem Q
        {"chassi": "ABC123"},
        {"placa": "AB"},
        {"renavam": "12ab"},
        {"data_entrada": "2999-01-01"},
        {"peso_entrada_kg": "0"},
        {"peso_entrada_kg": "-5"},
        {"tipo": "CARRO_VOADOR"},
        {"origem_aquisicao": "DOACAO"},
        {"certidao_baixa_numero": "  "},
    ],
)
def test_entrada_invalida(client, h, mudanca) -> None:
    r = client.post(VEICULOS, json=dados_veiculo(**mudanca), headers=h)
    assert r.status_code == 422
    assert r.json()["codigo"] == "ENTRADA_INVALIDA"


def test_listagem_com_filtros(client, h) -> None:
    a = criar_veiculo(client, h)
    b = criar_veiculo(client, h, chassi="8AFZZZ54ABJ123456", placa="QWE4R56")
    etapa(client, h, b["id"], "DESCONTAMINACAO")

    r = client.get(VEICULOS, headers=h)
    assert r.json()["total"] == 2
    r = client.get(VEICULOS, params={"chassi": "zzz377"}, headers=h)
    assert [v["id"] for v in r.json()["itens"]] == [a["id"]]
    r = client.get(VEICULOS, params={"estado": "EM_PROCESSO"}, headers=h)
    assert [v["id"] for v in r.json()["itens"]] == [b["id"]]


# --- Papéis e isolamento ------------------------------------------------------------------------


def test_uma_desmontadora_nao_le_nem_altera_veiculo_de_outra(client, h, h_outra) -> None:
    v = criar_veiculo(client, h)
    anexo = anexar(client, h, v["id"], "FOTO", "RECEPCAO").json()
    p = peca(client, h, v["id"]).json()
    url = f"{VEICULOS}/{v['id']}"

    assert client.get(VEICULOS, headers=h_outra).json() == {"itens": [], "total": 0}
    assert client.get(f"{API}/pecas", headers=h_outra).json()["total"] == 0
    assert client.get(f"{API}/certificados", headers=h_outra).json()["total"] == 0

    leituras = [url, f"{url}/pesagens", f"{url}/dmrs", f"{API}/anexos/{anexo['id']}/arquivo"]
    for caminho in leituras:
        r = client.get(caminho, headers=h_outra)
        assert r.status_code == 404, caminho
        assert r.json()["codigo"] == "NAO_ENCONTRADO"

    escritas = [
        client.put(f"{url}/etapas/RECEPCAO", json={"iniciada_em": "2026-11-10T08:00:00Z"}, headers=h_outra),
        anexar(client, h_outra, v["id"], "FOTO", "RECEPCAO"),
        peca(client, h_outra, v["id"]),
        client.patch(f"{API}/pecas/{p['id']}", json={"destino": "REVENDA"}, headers=h_outra),
        client.post(
            f"{url}/pesagens",
            json={"fracao": "FERROSO", "destino": "RECICLAGEM", "peso_kg": "1"},
            headers=h_outra,
        ),
        client.post(
            f"{url}/laudo", json={"responsavel_nome": "Fulano", "responsavel_registro": "1"}, headers=h_outra
        ),
        client.post(f"{url}/certificado", headers=h_outra),
    ]
    assert [r.status_code for r in escritas] == [404] * len(escritas)

    # A dona continua vendo o veículo intacto.
    detalhe = client.get(url, headers=h).json()
    assert detalhe["etapas"] == []
    assert len(detalhe["anexos"]) == 1


def test_auditor_e_admin_leem_tudo_e_nao_escrevem(client, h, h_outra, auth) -> None:
    a = criar_veiculo(client, h)
    b = criar_veiculo(client, h_outra, chassi="8AFZZZ54ABJ123456")
    for email, codigo in ((EMAIL_AUDITOR, "AUDITOR_SOMENTE_LEITURA"), (EMAIL_ADMIN, "PAPEL_NAO_PERMITIDO")):
        ids = {v["id"] for v in client.get(VEICULOS, headers=auth(email)).json()["itens"]}
        assert ids == {a["id"], b["id"]}
        assert client.get(f"{VEICULOS}/{b['id']}", headers=auth(email)).status_code == 200

        r = client.post(VEICULOS, json=dados_veiculo(chassi="XXXXXXXX1"), headers=auth(email))
        assert r.status_code == 403
        assert r.json()["codigo"] == codigo
        assert etapa(client, auth(email), a["id"], "RECEPCAO").status_code == 403


def test_fabricante_fica_fora_do_fluxo(client, h, auth) -> None:
    v = criar_veiculo(client, h)
    fab = auth(EMAIL_FABRICANTE)
    assert client.get(VEICULOS, headers=fab).status_code == 403
    assert client.get(f"{VEICULOS}/{v['id']}/pesagens", headers=fab).status_code == 403
    # O dossiê só é do titular de um crédito do veículo (A8): sem ele, 404, sem revelar que existe.
    assert client.get(f"{VEICULOS}/{v['id']}", headers=fab).status_code == 404
    assert client.post(VEICULOS, json=dados_veiculo(chassi="XXXXXXXX1"), headers=fab).status_code == 403


def test_fabricante_titular_le_o_dossie(client, h, auth, dados_demo) -> None:
    """RF-23, art. 9º: o titular do crédito lê certificado, laudo, anexos e DMRs (A8 da revisão)."""
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    cert = certificado(client, h, v["id"]).json()
    fab = auth(EMAIL_FABRICANTE)
    assert client.get(f"{API}/certificados", headers=fab).json()["total"] == 0
    r = client.post(
        f"{API}/urv/creditos/{cert['credito']['id']}/transferir",
        json={"fabricante_id": str(dados_demo.montadora_id)},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert [c["id"] for c in client.get(f"{API}/certificados", headers=fab).json()["itens"]] == [cert["id"]]
    assert client.get(f"{API}/certificados/{cert['id']}", headers=fab).status_code == 200
    assert client.get(f"{VEICULOS}/{v['id']}/laudo", headers=fab).status_code == 200
    assert client.get(f"{VEICULOS}/{v['id']}/dmrs", headers=fab).status_code == 200
    anexos = client.get(f"{VEICULOS}/{v['id']}", headers=fab).json()["anexos"]
    assert anexos and all(
        client.get(f"{API}/anexos/{a['id']}/arquivo", headers=fab).status_code == 200 for a in anexos
    )


def test_sem_token(client, dados_demo) -> None:
    assert client.get(VEICULOS).status_code == 401
    assert client.post(VEICULOS, json=dados_veiculo()).status_code == 401


# --- Etapas (RF-08) -----------------------------------------------------------------------------


def test_descontaminacao_pode_ser_anterior_a_recepcao(client, h) -> None:
    v = criar_veiculo(client, h)
    r = etapa(client, h, v["id"], "DESCONTAMINACAO", "2026-10-01T08:00:00Z", "2026-10-01T12:00:00Z")
    assert r.status_code == 200, r.text
    assert etapa(client, h, v["id"], "RECEPCAO").status_code == 200

    detalhe = client.get(f"{VEICULOS}/{v['id']}", headers=h).json()
    assert [e["tipo"] for e in detalhe["etapas"]] == ["DESCONTAMINACAO", "RECEPCAO"]
    assert detalhe["estado"] == "EM_PROCESSO"


def test_put_de_etapa_atualiza_o_mesmo_registro(client, h, db_session) -> None:
    v = criar_veiculo(client, h)
    aberta = etapa(client, h, v["id"], "RECEPCAO", fim=None, observacoes="chegou de guincho").json()
    assert aberta["concluida_em"] is None
    fechada = etapa(client, h, v["id"], "RECEPCAO").json()
    assert fechada["id"] == aberta["id"]
    assert fechada["concluida_em"] is not None
    assert fechada["observacoes"] is None  # PUT substitui o registro inteiro

    assert len(client.get(f"{VEICULOS}/{v['id']}", headers=h).json()["etapas"]) == 1
    assert len(eventos(db_session, "ETAPA_REGISTRADA", aberta["id"])) == 1
    assert len(eventos(db_session, "ETAPA_ATUALIZADA", aberta["id"])) == 1


def test_etapa_invalida(client, h) -> None:
    v = criar_veiculo(client, h)
    assert (
        etapa(client, h, v["id"], "RECEPCAO", "2026-11-10T10:00:00Z", "2026-11-10T09:00:00Z").status_code
        == 422
    )
    assert etapa(client, h, v["id"], "RECEPCAO", "2026-11-10T10:00:00", None).status_code == 422  # sem fuso
    assert etapa(client, h, v["id"], "PINTURA").status_code == 422
    assert etapa(client, h, "00000000-0000-0000-0000-000000000000", "RECEPCAO").status_code == 404


# --- Anexos (RF-08) -----------------------------------------------------------------------------


def test_anexo_guarda_sha256_e_devolve_o_arquivo(client, h, pasta_uploads, db_session) -> None:
    v = criar_veiculo(client, h)
    r = anexar(client, h, v["id"], "FOTO", "RECEPCAO", conteudo=JPEG, nome="../../frente do carro.jpg")
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["sha256"] == hashlib.sha256(JPEG).hexdigest()
    assert a["content_type"] == "image/jpeg"
    assert a["tamanho_bytes"] == len(JPEG)
    assert a["nome_original"] == "frente do carro.jpg"  # só o nome, sem pastas
    assert "caminho" not in a

    # Nome de arquivo gerado, dentro da pasta do veículo.
    gravados = [p for p in pasta_uploads.rglob("*") if p.is_file()]
    assert len(gravados) == 1
    assert gravados[0].parent.name == v["id"]
    assert gravados[0].suffix == ".jpg"
    assert "frente" not in gravados[0].name

    r = client.get(f"{API}/anexos/{a['id']}/arquivo", headers=h)
    assert r.status_code == 200
    assert r.content == JPEG
    assert r.headers["content-type"] == "image/jpeg"
    assert eventos(db_session, "ANEXO_ENVIADO", a["id"])[0].payload["sha256"] == a["sha256"]


def test_anexo_recusa_tipo_de_arquivo(client, h, pasta_uploads) -> None:
    v = criar_veiculo(client, h)
    r = anexar(client, h, v["id"], "DOCUMENTO_ENTRADA", conteudo=b"MZ\x90\x00programa", nome="nota.pdf")
    assert r.status_code == 415
    assert r.json()["codigo"] == "TIPO_DE_ARQUIVO_NAO_PERMITIDO"
    assert anexar(client, h, v["id"], "FOTO", "RECEPCAO", conteudo=PDF).status_code == 415  # foto é imagem
    assert anexar(client, h, v["id"], "FOTO", "RECEPCAO", conteudo=b"").status_code == 422
    assert [p for p in pasta_uploads.rglob("*") if p.is_file()] == []


def test_anexo_acima_do_limite(client, h, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "upload_limite_bytes", 64)
    v = criar_veiculo(client, h)
    assert anexar(client, h, v["id"], "FOTO", "RECEPCAO", conteudo=PNG + b"\x00" * 64).status_code == 413
    assert anexar(client, h, v["id"], "FOTO", "RECEPCAO", conteudo=PNG).status_code == 201


def test_foto_exige_etapa(client, h) -> None:
    v = criar_veiculo(client, h)
    r = anexar(client, h, v["id"], "FOTO")
    assert r.status_code == 422
    assert r.json()["codigo"] == "ETAPA_OBRIGATORIA"


def test_detalhe_traz_pendencias_e_percentual(client, h) -> None:
    v = criar_veiculo(client, h)
    detalhe = client.get(f"{VEICULOS}/{v['id']}", headers=h).json()
    assert detalhe["etapas"] == [] and detalhe["anexos"] == []
    assert detalhe["percentual_aproveitado"] is None
    assert detalhe["laudo_id"] is None and detalhe["certificado_id"] is None
    assert len(detalhe["pendencias_certificado"]) > 5
