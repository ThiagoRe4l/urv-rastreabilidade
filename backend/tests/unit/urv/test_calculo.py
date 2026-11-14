"""Funções puras do livro de URV. RF-18, RF-19 e RF-20."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.modules.urv.calculo import (
    ano_mes,
    calcular_debito,
    decimo_dia_util,
    multiplicador_preco,
    regularizar_ate,
    rm_do_nivel,
)
from app.modules.urv.relogio import data_operacao

PB = Decimal("150000.00")  # art. 3º §5º

# --- Débito (RF-18, art. 3º §3º) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("qv", "rm", "pm", "esperado"),
    [
        (1000, 10, "180000", "120.00"),  # casos obrigatórios de agents/02-backend-urv.md
        (1000, 5, "180000", "240.00"),
        (1000, 10, "90000", "100.00"),  # o multiplicador não fica abaixo de 1
        (7, 10, "150000", "0.70"),
        (1, 10, "150000", "0.10"),  # menor débito possível
        (1, 5, "150000", "0.20"),
        (3, 10, "450000.00", "0.90"),
    ],
)
def test_calcular_debito(qv: int, rm: int, pm: str, esperado: str) -> None:
    debito = calcular_debito(qv, rm, Decimal(pm), PB)
    assert debito == Decimal(esperado)
    assert str(debito) == esperado  # sempre duas casas


@pytest.mark.parametrize(
    ("qv", "rm", "pm", "esperado"),
    [
        (1, 10, "157500", "0.11"),  # 0.105: ROUND_HALF_EVEN daria 0.10
        (1, 5, "153750", "0.21"),  # 0.205: ROUND_HALF_EVEN daria 0.20
        (1, 10, "172500", "0.12"),  # 0.115
        (1, 10, "157499.99", "0.10"),  # 0.10499999...: logo abaixo da metade
        (1, 10, "166666.67", "0.11"),  # 0.1111111...
    ],
)
def test_calcular_debito_arredonda_meio_para_cima(qv: int, rm: int, pm: str, esperado: str) -> None:
    assert str(calcular_debito(qv, rm, Decimal(pm), PB)) == esperado


def test_calcular_debito_aceita_inteiro_e_string_mas_nao_float() -> None:
    assert calcular_debito(1000, 10, 180000, "150000.00") == Decimal("120.00")
    with pytest.raises(TypeError):
        calcular_debito(1000, 10, 180000.0, PB)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        calcular_debito(1000, 10, Decimal("180000"), 150000.0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("qv", "rm", "pm", "pb"),
    [(0, 10, "1", "1"), (-1, 10, "1", "1"), (True, 10, "1", "1"), (1, 7, "1", "1"), (1, 0, "1", "1")]
    + [(1, 10, "0", "1"), (1, 10, "-5", "1"), (1, 10, "1", "0")],
)
def test_calcular_debito_rejeita_entrada_invalida(qv, rm, pm, pb) -> None:
    with pytest.raises(ValueError):
        calcular_debito(qv, rm, Decimal(pm), Decimal(pb))


def test_multiplicador_de_preco_nunca_abaixo_de_um() -> None:
    assert multiplicador_preco(Decimal("90000"), PB) == Decimal(1)
    assert multiplicador_preco(Decimal("150000"), PB) == Decimal(1)
    assert multiplicador_preco(Decimal("180000"), PB) == Decimal("1.2")


def test_rm_do_nivel() -> None:
    assert rm_do_nivel(1) == 10  # item 18 do Anexo III do Decreto 12.435/2025
    assert rm_do_nivel(2) == 5  # item 17
    with pytest.raises(ValueError):
        rm_do_nivel(3)


# --- Prazo de reporte (RF-20, art. 7º, parágrafo único) ----------------------------------------


@pytest.mark.parametrize(
    ("periodo", "esperado"),
    [
        ("2026-10", date(2026, 11, 13)),  # novembro começa no domingo: 2 a 6 e 9 a 13
        ("2026-11", date(2026, 12, 14)),  # dezembro começa na terça
        ("2026-12", date(2027, 1, 14)),  # vira o ano; 1º/1 é sexta e conta (sem feriados)
        ("2027-04", date(2027, 5, 14)),  # maio começa no sábado
        ("2027-01", date(2027, 2, 12)),  # fevereiro começa na segunda: o mais cedo possível
    ],
)
def test_decimo_dia_util(periodo: str, esperado: date) -> None:
    prazo = decimo_dia_util(periodo)
    assert prazo == esperado
    assert prazo.weekday() < 5


def test_decimo_dia_util_conta_dez_dias_de_segunda_a_sexta() -> None:
    for ano in (2026, 2027, 2028):
        for mes in range(1, 13):
            prazo = decimo_dia_util(f"{ano}-{mes:02d}")
            uteis = [d for d in range(1, prazo.day + 1) if date(prazo.year, prazo.month, d).weekday() < 5]
            assert len(uteis) == 10
            assert (prazo.year, prazo.month) == ((ano, mes + 1) if mes < 12 else (ano + 1, 1))
            assert 12 <= prazo.day <= 14


@pytest.mark.parametrize("periodo", ["2026-13", "2026-00", "2026-1", "26-01", "2026/01", "", "2026-01-01"])
def test_periodo_invalido(periodo: str) -> None:
    with pytest.raises(ValueError):
        decimo_dia_util(periodo)
    with pytest.raises(ValueError):
        ano_mes(periodo)


# --- Regularização do saldo devedor (RF-19, art. 8º §1º) ---------------------------------------


@pytest.mark.parametrize(
    ("registro", "esperado"),
    [
        (date(2026, 11, 13), date(2027, 2, 28)),  # terceiro mês seguinte a novembro: fevereiro
        (date(2027, 1, 15), date(2027, 4, 30)),
        (date(2027, 11, 30), date(2028, 2, 29)),  # ano bissexto
        (date(2027, 12, 31), date(2028, 3, 31)),  # último dia da exceção
        (date(2027, 9, 1), date(2027, 12, 31)),
    ],
)
def test_regularizar_ate(registro: date, esperado: date) -> None:
    assert regularizar_ate(registro) == esperado


# --- Data da operação --------------------------------------------------------------------------


def test_data_da_operacao_e_a_de_brasilia() -> None:
    # 23h30 de 31/12/2027 em Brasília já é 1º/1/2028 em UTC.
    assert data_operacao(datetime(2028, 1, 1, 2, 30, tzinfo=UTC)) == date(2027, 12, 31)
    assert data_operacao(datetime(2028, 1, 1, 3, 0, tzinfo=UTC)) == date(2028, 1, 1)
    with pytest.raises(ValueError):
        data_operacao(datetime(2028, 1, 1, 3, 0))  # noqa: DTZ001
