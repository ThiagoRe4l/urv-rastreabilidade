"""Criação e remoção do banco de teste. Usado por conftest.py e por testes que precisam de commit real."""

import hashlib
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
_SUFIXO = hashlib.sha1(str(BACKEND_DIR).encode(), usedforsecurity=False).hexdigest()[:8]


def url_banco_teste(sufixo: str = "") -> str:
    base = make_url(
        os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://urv:urv@localhost:5432/urv_test")
    )
    return base.set(database=f"{base.database}_{_SUFIXO}{sufixo}").render_as_string(hide_password=False)


def recriar_banco(url: str) -> None:
    """Apaga e cria o banco vazio, depois aplica as migrações."""
    alvo = make_url(url)
    admin = create_engine(alvo.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{alvo.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{alvo.database}"'))
    admin.dispose()

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    cfg.attributes["configurar_log"] = False
    command.upgrade(cfg, "head")


def apagar_banco(url: str) -> None:
    alvo = make_url(url)
    admin = create_engine(alvo.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{alvo.database}" WITH (FORCE)'))
    admin.dispose()
