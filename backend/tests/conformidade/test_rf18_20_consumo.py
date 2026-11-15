"""RF-18 (art. 3º §3º; art. 8º III), RF-19 (art. 8º III e §1º) e RF-20 (art. 7º parágrafo único)."""

from datetime import UTC, date, datetime

import pytest

from tests.conformidade.apoio import (
    ADMIN,
    FISCAL,
    OPERADOR,
    chassis,
    consumir,
    criar_mmv,
    dec,
    decimo_dia_util_do_mes_seguinte,
    erro,
    gerar_credito,
    itens,
    ok,
    periodo_atual,
    saldo,
    transferir,
    ultimo_dia_do_terceiro_mes_seguinte,
)


def _dar_saldo(api, demo, tipo: str = "LICENCIADO_RODAGEM") -> None:
    """Gera um crédito na desmontadora do seed e o transfere à montadora do seed."""
    _, cert = gerar_credito(api, tipo=tipo)
    ok(transferir(api, OPERADOR, cert["credito"]["id"], demo.montadora_id))


def _simular(api, mmv_id: str, quantidade: int, preco_medio: str, quem: str = FISCAL):
    corpo = {"mmv_id": mmv_id, "quantidade": quantidade, "preco_medio": preco_medio}
    return api.post("/urv/consumos/simular", quem, json=corpo)


def _prazos_de_regularizacao() -> set[str]:
    return {
        ultimo_dia_do_terceiro_mes_seguinte(d).isoformat() for d in (date.today(), datetime.now(UTC).date())
    }


# --- RF-18 ----------------------------------------------------------------------------------

# URV débito = (Qv / RM) × max(1, Pm / Pb), com Pb = 150.000,00; duas casas, ROUND_HALF_UP.
# Os casos são por RM, não por nível: qual nível usa RM 5 e qual usa RM 10 é parâmetro em
# config_parametro (nível 1 = 10, nível 2 = 5: Decreto 12.435/2025, Anexo III, itens 18 e 17).
CASOS_DE_DEBITO = [
    (10, 10, "150000.00", "1.00"),  # 10 veículos no preço base, RM 10: 1 URV
    (10, 3, "150000.00", "0.30"),
    (10, 3, "90000.00", "0.30"),  # preço abaixo da base não reduz o débito: max(1, Pm/Pb)
    (10, 10, "300000.00", "2.00"),  # o dobro do preço base dobra o débito
    (5, 5, "150000.00", "1.00"),  # RM 5
    (5, 1, "150000.00", "0.20"),
    (5, 1, "200000.00", "0.27"),  # 0,2 × 1,3333… = 0,2666…
    (5, 7, "175000.00", "1.63"),  # 1,4 × 1,1666… = 1,6333…
    (10, 1, "157500.00", "0.11"),  # 0,1 × 1,05 = 0,105: HALF_UP dá 0,11 (HALF_EVEN daria 0,10)
    (10, 1, "172500.00", "0.12"),  # 0,1 × 1,15 = 0,115: HALF_UP dá 0,12
    (10, 1, "100000.00", "0.10"),
    (10, 250, "189990.00", "31.67"),  # 25 × 1,2666 = 31,665: HALF_UP dá 31,67
]


def _mmv_com_rm(api, rm: int) -> dict:
    """MMV do nível que, na configuração vigente, usa este RM (art. 3º §3º: 5 ou 10)."""
    for nivel in (1, 2):
        mmv = criar_mmv(api, nivel=nivel)
        if mmv["rm"] == rm:
            return mmv
    raise AssertionError(f"Nenhum nível usa RM {rm}")


@pytest.mark.parametrize(("rm", "qv", "pm", "esperado"), CASOS_DE_DEBITO)
def test_rf18_calculo_do_debito_por_mmv(api, rm, qv, pm, esperado) -> None:
    mmv = _mmv_com_rm(api, rm)
    simulacao = ok(_simular(api, mmv["id"], qv, pm))
    assert dec(simulacao["urv_debito"]) == dec(esperado)
    assert isinstance(simulacao["urv_debito"], str)
    assert dec(simulacao["saldo_apos"]) == -dec(esperado)


def test_rf18_simulacao_nao_grava_nada(api) -> None:
    mmv = criar_mmv(api)
    ok(_simular(api, mmv["id"], 10, "150000.00"))
    assert saldo(api, FISCAL) == 0
    assert itens(api.get("/urv/consumos", FISCAL)) == []
    assert itens(api.get("/urv/extrato", FISCAL)) == []


