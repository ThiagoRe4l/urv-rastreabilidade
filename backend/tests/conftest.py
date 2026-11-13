"""Infraestrutura de teste compartilhada (dono: fundação).

- O banco de teste é PostgreSQL de verdade (gatilhos, JSONB e bloqueios consultivos não
  existem no SQLite). URL em TEST_DATABASE_URL; por padrão, o Postgres do docker compose
  em localhost:5432. O nome do banco recebe um sufixo derivado da pasta do projeto, para
  worktrees diferentes rodarem os testes ao mesmo tempo sem apagar o banco uma da outra.
- O banco é recriado e migrado (alembic upgrade head) uma vez por sessão do pytest.
- Cada teste roda dentro de uma transação desfeita no fim. `session.commit()` nas rotas
  vira um savepoint, então nada vaza entre testes. Não use TRUNCATE nem DELETE para
  limpar: `evento_auditoria` e `urv_lancamento` rejeitam as duas operações.

Fixtures: `engine`, `db_session`, `client`, `dados_demo`, `token`, `auth`.
"""

import os
from collections.abc import Callable, Iterator

# Antes de importar a aplicação: bcrypt rápido nos testes.
os.environ.setdefault("BCRYPT_ROUNDS", "4")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.main import criar_app
from scripts.seed import SENHA_DEMO, DadosDemo, semear
from tests.banco import recriar_banco, url_banco_teste


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = url_banco_teste()
    recriar_banco(url)
    eng = create_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Sessão dentro de uma transação externa, desfeita ao fim do teste."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = criar_app()
    app.dependency_overrides[obter_sessao] = lambda: db_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def dados_demo(db_session: Session) -> DadosDemo:
    """Usuários, empresas, vínculo, fatores e parâmetros do seed."""
    return semear(db_session)


@pytest.fixture
def token(client: TestClient, dados_demo: DadosDemo) -> Callable[[str], str]:
    """`token("admin@urv.local")` devolve um access_token (senha do seed)."""
    cache: dict[str, str] = {}

    def _token(email: str) -> str:
        if email not in cache:
            r = client.post("/api/v1/auth/login", json={"email": email, "senha": SENHA_DEMO})
            assert r.status_code == 200, r.text
            cache[email] = r.json()["access_token"]
        return cache[email]

    return _token


@pytest.fixture
def auth(token: Callable[[str], str]) -> Callable[[str], dict[str, str]]:
    """`client.get(url, headers=auth("admin@urv.local"))`."""
    return lambda email: {"Authorization": f"Bearer {token(email)}"}
