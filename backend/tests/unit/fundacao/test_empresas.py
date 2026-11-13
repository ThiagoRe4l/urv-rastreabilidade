"""Empresas, credenciamento e vínculos. RF-01 e RF-02, arts. 8º II, 11, 13 e 16."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import EventoAuditoria
from app.modules.empresas.service import somar_anos
from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA, EMAIL_FABRICANTE

EMPRESAS = "/api/v1/empresas"
VINCULOS = "/api/v1/vinculos"

CNPJ_NOVO = "11.222.333/0001-81"
CNPJ_OUTRO = "11444777000161"


def _criar(client, auth, **dados):
    corpo = {"cnpj": CNPJ_NOVO, "razao_social": "Recicla Sul S.A.", "tipo": "RECICLADORA", **dados}
    return client.post(EMPRESAS, json=corpo, headers=auth(EMAIL_ADMIN))


def _eventos(db_session, tipo: str, entidade_id) -> list[EventoAuditoria]:
    return list(
        db_session.scalars(
            select(EventoAuditoria).where(
                EventoAuditoria.tipo == tipo, EventoAuditoria.entidade_id == entidade_id
            )
        )
    )


# --- POST /empresas --------------------------------------------------------------------------


def test_admin_cria_geradora_pendente_e_registra_evento(client, auth, db_session) -> None:
    r = _criar(client, auth)
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["cnpj"] == "11222333000181"  # gravado só com dígitos
    assert e["credenciamento_status"] == "PENDENTE"
    assert e["credenciamento_vigente"] is False
    assert e["registro_compromissos"] is False

    eventos = _eventos(db_session, "EMPRESA_CRIADA", uuid.UUID(e["id"]))
    assert len(eventos) == 1
    assert eventos[0].payload["cnpj"] == "11222333000181"
    assert str(eventos[0].empresa_id) == e["id"]


def test_fabricante_nao_tem_credenciamento(client, auth) -> None:
    r = _criar(client, auth, tipo="FABRICANTE", registro_compromissos=True)
    assert r.status_code == 201
    assert r.json()["credenciamento_status"] is None
    assert r.json()["registro_compromissos"] is True


def test_registro_compromissos_so_para_fabricante(client, auth) -> None:
    r = _criar(client, auth, registro_compromissos=True)
    assert r.status_code == 422
    assert r.json()["codigo"] == "REGISTRO_COMPROMISSOS_SO_FABRICANTE"


@pytest.mark.parametrize("cnpj", ["11222333000180", "123", "00000000000000"])
def test_cnpj_invalido(client, auth, cnpj) -> None:
    r = _criar(client, auth, cnpj=cnpj)
    assert r.status_code == 422
    assert r.json()["codigo"] == "ENTRADA_INVALIDA"


def test_cnpj_duplicado(client, auth) -> None:
    assert _criar(client, auth).status_code == 201
    r = _criar(client, auth, razao_social="Outra")
    assert r.status_code == 409
    assert r.json()["codigo"] == "CNPJ_DUPLICADO"


@pytest.mark.parametrize("email", [EMAIL_DESMONTADORA, EMAIL_FABRICANTE])
def test_so_admin_cria_empresa(client, auth, email) -> None:
    r = client.post(
        EMPRESAS, json={"cnpj": CNPJ_NOVO, "razao_social": "X", "tipo": "RECICLADORA"}, headers=auth(email)
    )
    assert r.status_code == 403


def test_auditor_nao_cria_empresa(client, auth) -> None:
    r = client.post(
        EMPRESAS,
        json={"cnpj": CNPJ_NOVO, "razao_social": "X", "tipo": "RECICLADORA"},
        headers=auth(EMAIL_AUDITOR),
    )
    assert r.status_code == 403
    assert r.json()["codigo"] == "AUDITOR_SOMENTE_LEITURA"


# --- GET /empresas ---------------------------------------------------------------------------


def test_admin_e_auditor_veem_todas(client, auth) -> None:
    _criar(client, auth)
    for email in (EMAIL_ADMIN, EMAIL_AUDITOR):
        r = client.get(EMPRESAS, headers=auth(email))
        assert r.status_code == 200
        assert r.json()["total"] == 3


def test_filtro_por_tipo(client, auth) -> None:
    r = client.get(EMPRESAS, params={"tipo": "FABRICANTE"}, headers=auth(EMAIL_ADMIN))
    assert [e["razao_social"] for e in r.json()["itens"]] == ["Montadora Exemplo S.A."]


def test_empresa_ve_a_propria_e_as_contrapartes_com_vinculo(client, auth) -> None:
    _criar(client, auth)  # recicladora sem vínculo: invisível para as demais
    r = client.get(EMPRESAS, headers=auth(EMAIL_DESMONTADORA))
    nomes = {e["razao_social"] for e in r.json()["itens"]}
    assert nomes == {"Desmonte Paraná S.A.", "Montadora Exemplo S.A."}

    r = client.get(EMPRESAS, params={"tipo": "FABRICANTE"}, headers=auth(EMAIL_DESMONTADORA))
    assert [e["razao_social"] for e in r.json()["itens"]] == ["Montadora Exemplo S.A."]


def test_contraparte_some_quando_vinculo_desativado(client, auth, dados_demo) -> None:
    client.patch(f"{VINCULOS}/{dados_demo.vinculo_id}", json={"ativo": False}, headers=auth(EMAIL_ADMIN))
    r = client.get(EMPRESAS, headers=auth(EMAIL_FABRICANTE))
    assert {e["razao_social"] for e in r.json()["itens"]} == {"Montadora Exemplo S.A."}


def test_paginacao(client, auth) -> None:
    r = client.get(EMPRESAS, params={"pagina": 2, "tamanho": 1}, headers=auth(EMAIL_ADMIN))
    assert r.json()["total"] == 2
    assert len(r.json()["itens"]) == 1
    assert client.get(EMPRESAS, params={"tamanho": 1000}, headers=auth(EMAIL_ADMIN)).status_code == 422


# --- PATCH /empresas/{id} --------------------------------------------------------------------


def test_admin_altera_registro_compromissos(client, auth, dados_demo, db_session) -> None:
    r = client.patch(
        f"{EMPRESAS}/{dados_demo.montadora_id}",
        json={"registro_compromissos": False},
        headers=auth(EMAIL_ADMIN),
    )
    assert r.status_code == 200
    assert r.json()["registro_compromissos"] is False
    ev = _eventos(db_session, "EMPRESA_ATUALIZADA", dados_demo.montadora_id)
    assert ev[0].payload == {"registro_compromissos": {"antes": True, "depois": False}}


def test_registro_compromissos_em_geradora_rejeitado(client, auth, dados_demo) -> None:
    r = client.patch(
        f"{EMPRESAS}/{dados_demo.desmonte_id}",
        json={"registro_compromissos": True},
        headers=auth(EMAIL_ADMIN),
    )
    assert r.status_code == 422


def test_patch_empresa_inexistente(client, auth) -> None:
    r = client.patch(
        f"{EMPRESAS}/00000000-0000-0000-0000-000000000000",
        json={"registro_compromissos": True},
        headers=auth(EMAIL_ADMIN),
    )
    assert r.status_code == 404
    assert r.json()["codigo"] == "NAO_ENCONTRADO"


# --- PATCH /empresas/{id}/credenciamento -----------------------------------------------------


def _credenciar(client, auth, empresa_id, **dados):
    return client.patch(f"{EMPRESAS}/{empresa_id}/credenciamento", json=dados, headers=auth(EMAIL_ADMIN))


def test_credenciamento_ativo_por_ate_dois_anos(client, auth, db_session) -> None:
    empresa_id = _criar(client, auth).json()["id"]
    validade = somar_anos(date.today(), 2)
    r = _credenciar(client, auth, empresa_id, status="ATIVO", validade=validade.isoformat())
    assert r.status_code == 200, r.text
    assert r.json()["credenciamento_status"] == "ATIVO"
    assert r.json()["credenciamento_vigente"] is True
    ev = _eventos(db_session, "CREDENCIAMENTO_ALTERADO", uuid.UUID(empresa_id))
    assert ev[0].payload["antes"]["status"] == "PENDENTE"
    assert ev[0].payload["depois"] == {"status": "ATIVO", "validade": validade.isoformat()}


def test_credenciamento_acima_de_dois_anos(client, auth) -> None:
    empresa_id = _criar(client, auth).json()["id"]
    validade = somar_anos(date.today(), 2) + timedelta(days=1)
    r = _credenciar(client, auth, empresa_id, status="ATIVO", validade=validade.isoformat())
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDADE_ACIMA_DE_DOIS_ANOS"


def test_credenciamento_ativo_exige_validade_futura(client, auth) -> None:
    empresa_id = _criar(client, auth).json()["id"]
    assert _credenciar(client, auth, empresa_id, status="ATIVO").json()["codigo"] == "VALIDADE_OBRIGATORIA"
    ontem = (date.today() - timedelta(days=1)).isoformat()
    assert _credenciar(client, auth, empresa_id, status="ATIVO", validade=ontem).json()["codigo"] == (
        "VALIDADE_VENCIDA"
    )


def test_suspensao_mantem_validade_e_deixa_de_estar_vigente(client, auth, dados_demo) -> None:
    r = _credenciar(client, auth, dados_demo.desmonte_id, status="SUSPENSO")
    assert r.status_code == 200
    assert r.json()["credenciamento_validade"] is not None
    assert r.json()["credenciamento_vigente"] is False


def test_fabricante_sem_credenciamento(client, auth, dados_demo) -> None:
    r = _credenciar(client, auth, dados_demo.montadora_id, status="ATIVO", validade=date.today().isoformat())
    assert r.status_code == 422
    assert r.json()["codigo"] == "FABRICANTE_SEM_CREDENCIAMENTO"


def test_so_admin_credencia(client, auth, dados_demo) -> None:
    r = client.patch(
        f"{EMPRESAS}/{dados_demo.desmonte_id}/credenciamento",
        json={"status": "CANCELADO"},
        headers=auth(EMAIL_DESMONTADORA),
    )
    assert r.status_code == 403


# --- Vínculos --------------------------------------------------------------------------------


def test_admin_cria_vinculo(client, auth, dados_demo, db_session) -> None:
    geradora = _criar(client, auth).json()["id"]
    r = client.post(
        VINCULOS,
        json={"geradora_id": geradora, "fabricante_id": str(dados_demo.montadora_id)},
        headers=auth(EMAIL_ADMIN),
    )
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["ativo"] is True
    assert v["geradora"]["razao_social"] == "Recicla Sul S.A."
    assert v["fabricante"]["tipo"] == "FABRICANTE"
    assert len(_eventos(db_session, "VINCULO_CRIADO", uuid.UUID(v["id"]))) == 1


def test_vinculo_duplicado(client, auth, dados_demo) -> None:
    r = client.post(
        VINCULOS,
        json={"geradora_id": str(dados_demo.desmonte_id), "fabricante_id": str(dados_demo.montadora_id)},
        headers=auth(EMAIL_ADMIN),
    )
    assert r.status_code == 409
    assert r.json()["codigo"] == "VINCULO_DUPLICADO"


def test_vinculo_com_tipos_errados(client, auth, dados_demo) -> None:
    invertido = {"geradora_id": str(dados_demo.montadora_id), "fabricante_id": str(dados_demo.desmonte_id)}
    r = client.post(VINCULOS, json=invertido, headers=auth(EMAIL_ADMIN))
    assert r.status_code == 422
    assert r.json()["codigo"] == "GERADORA_INVALIDA"

    outra_geradora = _criar(client, auth).json()["id"]
    r = client.post(
        VINCULOS,
        json={"geradora_id": str(dados_demo.desmonte_id), "fabricante_id": outra_geradora},
        headers=auth(EMAIL_ADMIN),
    )
    assert r.json()["codigo"] == "FABRICANTE_INVALIDO"


def test_vinculos_filtrados_pela_empresa(client, auth, dados_demo) -> None:
    geradora = _criar(client, auth).json()["id"]
    fabricante = _criar(
        client, auth, cnpj=CNPJ_OUTRO, tipo="FABRICANTE", razao_social="Importadora Z"
    ).json()["id"]
    client.post(
        VINCULOS, json={"geradora_id": geradora, "fabricante_id": fabricante}, headers=auth(EMAIL_ADMIN)
    )

    assert client.get(VINCULOS, headers=auth(EMAIL_ADMIN)).json()["total"] == 2
    assert client.get(VINCULOS, headers=auth(EMAIL_AUDITOR)).json()["total"] == 2
    for email in (EMAIL_DESMONTADORA, EMAIL_FABRICANTE):
        r = client.get(VINCULOS, headers=auth(email))
        assert r.json()["total"] == 1
        assert r.json()["itens"][0]["id"] == str(dados_demo.vinculo_id)


def test_admin_desativa_e_reativa_vinculo(client, auth, dados_demo, db_session) -> None:
    url = f"{VINCULOS}/{dados_demo.vinculo_id}"
    r = client.patch(url, json={"ativo": False}, headers=auth(EMAIL_ADMIN))
    assert r.status_code == 200
    assert r.json()["ativo"] is False
    assert client.patch(url, json={"ativo": True}, headers=auth(EMAIL_ADMIN)).json()["ativo"] is True
    eventos = _eventos(db_session, "VINCULO_ALTERADO", dados_demo.vinculo_id)
    assert [e.payload["ativo"] for e in eventos] == [
        {"antes": True, "depois": False},
        {"antes": False, "depois": True},
    ]


def test_so_admin_altera_vinculo(client, auth, dados_demo) -> None:
    url = f"{VINCULOS}/{dados_demo.vinculo_id}"
    assert client.patch(url, json={"ativo": False}, headers=auth(EMAIL_DESMONTADORA)).status_code == 403
    assert client.patch(url, json={"ativo": False}, headers=auth(EMAIL_AUDITOR)).status_code == 403


def test_servicos_para_outros_modulos(db_session, dados_demo) -> None:
    from app.models import Empresa
    from app.modules.empresas.service import alterar_vinculo, credenciamento_vigente, vinculo_ativo

    desmonte = db_session.get(Empresa, dados_demo.desmonte_id)
    montadora = db_session.get(Empresa, dados_demo.montadora_id)
    assert credenciamento_vigente(desmonte, date.today())
    assert not credenciamento_vigente(desmonte, somar_anos(date.today(), 3))
    assert not credenciamento_vigente(montadora, date.today())

    assert vinculo_ativo(db_session, dados_demo.desmonte_id, dados_demo.montadora_id)
    assert not vinculo_ativo(db_session, dados_demo.montadora_id, dados_demo.desmonte_id)
    alterar_vinculo(db_session, None, dados_demo.vinculo_id, False)
    assert not vinculo_ativo(db_session, dados_demo.desmonte_id, dados_demo.montadora_id)
