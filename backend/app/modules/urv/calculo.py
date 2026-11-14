"""Funções puras do livro de URV: débito e prazos. Sem banco, sem relógio.

O RM de cada nível não está aqui: é parâmetro com vigência em `config_parametro`
(`RM_NIVEL_1`, `RM_NIVEL_2`), lido por `app.core.configuracao.rm_vigente` (lacuna L-01).

Tudo aqui usa `Decimal` e `ROUND_HALF_UP` (regra do projeto; Anexo I, item 5).
"""

import re
from calendar import monthrange
from datetime import date
from decimal import Decimal, localcontext

from app.core.decimais import quantizar

# Art. 3º §3º: "conforme item 17 ou 18 do Anexo III ao Decreto nº 12.435, de 2025 (5 ou 10,
# respectivamente)". Os dois valores possíveis são certos; qual nível usa qual é parâmetro (L-01).
RMS_DA_PORTARIA: frozenset[int] = frozenset({5, 10})

_PERIODO = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")

DIAS_UTEIS_REPORTE = 10  # art. 7º, parágrafo único
MESES_REGULARIZACAO = 3  # art. 8º §1º


def multiplicador_preco(pm: Decimal, pb: Decimal) -> Decimal:
    """`max(1, pm / pb)`: o preço médio abaixo do preço base não reduz o débito. Art. 3º §3º."""
    return max(Decimal(1), Decimal(pm) / Decimal(pb))


def calcular_debito(qv: int, rm: int, pm: Decimal | int | str, pb: Decimal | int | str) -> Decimal:
    """URV exigida para compensar veículos novos. RF-18, art. 3º §3º.

        urv_debito = (qv / rm) * max(1, pm / pb)      # duas casas, ROUND_HALF_UP

    `qv`: veículos comercializados do MMV; `rm`: 5 ou 10; `pm`: preço médio; `pb`: preço base.
    """
    if isinstance(pm, float) or isinstance(pb, float):
        raise TypeError("Use Decimal, não float.")
    if isinstance(qv, bool) or not isinstance(qv, int) or qv <= 0:
        raise ValueError("qv precisa ser um inteiro positivo.")
    if rm not in RMS_DA_PORTARIA:
        raise ValueError("rm precisa ser 5 ou 10 (art. 3º §3º).")
    pm, pb = Decimal(pm), Decimal(pb)
    if pm <= 0 or pb <= 0:
        raise ValueError("pm e pb precisam ser positivos.")
    with localcontext() as ctx:
        ctx.prec = 50
        # (qv / rm) * max(1, pm / pb) == qv * max(pm, pb) / (rm * pb): uma única divisão,
        # para que nenhum arredondamento intermediário chegue à terceira casa.
        bruto = Decimal(qv) * max(pm, pb) / (Decimal(rm) * pb)
    return quantizar(bruto)


def ano_mes(periodo: str) -> tuple[int, int]:
    """Converte "AAAA-MM" em (ano, mês)."""
    m = _PERIODO.match(periodo or "")
    if m is None:
        raise ValueError(f"Período inválido: {periodo!r} (use AAAA-MM).")
    return int(m.group(1)), int(m.group(2))


def _somar_meses(ano: int, mes: int, meses: int) -> tuple[int, int]:
    indice = ano * 12 + (mes - 1) + meses
    return indice // 12, indice % 12 + 1


def decimo_dia_util(periodo: str) -> date:
    """Prazo de reporte do consumo: décimo dia útil do mês seguinte ao período. RF-20, art. 7º.

    Dia útil = segunda a sexta, sem calendário de feriados (premissa de docs/01-requisitos.md).
    """
    ano, mes = _somar_meses(*ano_mes(periodo), 1)
    uteis = 0
    for dia in range(1, monthrange(ano, mes)[1] + 1):
        candidato = date(ano, mes, dia)
        if candidato.weekday() < 5:
            uteis += 1
            if uteis == DIAS_UTEIS_REPORTE:
                return candidato
    raise AssertionError("Todo mês tem ao menos dez dias úteis.")  # pragma: no cover


def regularizar_ate(data_registro: date) -> date:
    """Último dia do terceiro mês seguinte ao do registro do consumo. RF-19, art. 8º §1º."""
    ano, mes = _somar_meses(data_registro.year, data_registro.month, MESES_REGULARIZACAO)
    return date(ano, mes, monthrange(ano, mes)[1])
