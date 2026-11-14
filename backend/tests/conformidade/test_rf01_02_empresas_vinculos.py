"""RF-01 (arts. 11 e 16) e RF-02 (art. 13 §1º VI e §2º): empresas, credenciamento e vínculo."""

from datetime import date, timedelta

import pytest

from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FISCAL,
    OPERADOR,
    cnpj_aleatorio,
    emitir_certificado,
    erro,
    hojes,
    itens,
    ok,
    processar_veiculo,
)


def _empresa(tipo: str = "DESMONTADORA", **extra) -> dict:
    return {"cnpj": cnpj_aleatorio(), "razao_social": f"Empresa {tipo}", "tipo": tipo, **extra}


def _dois_anos(inicio: str) -> str:
    d = date.fromisoformat(inicio)
    return d.replace(year=d.year + 2).isoformat()


# --- RF-01 ----------------------------------------------------------------------------------


@pytest.mark.parametrize("tipo", ["FABRICANTE", "DESMONTADORA", "RECICLADORA"])
def test_rf01_cadastro_de_empresa_por_papel(api, tipo) -> None:
    corpo = _empresa(tipo)
    empresa = ok(api.post("/empresas", ADMIN, json=corpo))
    assert empresa["tipo"] == tipo
    assert empresa["cnpj"] == corpo["cnpj"]
    assert empresa["razao_social"] == corpo["razao_social"]
    listadas = itens(api.get("/empresas", ADMIN, params={"tipo": tipo, "tamanho": 100}))
    assert empresa["id"] in {e["id"] for e in listadas}
    assert {e["tipo"] for e in listadas} == {tipo}


def test_rf01_cnpj_unico(api) -> None:
    corpo = _empresa()
    ok(api.post("/empresas", ADMIN, json=corpo))
    erro(api.post("/empresas", ADMIN, json=corpo), 409)


def test_rf01_cnpj_invalido_rejeitado(api) -> None:
    erro(api.post("/empresas", ADMIN, json=_empresa() | {"cnpj": "11111111111111"}), 422)


@pytest.mark.parametrize("quem", [OPERADOR, FISCAL])
def test_rf01_somente_admin_cadastra_empresa(api, quem) -> None:
    erro(api.post("/empresas", quem, json=_empresa()), 403)


def test_rf01_credenciamento_com_situacao_e_validade(api) -> None:
    empresa = ok(api.post("/empresas", ADMIN, json=_empresa("RECICLADORA")))
    assert empresa["credenciamento_status"] == "PENDENTE"

    validade = (date.today() + timedelta(days=730)).isoformat()
    r = api.patch(
        f"/empresas/{empresa['id']}/credenciamento", ADMIN, json={"status": "ATIVO", "validade": validade}
    )
    credenciada = ok(r)
    assert credenciada["credenciamento_status"] == "ATIVO"
    assert credenciada["credenciamento_validade"] == validade

    suspensa = ok(
        api.patch(
            f"/empresas/{empresa['id']}/credenciamento",
            ADMIN,
            json={"status": "SUSPENSO", "validade": validade},
        )
    )
    assert suspensa["credenciamento_status"] == "SUSPENSO"


def test_rf01_credenciamento_lancado_so_pelo_admin(api, demo) -> None:
    corpo = {"status": "ATIVO", "validade": "2030-01-01"}
    erro(api.patch(f"/empresas/{demo.desmonte_id}/credenciamento", OPERADOR, json=corpo), 403)


def test_rf01_credenciamento_do_seed_vale_dois_anos(api, demo) -> None:
    """Art. 16: validade de 2 anos."""
    empresas = itens(api.get("/empresas", ADMIN, params={"tamanho": 100}))
    desmonte = next(e for e in empresas if e["id"] == str(demo.desmonte_id))
    assert desmonte["credenciamento_status"] == "ATIVO"
    assert desmonte["credenciamento_validade"] in {_dois_anos(h) for h in hojes()}


def test_rf01_fabricante_usa_registro_de_compromissos(api, demo) -> None:
    """Art. 8º II: o fabricante não é credenciado; tem ato de registro de compromissos."""
    fabricante = ok(api.post("/empresas", ADMIN, json=_empresa("FABRICANTE", registro_compromissos=False)))
    assert fabricante["registro_compromissos"] is False
    r = api.patch(f"/empresas/{fabricante['id']}", ADMIN, json={"registro_compromissos": True})
    assert ok(r)["registro_compromissos"] is True
    erro(api.patch(f"/empresas/{demo.desmonte_id}", ADMIN, json={"registro_compromissos": True}), 422)


@pytest.mark.parametrize("status", ["PENDENTE", "SUSPENSO", "CANCELADO"])
def test_rf01_sem_credenciamento_ativo_nao_emite_certificado(api, demo, status) -> None:
    """Art. 8º I: crédito só de empresa credenciada."""
    v = processar_veiculo(api)
    validade = (date.today() + timedelta(days=365)).isoformat()
    ok(
        api.patch(
            f"/empresas/{demo.desmonte_id}/credenciamento",
            ADMIN,
            json={"status": status, "validade": validade},
        )
    )
    corpo = erro(emitir_certificado(api, OPERADOR, v["id"]), 422, "PENDENCIAS_CERTIFICADO")
    assert corpo["pendencias"]


