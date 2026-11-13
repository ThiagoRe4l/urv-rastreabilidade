"""Configuração da aplicação, lida de variáveis de ambiente."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://urv:urv@localhost:5432/urv"

    jwt_secret: str = "troque-este-segredo-fora-do-ambiente-local"  # noqa: S105 (só para ambiente local)
    jwt_algoritmo: str = "HS256"
    jwt_expira_minutos: int = 480
    bcrypt_rounds: int = 12

    upload_dir: str = "/data/uploads"
    upload_limite_bytes: int = 10 * 1024 * 1024

    cors_origens: list[str] = ["http://localhost:5173"]

    # Chave da assinatura simulada (AssinadorDigitalFalso). Não é ICP-Brasil.
    assinatura_segredo: str = "chave-da-assinatura-simulada"


@lru_cache
def get_settings() -> Settings:
    return Settings()
