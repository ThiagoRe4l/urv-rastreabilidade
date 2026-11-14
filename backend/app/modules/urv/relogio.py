"""Relógio das operações de URV.

As datas-limite da portaria (31/12/2027 do art. 8º §1º, 1º de janeiro do art. 5º §2º, décimo
dia útil do art. 7º) valem no horário de Brasília, não em UTC: um consumo registrado às 22h
de 31/12/2027 ainda é de 2027. O Brasil não adota horário de verão desde 2019, então o fuso
é fixo em UTC-3 e dispensa a base de fusos do sistema.
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


def inicio_do_dia(dia: date) -> datetime:
    """Meia-noite de Brasília do dia informado."""
    return datetime(dia.year, dia.month, dia.day, tzinfo=FUSO_BRASILIA)
