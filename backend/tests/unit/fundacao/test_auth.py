"""Autenticação JWT, papéis e escopo por empresa. RNF-03, RNF-06, art. 20 VII; art. 24 V."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import obter_sessao
from app.core.deps import exige_papel, filtrar_por_empresa, garantir_acesso_empresa, usuario_atual
from app.core.erros import ErroNegocio
from app.main import criar_app
from app.models import Empresa, Papel, Usuario
from scripts.seed import (
    EMAIL_ADMIN,
    EMAIL_AUDITOR,
    EMAIL_DESMONTADORA,
    EMAIL_FABRICANTE,
    SENHA_DEMO,
)

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"

USUARIOS_DEMO = [
    (EMAIL_ADMIN, "ADMIN", None),
    (EMAIL_AUDITOR, "AUDITOR", None),
    (EMAIL_DESMONTADORA, "DESMONTADORA", "Desmonte Paraná S.A."),
    (EMAIL_FABRICANTE, "FABRICANTE", "Montadora Exemplo S.A."),
]


@pytest.mark.parametrize(("email", "papel", "empresa"), USUARIOS_DEMO)
def test_login_dos_quatro_usuarios_de_demonstracao(client, dados_demo, email, papel, empresa) -> None:
    r = client.post(LOGIN, json={"email": email, "senha": SENHA_DEMO})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["usuario"]["papel"] == papel
    assert (corpo["usuario"]["empresa"] or {}).get("razao_social") == empresa

    me = client.get(ME, headers={"Authorization": f"Bearer {corpo['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert set(me.json()) == {"id", "nome", "email", "papel", "empresa"}


def test_token_carrega_papel_e_empresa(client, dados_demo) -> None:
    r = client.post(LOGIN, json={"email": EMAIL_DESMONTADORA, "senha": SENHA_DEMO})
    claims = jwt.decode(r.json()["access_token"], options={"verify_signature": False})
    assert claims["papel"] == "DESMONTADORA"
    assert claims["empresa_id"] == str(dados_demo.desmonte_id)
    assert claims["sub"] == str(dados_demo.operador_id)


def test_login_ignora_maiusculas_e_espacos_no_email(client, dados_demo) -> None:
    r = client.post(LOGIN, json={"email": "  Admin@URV.local ", "senha": SENHA_DEMO})
    assert r.status_code == 200


@pytest.mark.parametrize(
    ("email", "senha"), [(EMAIL_ADMIN, "errada"), ("ninguem@urv.local", SENHA_DEMO), (EMAIL_ADMIN, "x" * 100)]
)
def test_login_invalido(client, dados_demo, email, senha) -> None:
    r = client.post(LOGIN, json={"email": email, "senha": senha})
    assert r.status_code == 401
    assert r.json() == {"detail": "E-mail ou senha incorretos.", "codigo": "CREDENCIAIS_INVALIDAS"}


def test_login_sem_campos_devolve_422_no_formato_do_contrato(client) -> None:
    r = client.post(LOGIN, json={"email": EMAIL_ADMIN})
    assert r.status_code == 422
    assert r.json()["codigo"] == "ENTRADA_INVALIDA"
    assert "senha" in r.json()["detail"]


def test_me_sem_token(client) -> None:
    r = client.get(ME)
    assert r.status_code == 401
    assert r.json()["codigo"] == "NAO_AUTENTICADO"


def test_me_com_token_invalido(client) -> None:
    r = client.get(ME, headers={"Authorization": "Bearer nao-e-um-jwt"})
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_INVALIDO"


def test_me_com_token_expirado(client, dados_demo) -> None:
    s = get_settings()
    vencido = jwt.encode(
        {"sub": str(dados_demo.admin_id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        s.jwt_secret,
        algorithm=s.jwt_algoritmo,
    )
    r = client.get(ME, headers={"Authorization": f"Bearer {vencido}"})
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_INVALIDO"


def test_me_com_token_assinado_por_outra_chave(client, dados_demo) -> None:
    falso = jwt.encode(
        {"sub": str(dados_demo.admin_id), "exp": datetime.now(UTC) + timedelta(hours=1)},
        "outra-chave-com-tamanho-suficiente-para-hs256",
        algorithm="HS256",
    )
    r = client.get(ME, headers={"Authorization": f"Bearer {falso}"})
    assert r.status_code == 401


# --- Dependências -----------------------------------------------------------------------------


@pytest.fixture
def app_com_rotas_de_teste(db_session):
    """App com rotas fictícias para exercitar exige_papel e o bloqueio de escrita do AUDITOR."""
    app = criar_app()
    app.dependency_overrides[obter_sessao] = lambda: db_session

    @app.post("/teste/escrita")
    def escrita(u: Usuario = Depends(usuario_atual)) -> dict:
        return {"papel": u.papel}

    @app.get("/teste/so-fabricante")
    def so_fabricante(u: Usuario = Depends(exige_papel(Papel.FABRICANTE))) -> dict:
        return {"ok": True}

    with TestClient(app) as c:
        yield c


def test_auditor_nunca_escreve_em_rota_alguma(app_com_rotas_de_teste, auth) -> None:
    r = app_com_rotas_de_teste.post("/teste/escrita", headers=auth(EMAIL_AUDITOR))
    assert r.status_code == 403
    assert r.json()["codigo"] == "AUDITOR_SOMENTE_LEITURA"

    r = app_com_rotas_de_teste.post("/teste/escrita", headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 200


def test_exige_papel(app_com_rotas_de_teste, auth) -> None:
    assert (
        app_com_rotas_de_teste.get("/teste/so-fabricante", headers=auth(EMAIL_FABRICANTE)).status_code == 200
    )
    r = app_com_rotas_de_teste.get("/teste/so-fabricante", headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 403
    assert r.json()["codigo"] == "PAPEL_NAO_PERMITIDO"


def test_filtro_por_empresa(db_session, dados_demo) -> None:
    operador = db_session.get(Usuario, dados_demo.operador_id)
    auditor = db_session.get(Usuario, dados_demo.auditor_id)

    stmt = select(Empresa.id)
    assert set(db_session.scalars(filtrar_por_empresa(stmt, Empresa.id, operador))) == {
        dados_demo.desmonte_id
    }
    assert {dados_demo.desmonte_id, dados_demo.montadora_id} <= set(
        db_session.scalars(filtrar_por_empresa(stmt, Empresa.id, auditor))
    )

    garantir_acesso_empresa(operador, dados_demo.desmonte_id)
    garantir_acesso_empresa(auditor, dados_demo.montadora_id)
    with pytest.raises(ErroNegocio) as e:
        garantir_acesso_empresa(operador, dados_demo.montadora_id)
    assert e.value.status_code == 404
