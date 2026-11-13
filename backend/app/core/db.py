"""Engine e sessão do SQLAlchemy (síncrono).

Convenção de transação: services nunca fazem commit; quem faz é a rota,
depois de todas as escritas e do `registrar_evento`. Assim o evento de
auditoria e a escrita de negócio entram juntos ou não entram.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def obter_sessao() -> Iterator[Session]:
    """Dependência FastAPI. Sem commit explícito, o fechamento desfaz a transação."""
    with SessionLocal() as session:
        yield session
