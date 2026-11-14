"""RNF-01 (art. 20 V; art. 24 I), RNF-02 (art. 20 VI), RNF-03 (art. 20 VII) e RNF-06 (art. 24 V)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.seed import SENHA_DEMO
from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FISCAL,
    OPERADOR,
    PREFIXO,
    dec,
    erro,
    gerar_credito,
    itens,
    ok,
    saldo,
    transferir,
)

ID = "{id}"

# Todas as rotas de docs/03-contrato-api.md.
CONTRATO = [
    ("POST", "/auth/login"),
    ("GET", "/auth/me"),
    ("POST", "/empresas"),
    ("GET", "/empresas"),
    ("PATCH", f"/empresas/{ID}"),
    ("PATCH", f"/empresas/{ID}/credenciamento"),
    ("POST", "/vinculos"),
    ("GET", "/vinculos"),
    ("PATCH", f"/vinculos/{ID}"),
    ("GET", "/auditoria/eventos"),
    ("GET", "/auditoria/verificar"),
    ("GET", "/configuracao/fatores"),
    ("POST", "/veiculos"),
    ("GET", "/veiculos"),
    ("GET", f"/veiculos/{ID}"),
    ("POST", f"/veiculos/{ID}/anexos"),
    ("GET", f"/anexos/{ID}/arquivo"),
    ("PUT", f"/veiculos/{ID}/etapas/RECEPCAO"),
    ("POST", f"/veiculos/{ID}/pecas"),
    ("PATCH", f"/pecas/{ID}"),
    ("GET", "/pecas"),
    ("GET", f"/pecas/rastreio/{ID}"),
    ("POST", f"/veiculos/{ID}/pesagens"),
    ("GET", f"/veiculos/{ID}/pesagens"),
    ("POST", f"/veiculos/{ID}/dmrs"),
    ("GET", f"/veiculos/{ID}/dmrs"),
    ("POST", f"/veiculos/{ID}/laudo"),
    ("POST", f"/veiculos/{ID}/certificado"),
    ("GET", "/certificados"),
    ("GET", f"/certificados/{ID}"),
    ("POST", "/mmvs"),
    ("GET", "/mmvs"),
    ("GET", "/urv/saldo"),
    ("GET", "/urv/extrato"),
    ("GET", "/urv/creditos"),
    ("POST", f"/urv/creditos/{ID}/transferir"),
    ("POST", "/urv/consumos/simular"),
    ("POST", "/urv/consumos"),
    ("GET", "/urv/consumos"),
    ("GET", "/relatorios/mdic"),
    ("GET", "/portabilidade/exportar"),
    ("POST", "/portabilidade/importar"),
]
PUBLICAS = {("POST", "/auth/login"), ("GET", f"/pecas/rastreio/{ID}")}
ESCRITAS = [(m, c) for m, c in CONTRATO if m != "GET" and (m, c) != ("POST", "/auth/login")]


def _concreto(caminho: str) -> str:
    return caminho.replace(ID, str(uuid.uuid4()))


def _id(rota: tuple[str, str]) -> str:
    return f"{rota[0]} {rota[1]}"


# --- RNF-03 ---------------------------------------------------------------------------------


def test_rnf03_openapi_publicado(client) -> None:
    """Padrão aberto: a especificação OpenAPI é servida pela própria API."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["openapi"].startswith("3.")
    assert f"{PREFIXO}/auth/login" in spec["paths"]


@pytest.mark.parametrize("rota", CONTRATO, ids=_id)
def test_rnf03_rota_do_contrato_existe(api, rota) -> None:
    """O OpenAPI deve refletir o contrato. Rota ausente fica pendente (xfail)."""
    api.exigir(rota[0], _concreto(rota[1]))


@pytest.mark.parametrize("rota", [r for r in CONTRATO if r not in PUBLICAS], ids=_id)
def test_rnf03_rota_exige_token(api, rota) -> None:
    metodo, caminho = rota
    erro(api.chamar(metodo, _concreto(caminho)), 401)
    falso = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.e30.assinatura-invalida"}
    erro(api.chamar(metodo, _concreto(caminho), headers=falso), 401)


def test_rnf03_token_com_assinatura_alterada_e_recusado(api, token) -> None:
    valido = token(ADMIN)
    cabecalho, corpo, assinatura = valido.split(".")
    adulterado = ".".join(
        [cabecalho, corpo, assinatura[:-4] + ("AAAA" if assinatura[-4:] != "AAAA" else "BBBB")]
    )
    erro(api.get("/auth/me", headers={"Authorization": f"Bearer {adulterado}"}), 401)
    assert api.get("/auth/me", headers={"Authorization": f"Bearer {valido}"}).status_code == 200


def test_rnf03_login_devolve_token_e_usuario(api, demo) -> None:
    r = api.post("/auth/login", json={"email": OPERADOR, "senha": SENHA_DEMO})
    corpo = ok(r)
    assert corpo["access_token"]
    assert corpo["usuario"]["papel"] == "DESMONTADORA"
    eu = ok(api.get("/auth/me", OPERADOR))
    assert eu["email"] == OPERADOR
    assert eu["empresa"]["id"] == str(demo.desmonte_id)