def test_rf01_credenciamento_vencido_nao_emite_certificado(api, demo, vencer_credenciamento) -> None:
    """Art. 16: credenciamento vale por prazo certo."""
    v = processar_veiculo(api)
    # Ninguém credencia com prazo já vencido: a API recusa (integração, caso a).
    ontem = (date.today() - timedelta(days=2)).isoformat()
    erro(
        api.patch(
            f"/empresas/{demo.desmonte_id}/credenciamento", ADMIN, json={"status": "ATIVO", "validade": ontem}
        ),
        422,
    )
    # O prazo vence com o tempo: a validade é recuada no banco (ver conftest.py).
    vencer_credenciamento(demo.desmonte_id)
    corpo = erro(emitir_certificado(api, OPERADOR, v["id"]), 422, "PENDENCIAS_CERTIFICADO")
    assert corpo["pendencias"]


# --- RF-02 ----------------------------------------------------------------------------------


def test_rf02_vinculo_entre_geradora_e_fabricante(api, demo, nova_empresa) -> None:
    recicladora = nova_empresa("RECICLADORA")
    r = api.post(
        "/vinculos", ADMIN, json={"geradora_id": recicladora.id, "fabricante_id": str(demo.montadora_id)}
    )
    vinculo = ok(r)
    assert vinculo["geradora_id"] == recicladora.id
    assert vinculo["fabricante_id"] == str(demo.montadora_id)
    assert vinculo["ativo"] is True


def test_rf02_vinculo_por_fabricante_e_par_unico(api, demo, nova_empresa) -> None:
    """Art. 13 §2º: uma declaração por fabricante; o mesmo par não se repete."""
    outro = nova_empresa("FABRICANTE")
    par = {"geradora_id": str(demo.desmonte_id), "fabricante_id": outro.id}
    ok(api.post("/vinculos", ADMIN, json=par))
    erro(api.post("/vinculos", ADMIN, json=par), 409)
    # O par do seed também já existe.
    par_seed = {"geradora_id": str(demo.desmonte_id), "fabricante_id": str(demo.montadora_id)}
    erro(api.post("/vinculos", ADMIN, json=par_seed), 409)


def test_rf02_vinculo_exige_geradora_e_fabricante_nos_papeis_certos(api, demo, nova_empresa) -> None:
    outra = nova_empresa("DESMONTADORA")
    invertido = {"geradora_id": str(demo.montadora_id), "fabricante_id": str(demo.desmonte_id)}
    erro(api.post("/vinculos", ADMIN, json=invertido), (409, 422))
    entre_geradoras = {"geradora_id": str(demo.desmonte_id), "fabricante_id": outra.id}
    erro(api.post("/vinculos", ADMIN, json=entre_geradoras), (409, 422))


@pytest.mark.parametrize("quem", [OPERADOR, FISCAL])
def test_rf02_somente_admin_lanca_vinculo(api, demo, nova_empresa, quem) -> None:
    outro = nova_empresa("FABRICANTE")
    par = {"geradora_id": str(demo.desmonte_id), "fabricante_id": outro.id}
    erro(api.post("/vinculos", quem, json=par), 403)


def test_rf02_lista_de_vinculos_filtrada_pela_empresa(api, demo, nova_empresa) -> None:
    alheia = nova_empresa("DESMONTADORA", vinculo_com=demo.montadora_id)

    da_desmonte = itens(api.get("/vinculos", OPERADOR, params={"tamanho": 100}))
    assert [v["id"] for v in da_desmonte] == [str(demo.vinculo_id)]

    da_alheia = itens(api.get("/vinculos", alheia.email, params={"tamanho": 100}))
    assert {v["geradora_id"] for v in da_alheia} == {alheia.id}

    da_montadora = itens(api.get("/vinculos", FISCAL, params={"tamanho": 100}))
    assert {v["geradora_id"] for v in da_montadora} == {str(demo.desmonte_id), alheia.id}

    todos = itens(api.get("/vinculos", AUDITOR, params={"tamanho": 100}))
    assert {v["geradora_id"] for v in todos} >= {str(demo.desmonte_id), alheia.id}


def test_rf02_vinculo_pode_ser_desativado(api, demo) -> None:
    vinculo = ok(api.patch(f"/vinculos/{demo.vinculo_id}", ADMIN, json={"ativo": False}))
    assert vinculo["ativo"] is False
    listado = itens(api.get("/vinculos", AUDITOR, params={"tamanho": 100}))
    assert next(v for v in listado if v["id"] == str(demo.vinculo_id))["ativo"] is False


def test_rf02_empresa_ve_so_contrapartes_com_vinculo(api, demo, nova_empresa) -> None:
    sem_vinculo = nova_empresa("FABRICANTE")
    vistas = {e["id"] for e in itens(api.get("/empresas", OPERADOR, params={"tamanho": 100}))}
    assert str(demo.montadora_id) in vistas
    assert sem_vinculo.id not in vistas
