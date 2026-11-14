"""Eventos da trilha por veículo: GET /auditoria/eventos?veiculo_id=. RF-22, RF-23; lacuna L-13."""

from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA
from tests.unit.fluxo.apoio import API, CNPJ_DESTINATARIO, certificado, criar_veiculo, executar_passos

EVENTOS = f"{API}/auditoria/eventos"

# Um evento de cada registro ligado ao veículo, além dos do próprio veículo.
TIPOS_DO_DOSSIE = {
    "VEICULO_RECEBIDO",
    "VEICULO_CLASSIFICADO",
    "ETAPA_REGISTRADA",
    "ANEXO_ENVIADO",
    "PECA_REGISTRADA",
    "PESAGEM_REGISTRADA",
    "DMR_EMITIDA",
    "LAUDO_ASSINADO",
    "CERTIFICADO_EMITIDO",
    "CREDITO_GERADO",
}


def _dmr(client, h, veiculo_id: str) -> None:
    corpo = {
        "numero": "DMR-1",
        "destinatario_nome": "Siderúrgica Exemplo",
        "destinatario_cnpj": CNPJ_DESTINATARIO,
        "tipo_material": "Sucata ferrosa",
        "peso_kg": "700.000",
    }
    r = client.post(f"{API}/veiculos/{veiculo_id}/dmrs", json=corpo, headers=h)
    assert r.status_code == 201, r.text


def _eventos(client, auth, veiculo_id: str, email: str = EMAIL_AUDITOR) -> list[dict]:
    r = client.get(EVENTOS, params={"veiculo_id": veiculo_id, "tamanho": 100}, headers=auth(email))
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["total"] == len(corpo["itens"])
    return corpo["itens"]


def test_eventos_do_veiculo_trazem_o_dossie_inteiro(client, h, auth) -> None:
    v = criar_veiculo(client, h)
    executar_passos(client, h, v["id"])
    _dmr(client, h, v["id"])
    assert certificado(client, h, v["id"]).status_code == 201
    outro = criar_veiculo(client, h, chassi="8AFZZZ54ABJ123456", placa="QWE4R56")
    executar_passos(client, h, outro["id"], pular=("laudo",))

    eventos = _eventos(client, auth, v["id"])
    assert {e["tipo"] for e in eventos} >= TIPOS_DO_DOSSIE
    for e in eventos:
        do_veiculo = e["entidade"] == "veiculo" and e["entidade_id"] == v["id"]
        assert do_veiculo or e["payload"].get("veiculo_id") == v["id"], e
    # Em ordem de sequência, e nada do outro veículo.
    assert [e["sequencia"] for e in eventos] == sorted(e["sequencia"] for e in eventos)
    ids_outro = {e["id"] for e in _eventos(client, auth, outro["id"])}
    assert ids_outro and not ids_outro & {e["id"] for e in eventos}
    # Antes, só o filtro por entidade_id existia, e achava só os eventos do próprio veículo.
    so_entidade = client.get(
        EVENTOS, params={"entidade_id": v["id"], "tamanho": 100}, headers=auth(EMAIL_AUDITOR)
    ).json()["itens"]
    assert len(eventos) > len(so_entidade)

    assert [e["id"] for e in _eventos(client, auth, v["id"], EMAIL_ADMIN)] == [e["id"] for e in eventos]
    r = client.get(EVENTOS, params={"veiculo_id": v["id"]}, headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 403  # a trilha é do AUDITOR e do ADMIN (RF-23)
