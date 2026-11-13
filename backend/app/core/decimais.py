"""Arredondamento de valores de URV, preços e pesos.

Regra do projeto: Decimal sempre, nunca float; arredondamento ROUND_HALF_UP
(Anexo I, item 5: "se a terceira casa decimal for igual ou maior que 5,
arredonda-se a segunda casa decimal para cima").
"""

from decimal import ROUND_HALF_UP, Decimal

DUAS_CASAS = Decimal("0.01")
TRES_CASAS = Decimal("0.001")


def quantizar(valor: Decimal | int | str, casas: Decimal = DUAS_CASAS) -> Decimal:
    if isinstance(valor, float):
        raise TypeError("Use Decimal, não float.")
    return Decimal(valor).quantize(casas, rounding=ROUND_HALF_UP)


def quantizar_peso(valor: Decimal | int | str) -> Decimal:
    return quantizar(valor, TRES_CASAS)
