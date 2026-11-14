"""Relógio das regras de negócio (PM-URV-06).

As datas da portaria valem no horário de Brasília, não em UTC: a validade do credenciamento
(art. 16), a meta do ano no certificado (art. 18 §7º), a vigência dos fatores (art. 3º §6º),
31/12/2027 do art. 8º §1º, 1º de janeiro do art. 5º §2º e o décimo dia útil do art. 7º. No
container o relógio é UTC: entre 21h e 0h de Brasília, `date.today()` já devolveria o dia
seguinte. O Brasil não adota horário de verão desde 2019, então o fuso é fixo em UTC-3 e
dispensa a base de fusos do sistema.

Regra: nenhuma regra de negócio usa `date.today()`. Rotas recebem o momento por
`Depends(agora)` (os testes o trocam); o que não é rota usa `hoje()`.
"""

from datetime import UTC, date, datetime, timedelta, timezone

FUSO_BRASILIA = timezone(timedelta(hours=-3), "BRT")


def agora() -> datetime:
    """Momento da operação. É dependência FastAPI: os testes a trocam para simular datas."""
    return datetime.now(UTC)


def data_operacao(momento: datetime) -> date:
    """Data civil, em Brasília, de um momento com fuso."""
    if momento.tzinfo is None:
        raise ValueError("O momento da operação precisa de fuso horário.")
    return momento.astimezone(FUSO_BRASILIA).date()


def hoje() -> date:
    """Data civil de agora, em Brasília. Para validações fora de rota (schemas, scripts)."""
    return data_operacao(datetime.now(UTC))


def inicio_do_dia(dia: date) -> datetime:
    """Meia-noite de Brasília do dia informado."""
    return datetime(dia.year, dia.month, dia.day, tzinfo=FUSO_BRASILIA)
