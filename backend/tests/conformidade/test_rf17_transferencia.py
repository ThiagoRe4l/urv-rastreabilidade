"""RF-17 (art. 8º II e §3º): transferência direta e única, só a fabricante com vínculo."""

import pytest

from tests.conformidade.apoio import (
    ADMIN,
    FISCAL,
    OPERADOR,
    dec,
    erro,
    gerar_credito,
    itens,
    ok,
    saldo,
    transferir,
)


def _credito(api, credito_id: str, quem: str = OPERADOR) -> dict:
    return next(c for c in itens(api.get("/urv/creditos", quem)) if c["id"] == credito_id)


def test_rf17_transferencia_direta_e_unica(api, demo) -> None:
    _, cert = gerar_credito(api, tipo="SINISTRADO_GRANDE")  # 0,79
    credito = ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))
    assert credito["status"] == "TRANSFERIDO"
    assert credito["titular_id"] == str(demo.montadora_id)  # o fabricante adquire a titularidade
    assert credito["geradora_id"] == str(demo.desmonte_id)
    assert dec(credito["quantidade"]) == dec("0.79")  # crédito indivisível, transferido inteiro
    assert saldo(api, OPERADOR) == 0
    assert saldo(api, FISCAL) == dec("0.79")

    erro(transferir(api, OPERADOR, credito["id"], demo.montadora_id), 409, "CREDITO_JA_TRANSFERIDO")
    assert saldo(api, OPERADOR) == 0
    assert saldo(api, FISCAL) == dec("0.79")


def test_rf17_transferencia_gera_saida_e_entrada_no_livro(api, demo) -> None:
    _, cert = gerar_credito(api)  # 0,38
    ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))

    da_geradora = {x["tipo"]: x for x in itens(api.get("/urv/extrato", OPERADOR))}
    assert set(da_geradora) == {"CREDITO", "TRANSFERENCIA_SAIDA"}
    assert dec(da_geradora["CREDITO"]["quantidade"]) == dec("0.38")
    assert dec(da_geradora["TRANSFERENCIA_SAIDA"]["quantidade"]) == dec("-0.38")
    assert da_geradora["TRANSFERENCIA_SAIDA"]["contraparte_id"] == str(demo.montadora_id)

    do_fabricante = itens(api.get("/urv/extrato", FISCAL))
    assert [x["tipo"] for x in do_fabricante] == ["TRANSFERENCIA_ENTRADA"]
    assert dec(do_fabricante[0]["quantidade"]) == dec("0.38")
    assert do_fabricante[0]["contraparte_id"] == str(demo.desmonte_id)


def test_rf17_fabricante_ve_o_credito_recebido(api, demo) -> None:
    v, cert = gerar_credito(api)
    ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))
    recebidos = itens(api.get("/urv/creditos", FISCAL))
    assert [c["id"] for c in recebidos] == [cert["credito"]["id"]]
    assert v["chassi"] in str(recebidos[0])
    assert _credito(api, cert["credito"]["id"])["status"] == "TRANSFERIDO"


def test_rf17_fabricante_sem_vinculo_nao_recebe(api, nova_empresa) -> None:
    """Art. 8º II: fabricantes 'com os quais foi atestado vínculo'."""
    sem_vinculo = nova_empresa("FABRICANTE")
    _, cert = gerar_credito(api)
    erro(transferir(api, OPERADOR, cert["credito"]["id"], sem_vinculo.id), 422, "SEM_VINCULO")
    assert _credito(api, cert["credito"]["id"])["status"] == "DISPONIVEL"
    assert saldo(api, OPERADOR) == dec("0.38")
    assert saldo(api, sem_vinculo.email) == 0


def test_rf17_vinculo_inativo_nao_vale(api, demo) -> None:
    _, cert = gerar_credito(api)
    ok(api.patch(f"/vinculos/{demo.vinculo_id}", ADMIN, json={"ativo": False}))
    erro(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id), 422, "SEM_VINCULO")
    assert saldo(api, FISCAL) == 0


def test_rf17_fabricante_sem_registro_de_compromissos_nao_recebe(api, demo, nova_empresa) -> None:
    """Art. 8º II: 'que possuam ato de registro de compromissos junto ao MDIC'."""
    sem_registro = nova_empresa("FABRICANTE", registro_compromissos=False, vinculo_com=demo.desmonte_id)
    _, cert = gerar_credito(api)
    erro(  # PM-URV-04
        transferir(api, OPERADOR, cert["credito"]["id"], sem_registro.id),
        422,
        "FABRICANTE_SEM_REGISTRO_COMPROMISSOS",
    )
    assert _credito(api, cert["credito"]["id"])["status"] == "DISPONIVEL"
    assert saldo(api, sem_registro.email) == 0


def test_rf17_intermediacao_vedada_fabricante_nao_repassa(api, demo, nova_empresa) -> None:
    """Art. 8º §3º: só da geradora ao fabricante consumidor; o fabricante não repassa o crédito."""
    outro = nova_empresa("FABRICANTE", vinculo_com=demo.desmonte_id)
    _, cert = gerar_credito(api)
    ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))
    erro(transferir(api, FISCAL, cert["credito"]["id"], outro.id), 403)
    assert saldo(api, FISCAL) == dec("0.38")
    assert saldo(api, outro.email) == 0


def test_rf17_intermediacao_vedada_destino_e_sempre_fabricante(api, demo, nova_empresa) -> None:
    """Uma desmontadora ou recicladora não recebe crédito de outra."""
    intermediaria = nova_empresa("RECICLADORA", vinculo_com=demo.montadora_id)
    _, cert = gerar_credito(api)
    erro(transferir(api, OPERADOR, cert["credito"]["id"], intermediaria.id), (404, 409, 422))
    assert saldo(api, OPERADOR) == dec("0.38")
    assert saldo(api, intermediaria.email) == 0


def test_rf17_so_a_geradora_transfere_o_proprio_credito(api, demo, nova_empresa) -> None:
    alheia = nova_empresa("DESMONTADORA", vinculo_com=demo.montadora_id)
    _, cert = gerar_credito(api)
    erro(transferir(api, alheia.email, cert["credito"]["id"], demo.montadora_id), (403, 404))
    assert _credito(api, cert["credito"]["id"])["status"] == "DISPONIVEL"
    assert saldo(api, FISCAL) == 0


@pytest.mark.parametrize("quem", [ADMIN])
def test_rf17_admin_nao_transfere_credito(api, demo, quem) -> None:
    """Art. 8º §3º: o operador da plataforma também é terceiro."""
    _, cert = gerar_credito(api)
    erro(transferir(api, quem, cert["credito"]["id"], demo.montadora_id), 403)
    assert saldo(api, FISCAL) == 0
