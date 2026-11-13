"""Normalização e validação de CNPJ (dígitos verificadores)."""

import re

_PESOS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_2 = [6, *_PESOS_1]


def normalizar_cnpj(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _digito(numeros: str, pesos: list[int]) -> str:
    resto = sum(int(n) * p for n, p in zip(numeros, pesos, strict=True)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(valor: str) -> bool:
    cnpj = normalizar_cnpj(valor)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    d1 = _digito(cnpj[:12], _PESOS_1)
    d2 = _digito(cnpj[:12] + d1, _PESOS_2)
    return cnpj[12:] == d1 + d2


def formatar_cnpj(valor: str) -> str:
    c = normalizar_cnpj(valor)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else valor
