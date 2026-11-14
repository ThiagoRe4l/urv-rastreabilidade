"""Peças, etiqueta de rastreio e consulta. RF-09 e RF-10, Anexo III 6 a 8, 10 e 16."""

from datetime import date

from scripts.seed import CNPJ_DESMONTE
from tests.unit.fluxo.apoio import API, CHASSI, criar_veiculo, eventos, peca

PECAS = f"{API}/pecas"


def test_peca_reutilizavel_recebe_codigo_e_etiqueta(client, h, db_session) -> None:
    v = criar_veiculo(client, h)
    r = peca(client, h, v["id"])
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["codigo_rastreio"].startswith("PC-")
    assert p["chassi"] == CHASSI
    assert p["descaracterizada"] is False
    # RF-09: a etiqueta devolve nome, chassi, data e CNPJ da desmontadora.
    assert p["etiqueta"] == {
        "nome": "Porta dianteira esquerda",
        "chassi": CHASSI,
        "data": date.fromisoformat(p["criado_em"][:10]).isoformat(),
        "cnpj": CNPJ_DESMONTE,
        "codigo": p["codigo_rastreio"],
    }
    assert (
        eventos(db_session, "PECA_REGISTRADA", p["id"])[0].payload["codigo_rastreio"] == p["codigo_rastreio"]
    )
    assert client.get(f"{API}/veiculos/{v['id']}", headers=h).json()["estado"] == "EM_PROCESSO"


def test_codigo_de_rastreio_e_unico(client, h) -> None:
    v = criar_veiculo(client, h)
    codigos = {peca(client, h, v["id"], nome=f"Peça {i}").json()["codigo_rastreio"] for i in range(20)}
    assert len(codigos) == 20


def test_peca_nao_reutilizavel_nao_tem_etiqueta(client, h) -> None:
    v = criar_veiculo(client, h)
    r = peca(
        client, h, v["id"], nome="Airbag", classificacao="NAO_REUTILIZAVEL", condicao=None, destino="DESCARTE"
    )
    assert r.status_code == 201, r.text
    assert r.json()["codigo_rastreio"] is None
    assert r.json()["etiqueta"] is None


def test_peca_nao_reutilizavel_nao_vai_para_venda(client, h) -> None:
    v = criar_veiculo(client, h)
    for destino in ("ESTOQUE", "REVENDA", "EXPORTACAO"):
        r = peca(client, h, v["id"], classificacao="NAO_REUTILIZAVEL", condicao=None, destino=destino)
        assert r.status_code == 422
        assert r.json()["codigo"] == "DESTINO_INCOMPATIVEL"
    # Anexo III, item 10 d: recondicionamento e remanufatura são destinos válidos.
    r = peca(client, h, v["id"], classificacao="NAO_REUTILIZAVEL", condicao=None, destino="REMANUFATURA")
    assert r.status_code == 201

    r = client.patch(f"{PECAS}/{r.json()['id']}", json={"destino": "REVENDA"}, headers=h)
    assert r.json()["codigo"] == "DESTINO_INCOMPATIVEL"


def test_peca_reutilizavel_exige_condicao(client, h) -> None:
    v = criar_veiculo(client, h)
    assert peca(client, h, v["id"], condicao=None).status_code == 422


def test_consulta_publica_expoe_so_etiqueta_e_destino(client, h) -> None:
    v = criar_veiculo(client, h)
    p = peca(client, h, v["id"]).json()

    r = client.get(f"{PECAS}/rastreio/{p['codigo_rastreio'].lower()}")  # sem token
    assert r.status_code == 200, r.text
    assert r.json() == {**p["etiqueta"], "destino": "ESTOQUE"}

    client.patch(f"{PECAS}/{p['id']}", json={"destino": "REVENDA"}, headers=h)
    assert client.get(f"{PECAS}/rastreio/{p['codigo_rastreio']}").json()["destino"] == "REVENDA"

    r = client.get(f"{PECAS}/rastreio/PC-NAOEXISTE")
    assert r.status_code == 404
    assert r.json()["codigo"] == "NAO_ENCONTRADO"