def test_rf18_consumo_por_chassi_baixa_o_saldo(api, demo) -> None:
    """Art. 8º III: o débito se dá pela indicação dos chassis dos veículos novos."""
    _dar_saldo(api, demo)  # 1,00
    mmv = criar_mmv(api, nivel=1)
    vendidos = chassis(3)
    consumo = ok(consumir(api, FISCAL, mmv["id"], vendidos))
    assert consumo["mmv_id"] == mmv["id"]
    assert consumo["periodo"] == periodo_atual()
    assert dec(consumo["qv"]) == 3
    assert dec(consumo["rm"]) == 10
    assert dec(consumo["pm"]) == dec("150000.00")
    assert dec(consumo["pb"]) == dec("150000.00")
    assert dec(consumo["urv_debito"]) == dec("0.30")
    assert dec(consumo["saldo_apos"]) == dec("0.70")
    assert saldo(api, FISCAL) == dec("0.70")

    debitos = [x for x in itens(api.get("/urv/extrato", FISCAL)) if x["tipo"] == "DEBITO"]
    assert [dec(x["quantidade"]) for x in debitos] == [dec("-0.30")]
    listado = itens(api.get("/urv/consumos", FISCAL))
    assert [c["id"] for c in listado] == [consumo["id"]]


def test_rf18_consumo_usa_preco_medio_e_nivel_do_mmv(api) -> None:
    mmv = criar_mmv(api, nivel=2)
    consumo = ok(consumir(api, FISCAL, mmv["id"], chassis(7), preco_medio="175000.00"))
    assert dec(consumo["rm"]) == 5
    assert dec(consumo["urv_debito"]) == dec("1.63")
    assert saldo(api, FISCAL) == dec("-1.63")


@pytest.mark.parametrize(
    "alteracao",
    [
        {"chassis": []},
        {"preco_medio": "0"},
        {"preco_medio": "-1.00"},
        {"periodo": "2026-13"},
        {"periodo": "11/2026"},
    ],
    ids=lambda a: "-".join(f"{k}={v}" for k, v in a.items()),
)
def test_rf18_consumo_invalido_rejeitado(api, alteracao) -> None:
    mmv = criar_mmv(api)
    corpo = {
        "mmv_id": mmv["id"],
        "periodo": periodo_atual(),
        "preco_medio": "150000.00",
        "chassis": chassis(1),
    } | alteracao
    erro(api.post("/urv/consumos", FISCAL, json=corpo), 422)
    assert saldo(api, FISCAL) == 0


def test_rf18_fabricante_nao_consome_com_mmv_de_outro(api, nova_empresa) -> None:
    outro = nova_empresa("FABRICANTE")
    mmv_alheio = criar_mmv(api, outro.email)
    erro(consumir(api, FISCAL, mmv_alheio["id"], chassis(1)), (403, 404, 422))
    assert saldo(api, FISCAL) == 0
    assert saldo(api, outro.email) == 0


@pytest.mark.parametrize("quem", [OPERADOR, ADMIN])
def test_rf18_somente_fabricante_consome(api, quem) -> None:
    mmv = criar_mmv(api)
    erro(consumir(api, quem, mmv["id"], chassis(1)), 403)


def test_rf18_consumos_visiveis_so_ao_proprio_fabricante(api, nova_empresa) -> None:
    outro = nova_empresa("FABRICANTE")
    meu = ok(consumir(api, FISCAL, criar_mmv(api)["id"], chassis(1)))
    alheio = ok(consumir(api, outro.email, criar_mmv(api, outro.email)["id"], chassis(1)))
    assert [c["id"] for c in itens(api.get("/urv/consumos", FISCAL))] == [meu["id"]]
    assert [c["id"] for c in itens(api.get("/urv/consumos", outro.email))] == [alheio["id"]]
    erro(api.get("/urv/consumos", OPERADOR), 403)


# --- RF-19 ----------------------------------------------------------------------------------


def test_rf19_saldo_negativo_ate_2027(api) -> None:
    """Art. 8º §1º: até 31/12/2027, admite-se saldo devedor, com prazo de regularização."""
    mmv = criar_mmv(api)
    assert ok(api.get("/urv/saldo", FISCAL)).get("regularizar_ate") is None

    consumo = ok(consumir(api, FISCAL, mmv["id"], chassis(10)))
    assert dec(consumo["urv_debito"]) == dec("1.00")
    assert dec(consumo["saldo_apos"]) == dec("-1.00")
    assert consumo["regularizar_ate"] in _prazos_de_regularizacao()

    posicao = ok(api.get("/urv/saldo", FISCAL))
    assert dec(posicao["saldo"]) == dec("-1.00")
    assert posicao["regularizar_ate"] in _prazos_de_regularizacao()


def test_rf19_prazo_de_regularizacao_e_o_ultimo_dia_do_terceiro_mes() -> None:
    """Confere a régua usada acima contra datas fixas."""
    assert ultimo_dia_do_terceiro_mes_seguinte(date(2026, 11, 13)) == date(2027, 2, 28)
    assert ultimo_dia_do_terceiro_mes_seguinte(date(2027, 11, 30)) == date(2028, 2, 29)
    assert ultimo_dia_do_terceiro_mes_seguinte(date(2027, 9, 1)) == date(2027, 12, 31)
    assert ultimo_dia_do_terceiro_mes_seguinte(date(2027, 12, 31)) == date(2028, 3, 31)


