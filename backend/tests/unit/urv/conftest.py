"""Fixtures dos testes do agente 02 (backend-urv). As gerais estão em tests/conftest.py."""

from collections.abc import Callable
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Mmv, Usuario
from app.modules.urv.relogio import agora
from scripts.seed import DadosDemo
from tests.unit.urv.apoio import HOJE, criar_mmv


@pytest.fixture
def relogio(client: TestClient) -> Callable[[datetime], None]:
    """`relogio(momento)` fixa o momento das operações nas rotas. Começa em `HOJE`."""

    def _fixar(momento: datetime) -> None:
        client.app.dependency_overrides[agora] = lambda: momento

    _fixar(HOJE)
    return _fixar


@pytest.fixture
def operador(db_session: Session, dados_demo: DadosDemo) -> Usuario:
    """Usuário da desmontadora credenciada do seed."""
    return db_session.get(Usuario, dados_demo.operador_id)


@pytest.fixture
def fiscal(db_session: Session, dados_demo: DadosDemo) -> Usuario:
    """Usuário do fabricante do seed."""
    return db_session.get(Usuario, dados_demo.fiscal_id)


@pytest.fixture
def mmv(db_session: Session, dados_demo: DadosDemo) -> Mmv:
    """MMV nível 1 (RM 10) do fabricante do seed, já com efeitos."""
    return criar_mmv(db_session, dados_demo.montadora_id)