def test_patch_muda_destino_e_descaracteriza(client, h, db_session) -> None:
    v = criar_veiculo(client, h)
    p = peca(client, h, v["id"], classificacao="NAO_REUTILIZAVEL", condicao=None, destino="RECICLAGEM").json()

    r = client.patch(f"{PECAS}/{p['id']}", json={"descaracterizada": True, "destino": "DESCARTE"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["descaracterizada"] is True
    assert r.json()["destino"] == "DESCARTE"
    ev = eventos(db_session, "PECA_ATUALIZADA", p["id"])
    assert ev[0].payload["destino"] == {"antes": "RECICLAGEM", "depois": "DESCARTE"}
    assert ev[0].payload["descaracterizada"] == {"antes": False, "depois": True}

    r = client.patch(f"{PECAS}/{p['id']}", json={"descaracterizada": False}, headers=h)
    assert r.status_code == 422
    assert r.json()["codigo"] == "DESCARACTERIZACAO_IRREVERSIVEL"
    # Sem mudança de fato, não há novo evento.
    assert client.patch(f"{PECAS}/{p['id']}", json={"destino": "DESCARTE"}, headers=h).status_code == 200
    assert len(eventos(db_session, "PECA_ATUALIZADA", p["id"])) == 1

    assert client.patch(f"{PECAS}/{p['id']}", json={}, headers=h).status_code == 422
    vazio = "00000000-0000-0000-0000-000000000000"
    assert client.patch(f"{PECAS}/{vazio}", json={"destino": "DESCARTE"}, headers=h).status_code == 404


def test_consulta_por_origem_tipo_condicao_e_destino(client, h) -> None:
    a = criar_veiculo(client, h)
    b = criar_veiculo(client, h, chassi="8AFZZZ54ABJ123456", placa="QWE4R56")
    peca(client, h, a["id"], nome="Porta dianteira", destino="ESTOQUE")
    peca(client, h, a["id"], nome="Motor 1.6", condicao="REMANUFATURADA", destino="REVENDA")
    peca(client, h, b["id"], nome="Porta traseira", destino="EXPORTACAO")
    peca(
        client, h, b["id"], nome="Cinto", classificacao="NAO_REUTILIZAVEL", condicao=None, destino="DESCARTE"
    )

    def nomes(**filtros) -> set[str]:
        r = client.get(PECAS, params=filtros, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["total"] == len(r.json()["itens"])
        return {p["nome"] for p in r.json()["itens"]}

    assert len(nomes()) == 4
    assert nomes(chassi=CHASSI) == {"Porta dianteira", "Motor 1.6"}
    assert nomes(nome="porta") == {"Porta dianteira", "Porta traseira"}
    assert nomes(condicao="REMANUFATURADA") == {"Motor 1.6"}
    assert nomes(destino="EXPORTACAO") == {"Porta traseira"}
    assert nomes(classificacao="NAO_REUTILIZAVEL") == {"Cinto"}
    assert nomes(nome="porta", chassi="8AFZ") == {"Porta traseira"}
    assert nomes(nome="100%") == set()  # curingas do LIKE são tratados como texto
    # PM-WEB-04: peças de um veículo, e toda peça traz o chassi de origem.
    assert nomes(veiculo_id=b["id"]) == {"Porta traseira", "Cinto"}
    assert nomes(veiculo_id=a["id"], destino="REVENDA") == {"Motor 1.6"}
    r = client.get(PECAS, params={"veiculo_id": b["id"]}, headers=h).json()["itens"]
    assert {p["chassi"] for p in r} == {"8AFZZZ54ABJ123456"}


def test_consulta_por_veiculo_de_outra_empresa_nao_vaza(client, h, h_outra) -> None:
    """PM-WEB-04 com RNF-01: o filtro por veículo não fura o escopo da empresa."""
    a = criar_veiculo(client, h)
    peca(client, h, a["id"], nome="Porta dianteira", destino="ESTOQUE")
    r = client.get(PECAS, params={"veiculo_id": a["id"]}, headers=h_outra)
    assert r.status_code == 200
    assert r.json() == {"itens": [], "total": 0}


def test_item_de_seguranca_so_como_nao_reutilizavel(client, h, db_session) -> None:
    """RF-27, Anexo III 7: item de segurança é obrigatoriamente não reutilizável (R10 da revisão)."""
    v = criar_veiculo(client, h)
    r = peca(client, h, v["id"], nome="Airbag do motorista", item_seguranca=True)  # REUTILIZAVEL
    assert (r.status_code, r.json()["codigo"]) == (422, "ITEM_SEGURANCA_NAO_REUTILIZAVEL")
    r = peca(
        client,
        h,
        v["id"],
        nome="Airbag do motorista",
        classificacao="NAO_REUTILIZAVEL",
        condicao=None,
        destino="DESCARTE",
        item_seguranca=True,
    )
    assert r.status_code == 201, r.text
    assert r.json()["item_seguranca"] is True and r.json()["etiqueta"] is None
    assert eventos(db_session, "PECA_REGISTRADA", r.json()["id"])[0].payload["item_seguranca"] is True
    # Sem marcação, a peça comum segue reutilizável.
    assert peca(client, h, v["id"]).json()["item_seguranca"] is False
