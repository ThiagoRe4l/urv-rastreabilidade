"""Cadastro de MMV. RF-03 e RF-04, art. 5º."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models import EventoAuditoria, TipoEmpresa
from app.modules.mmv.service import efeitos_a_partir_de
from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA, EMAIL_FABRICANTE
from tests.unit.urv.apoio import CNPJ_IMPORTADORA, criar_empresa_com_usuario, criar_mmv

MMVS = "/api/v1/mmvs"


def _corpo(**dados) -> dict:
    return {
        "codigo": "HATCH-1.0-FLEX",
        "ncm": "8703.21.00",
        "nivel": 1,
        "percentual_reciclabilidade": "85.50",
        "ja_comercializado": False,
        **dados,
    }


# --- Função pura (RF-04, art. 5º §2º) ----------------------------------------------------------


def test_mmv_ja_comercializado_tem_efeitos_em_primeiro_de_janeiro_seguinte() -> None:
    assert efeitos_a_partir_de(date(2026, 11, 13), ja_comercializado=True) == date(2027, 1, 1)
    assert efeitos_a_partir_de(date(2026, 12, 31), ja_comercializado=True) == date(2027, 1, 1)
    assert efeitos_a_partir_de(date(2027, 1, 1), ja_comercializado=True) == date(2028, 1, 1)


def test_mmv_ainda_nao_comercializado_tem_efeitos_na_data_do_cadastro() -> None:
    assert efeitos_a_partir_de(date(2026, 11, 13), ja_comercializado=False) == date(2026, 11, 13)
    assert efeitos_a_partir_de(date(2026, 12, 31), ja_comercializado=False) == date(2026, 12, 31)


# --- Rotas -------------------------------------------------------------------------------------


def test_mmv_novo_produz_efeitos_na_data_do_cadastro(client, auth, relogio, dados_demo, db_session) -> None:
    r = client.post(MMVS, json=_corpo(), headers=auth(EMAIL_FABRICANTE))
    assert r.status_code == 201, r.text
    mmv = r.json()
    assert mmv["fabricante_id"] == str(dados_demo.montadora_id)
    assert mmv["ncm"] == "87032100"  # gravado só com dígitos
    assert mmv["percentual_reciclabilidade"] == "85.50"  # Decimal trafega como string
    assert mmv["efeitos_a_partir_de"] == "2026-11-13"  # RF-04, art. 5º §2º II
    assert mmv["rm"] == 10  # nível 1: valor do seed em config_parametro, pendente do decreto (L-01)
    assert mmv["status"] == "ATIVO"

    evento = db_session.scalar(
        select(EventoAuditoria).where(
            EventoAuditoria.tipo == "MMV_CADASTRADO", EventoAuditoria.entidade_id == uuid.UUID(mmv["id"])
        )
    )
    assert evento is not None
    assert evento.empresa_id == dados_demo.montadora_id
    assert evento.payload["efeitos_a_partir_de"] == "2026-11-13"


def test_mmv_ja_comercializado_produz_efeitos_no_ano_seguinte(client, auth, relogio) -> None:
    r = client.post(MMVS, json=_corpo(nivel=2, ja_comercializado=True), headers=auth(EMAIL_FABRICANTE))
    assert r.status_code == 201, r.text
    assert r.json()["efeitos_a_partir_de"] == "2027-01-01"  # RF-04, art. 5º §2º I
    assert r.json()["rm"] == 5  # nível 2: valor do seed em config_parametro (L-01)


def test_data_do_cadastro_e_a_de_brasilia(client, auth, relogio) -> None:
    relogio(datetime(2027, 1, 1, 2, 0, tzinfo=UTC))  # 23h de 31/12/2026 em Brasília
    r = client.post(MMVS, json=_corpo(ja_comercializado=True), headers=auth(EMAIL_FABRICANTE))
    assert r.json()["efeitos_a_partir_de"] == "2027-01-01"
    r = client.post(MMVS, json=_corpo(codigo="SUV-2.0"), headers=auth(EMAIL_FABRICANTE))
    assert r.json()["efeitos_a_partir_de"] == "2026-12-31"


def test_codigo_duplicado_no_mesmo_fabricante(client, auth, relogio) -> None:
    assert client.post(MMVS, json=_corpo(), headers=auth(EMAIL_FABRICANTE)).status_code == 201
    r = client.post(MMVS, json=_corpo(nivel=2), headers=auth(EMAIL_FABRICANTE))
    assert r.status_code == 409
    assert r.json()["codigo"] == "MMV_DUPLICADO"


def test_mesmo_codigo_em_outro_fabricante_e_aceito(client, auth, relogio, db_session, dados_demo) -> None:
    criar_empresa_com_usuario(
        db_session,
        cnpj=CNPJ_IMPORTADORA,
        razao_social="Importadora Z",
        tipo=TipoEmpresa.FABRICANTE,
        email="fiscal@importadora.local",
    )
    assert client.post(MMVS, json=_corpo(), headers=auth(EMAIL_FABRICANTE)).status_code == 201
    assert client.post(MMVS, json=_corpo(), headers=auth("fiscal@importadora.local")).status_code == 201


@pytest.mark.parametrize(
    "dados",
    [
        {"nivel": 3},
        {"nivel": 0},
        {"ncm": "8703"},
        {"ncm": "8703.21.0X"},
        {"percentual_reciclabilidade": "100.01"},
        {"percentual_reciclabilidade": "-1"},
        {"percentual_reciclabilidade": "85.555"},
        {"codigo": "   "},
        {"codigo": "X" * 61},
    ],
)
def test_entrada_invalida(client, auth, relogio, dados) -> None:
    r = client.post(MMVS, json=_corpo(**dados), headers=auth(EMAIL_FABRICANTE))
    assert r.status_code == 422, r.text
    assert r.json()["codigo"] == "ENTRADA_INVALIDA"


@pytest.mark.parametrize(
    ("email", "codigo"),
    [
        (EMAIL_DESMONTADORA, "PAPEL_NAO_PERMITIDO"),
        (EMAIL_ADMIN, "PAPEL_NAO_PERMITIDO"),
        (EMAIL_AUDITOR, "AUDITOR_SOMENTE_LEITURA"),
    ],
)
def test_so_fabricante_cadastra_mmv(client, auth, relogio, email, codigo) -> None:
    r = client.post(MMVS, json=_corpo(), headers=auth(email))
    assert r.status_code == 403
    assert r.json()["codigo"] == codigo


def test_listagem_por_papel(client, auth, db_session, dados_demo) -> None:
    outro = criar_empresa_com_usuario(
        db_session,
        cnpj=CNPJ_IMPORTADORA,
        razao_social="Importadora Z",
        tipo=TipoEmpresa.FABRICANTE,
        email="fiscal@importadora.local",
    )
    criar_mmv(db_session, dados_demo.montadora_id, codigo="B-SEDAN")
    criar_mmv(db_session, dados_demo.montadora_id, codigo="A-HATCH", nivel=2)
    criar_mmv(db_session, outro.empresa_id, codigo="C-SUV")

    r = client.get(MMVS, headers=auth(EMAIL_FABRICANTE))
    assert r.status_code == 200
    assert [m["codigo"] for m in r.json()["itens"]] == ["A-HATCH", "B-SEDAN"]  # só os próprios
    assert [m["rm"] for m in r.json()["itens"]] == [5, 10]

    # Pedir os de outra empresa não revela que ela existe.
    r = client.get(MMVS, params={"empresa_id": str(outro.empresa_id)}, headers=auth(EMAIL_FABRICANTE))
    assert r.status_code == 404

    for email in (EMAIL_AUDITOR, EMAIL_ADMIN):  # RF-23
        assert client.get(MMVS, headers=auth(email)).json()["total"] == 3
        r = client.get(MMVS, params={"empresa_id": str(outro.empresa_id)}, headers=auth(email))
        assert [m["codigo"] for m in r.json()["itens"]] == ["C-SUV"]

    assert client.get(MMVS, headers=auth(EMAIL_DESMONTADORA)).status_code == 403
    assert client.get(MMVS).status_code == 401