def test_rnf03_erros_seguem_o_formato_do_contrato(api) -> None:
    corpo = erro(api.get("/auditoria/eventos", OPERADOR), 403)
    assert isinstance(corpo["detail"], str) and corpo["detail"]
    assert isinstance(corpo["codigo"], str) and corpo["codigo"].isupper()


def test_rnf03_listas_paginadas(api) -> None:
    primeira = ok(api.get("/empresas", ADMIN, params={"pagina": 1, "tamanho": 1}))
    assert primeira["total"] == 2
    assert len(primeira["itens"]) == 1
    segunda = ok(api.get("/empresas", ADMIN, params={"pagina": 2, "tamanho": 1}))
    assert segunda["itens"][0]["id"] != primeira["itens"][0]["id"]


# --- RNF-02 ---------------------------------------------------------------------------------


@pytest.mark.parametrize("senha", ["errada123", ""])
def test_rnf02_login_com_senha_errada(api, senha) -> None:
    erro(api.post("/auth/login", json={"email": ADMIN, "senha": senha}), (401, 422))


def test_rnf02_login_nao_revela_se_o_email_existe(api) -> None:
    inexistente = api.post("/auth/login", json={"email": "ninguem@urv.local", "senha": SENHA_DEMO})
    senha_errada = api.post("/auth/login", json={"email": ADMIN, "senha": "errada123"})
    assert inexistente.status_code == senha_errada.status_code == 401
    assert inexistente.json() == senha_errada.json()


def test_rnf02_api_nao_expoe_senha_e_guarda_dados_pessoais_minimos(api) -> None:
    """Dados pessoais mínimos: do usuário, só nome e e-mail."""
    login = ok(api.post("/auth/login", json={"email": FISCAL, "senha": SENHA_DEMO}))
    eu = ok(api.get("/auth/me", FISCAL))
    assert "senha" not in str(login["usuario"]).lower()
    assert "senha" not in str(eu).lower()
    assert set(eu) <= {"id", "nome", "email", "papel", "empresa"}


def test_rnf02_trilha_nao_guarda_senha(api) -> None:
    eventos = ok(api.get("/auditoria/eventos", AUDITOR, params={"tipo": "USUARIO_CRIADO", "tamanho": 100}))
    assert eventos["total"] >= 4
    assert SENHA_DEMO not in str(eventos)
    assert "senha" not in str(eventos).lower()


# --- RNF-01 ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    ["UPDATE urv_lancamento SET quantidade = 999", "DELETE FROM urv_lancamento", "TRUNCATE urv_lancamento"],
)
def test_rnf01_livro_de_urv_e_so_de_insercao(api, db_session, demo, sql) -> None:
    """Imutabilidade: o saldo é a soma de lançamentos que o banco não deixa alterar."""
    _, cert = gerar_credito(api)
    ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))
    with pytest.raises(DBAPIError), db_session.begin_nested():
        db_session.execute(text(sql))
    assert saldo(api, FISCAL) == dec(cert["credito"]["quantidade"])
    assert len(itens(api.get("/urv/extrato", OPERADOR))) == 2


def test_rnf01_nao_ha_rota_para_alterar_ou_apagar_registros_do_livro_e_da_trilha(client) -> None:
    """Nenhuma rota de alteração ou exclusão sobre extrato, créditos, consumos, certificados e eventos."""
    protegidos = ("/urv/extrato", "/urv/consumos", "/certificados", "/auditoria", "/urv/saldo")
    for caminho, operacoes in client.app.openapi()["paths"].items():
        if any(caminho.startswith(PREFIXO + p) for p in protegidos):
            assert not set(operacoes) & {"put", "patch", "delete"}, caminho
        assert "delete" not in operacoes, caminho  # nada é apagado pela API


# --- RNF-06 ---------------------------------------------------------------------------------

LEITURAS_DO_MDIC = [
    "/empresas",
    "/vinculos",
    "/auditoria/eventos",
    "/auditoria/verificar",
    "/configuracao/fatores",
    "/veiculos",
    "/pecas",
    "/certificados",
    "/mmvs",
    "/urv/consumos",
    "/relatorios/mdic",
]


@pytest.mark.parametrize("rota", LEITURAS_DO_MDIC)
def test_rnf06_auditor_le_todas_as_consultas(api, rota) -> None:
    assert api.get(rota, AUDITOR).status_code == 200


def test_rnf06_auditor_consulta_o_extrato_de_qualquer_empresa(api, demo) -> None:
    for empresa_id in (demo.desmonte_id, demo.montadora_id):
        r = api.get("/urv/extrato", AUDITOR, params={"empresa_id": str(empresa_id)})
        assert r.status_code == 200


@pytest.mark.parametrize("rota", ESCRITAS, ids=_id)
def test_rnf06_auditor_e_somente_leitura(api, rota) -> None:
    """O MDIC supervisiona; não opera. 403 em qualquer escrita, em todas as rotas."""
    metodo, caminho = rota
    erro(api.chamar(metodo, _concreto(caminho), AUDITOR, json={}), 403, "AUDITOR_SOMENTE_LEITURA")
