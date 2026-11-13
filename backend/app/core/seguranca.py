"""Senhas (bcrypt) e tokens JWT. RNF-03, art. 20 VII."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

_LIMITE_BCRYPT = 72  # bytes


def hash_senha(senha: str) -> str:
    dados = senha.encode("utf-8")
    if len(dados) > _LIMITE_BCRYPT:
        raise ValueError("Senha longa demais (máximo de 72 bytes).")
    return bcrypt.hashpw(dados, bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)).decode("ascii")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    dados = senha.encode("utf-8")
    if len(dados) > _LIMITE_BCRYPT:
        return False
    try:
        return bcrypt.checkpw(dados, senha_hash.encode("ascii"))
    except ValueError:
        return False


def criar_token(usuario_id: uuid.UUID, papel: str, empresa_id: uuid.UUID | None) -> str:
    s = get_settings()
    agora = datetime.now(UTC)
    claims = {
        "sub": str(usuario_id),
        "papel": papel,
        "empresa_id": str(empresa_id) if empresa_id else None,
        "iat": agora,
        "exp": agora + timedelta(minutes=s.jwt_expira_minutos),
    }
    return jwt.encode(claims, s.jwt_secret, algorithm=s.jwt_algoritmo)


def decodificar_token(token: str) -> dict[str, Any]:
    """Levanta jwt.InvalidTokenError se o token for inválido ou expirado."""
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algoritmo], options={"require": ["sub", "exp"]})