def test_rf19_consumo_com_saldo_suficiente_nao_tem_regularizacao(api, demo) -> None:
    _dar_saldo(api, demo)  # 1,00
    consumo = ok(consumir(api, FISCAL, criar_mmv(api)["id"], chassis(10)))  # 1,00
    assert dec(consumo["saldo_apos"]) == 0
    assert consumo["regularizar_ate"] is None
    assert ok(api.get("/urv/saldo", FISCAL)).get("regularizar_ate") is None


def test_rf19_saldo_devedor_regularizado_por_nova_transferencia(api, demo) -> None:
    ok(consumir(api, FISCAL, criar_mmv(api)["id"], chassis(5)))  # -0,50
    assert ok(api.get("/urv/saldo", FISCAL))["regularizar_ate"]
    _dar_saldo(api, demo)  # +1,00
    posicao = ok(api.get("/urv/saldo", FISCAL))
    assert dec(posicao["saldo"]) == dec("0.50")
    assert posicao.get("regularizar_ate") is None


def test_rf19_saldo_negativo_bloqueado_depois_de_2027(api, demo, encerrar_saldo_negativo) -> None:
    """Art. 8º III: vedada a operação que resulte em saldo negativo."""
    _dar_saldo(api, demo, tipo="SUCATA_INSERVIVEL")  # 0,38
    mmv = criar_mmv(api)
    encerrar_saldo_negativo()

    erro(consumir(api, FISCAL, mmv["id"], chassis(4)), 409, "SALDO_INSUFICIENTE")  # 0,40 > 0,38
    assert saldo(api, FISCAL) == dec("0.38")
    assert itens(api.get("/urv/consumos", FISCAL)) == []


def test_rf19_sem_saldo_previo_nao_consome_depois_de_2027(api, encerrar_saldo_negativo) -> None:
    """Art. 8º III: o débito fica condicionado à existência de saldo previamente adquirido."""
    mmv = criar_mmv(api)
    encerrar_saldo_negativo()
    erro(consumir(api, FISCAL, mmv["id"], chassis(1)), 409, "SALDO_INSUFICIENTE")
    assert saldo(api, FISCAL) == 0


def test_rf19_com_saldo_suficiente_consome_depois_de_2027(api, demo, encerrar_saldo_negativo) -> None:
    _dar_saldo(api, demo, tipo="SUCATA_INSERVIVEL")  # 0,38
    mmv = criar_mmv(api)
    encerrar_saldo_negativo()

    consumo = ok(consumir(api, FISCAL, mmv["id"], chassis(3)))  # 0,30
    assert dec(consumo["saldo_apos"]) == dec("0.08")
    assert consumo["regularizar_ate"] is None
    # Chassi rejeitado antes por falta de saldo não fica "queimado".
    rejeitados = chassis(1)
    erro(consumir(api, FISCAL, mmv["id"], rejeitados), 409, "SALDO_INSUFICIENTE")  # 0,10 > 0,08


# --- RF-20 ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("periodo", "prazo"),
    [
        ("2026-09", date(2026, 10, 14)),
        ("2026-10", date(2026, 11, 13)),
        ("2026-12", date(2027, 1, 14)),  # 1º/1/2027 é sexta e conta: não há calendário de feriados
        ("2027-01", date(2027, 2, 12)),
        ("2027-04", date(2027, 5, 14)),  # maio de 2027 começa num sábado
    ],
)
def test_rf20_decimo_dia_util_do_mes_seguinte(periodo, prazo) -> None:
    """Confere a régua usada abaixo contra datas contadas à mão (segunda a sexta)."""
    assert decimo_dia_util_do_mes_seguinte(periodo) == prazo


def test_rf20_consumo_do_mes_corrente_esta_no_prazo(api) -> None:
    consumo = ok(consumir(api, FISCAL, criar_mmv(api)["id"], chassis(1)))
    assert consumo["prazo_reporte"] == decimo_dia_util_do_mes_seguinte(periodo_atual()).isoformat()
    assert consumo["fora_do_prazo"] is False
    assert itens(api.get("/urv/consumos", FISCAL))[0]["fora_do_prazo"] is False


def test_rf20_reporte_atrasado_e_aceito_e_marcado(api, antecipar_efeitos_mmv) -> None:
    """O atraso é alerta, não bloqueio. Período de janeiro de 2026: prazo em 13/02/2026."""
    mmv = criar_mmv(api)
    antecipar_efeitos_mmv(mmv["id"], date(2026, 1, 1))
    consumo = ok(consumir(api, FISCAL, mmv["id"], chassis(1), periodo="2026-01"))
    assert consumo["periodo"] == "2026-01"
    assert consumo["prazo_reporte"] == "2026-02-13"
    assert consumo["fora_do_prazo"] is True
    assert itens(api.get("/urv/consumos", FISCAL))[0]["fora_do_prazo"] is True
