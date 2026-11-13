"""Dependências de autenticação, papel e escopo de empresa.

Uso típico numa rota:

    @router.get("/coisas")
    def listar(usuario: Usuario = Depends(usuario_atual), session: Session = Depends(obter_sessao)):
        stmt = filtrar_por_empresa(select(Coisa), Coisa.empresa_id, usuario)

    @router.post("/coisas")
    def criar(usuario: Usuario = Depends(exige_papel(Papel.DESMONTADORA, Papel.RECICLADORA)), ...):
        ...
"""

import uuid
from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.erros import ErroNegocio
from app.core.seguranca import decodificar_token
from app.models import PAPEIS_SEM_EMPRESA, Papel, Usuario

_bearer = HTTPBearer(auto_error=False, description="Token devolvido por POST /api/v1/auth/login")

METODOS_LEITURA = frozenset({"GET", "HEAD", "OPTIONS"})


def usuario_atual(
    request: Request,
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(obter_sessao),
) -> Usuario:
    if credenciais is None:
        raise ErroNegocio(401, "NAO_AUTENTICADO", "Token de acesso ausente.")
    try:
        claims = decodificar_token(credenciais.credentials)
        usuario_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise ErroNegocio(401, "TOKEN_INVALIDO", "Token de acesso inválido ou expirado.") from exc

    usuario = session.get(Usuario, usuario_id)
    if usuario is None:
        raise ErroNegocio(401, "TOKEN_INVALIDO", "Usuário do token não existe.")

    # RNF-06, art. 24 V: o MDIC tem acesso supervisionado, somente leitura. Vale para toda rota.
    if usuario.papel == Papel.AUDITOR and request.method not in METODOS_LEITURA:
        raise ErroNegocio(403, "AUDITOR_SOMENTE_LEITURA", "O papel AUDITOR não pode alterar dados.")
    return usuario


def exige_papel(*papeis: Papel) -> Callable[..., Usuario]:
    """Dependência que só deixa passar os papéis informados (403 PAPEL_NAO_PERMITIDO)."""
    permitidos = frozenset(papeis)

    def _dependencia(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        if usuario.papel not in permitidos:
            raise ErroNegocio(
                403,
                "PAPEL_NAO_PERMITIDO",
                f"Ação permitida apenas para: {', '.join(sorted(permitidos))}.",
            )
        return usuario

    return _dependencia


def le_tudo(usuario: Usuario) -> bool:
    """ADMIN e AUDITOR leem todos os registros (RF-23, art. 9º; art. 24 V)."""
    return usuario.papel in PAPEIS_SEM_EMPRESA


def escopo_empresa(usuario: Usuario) -> uuid.UUID | None:
    """`None` = sem filtro (ADMIN, AUDITOR); senão, o `empresa_id` do usuário."""
    return None if le_tudo(usuario) else usuario.empresa_id


def filtrar_por_empresa(stmt: Select[Any], coluna: Any, usuario: Usuario) -> Select[Any]:
    """Aplica o filtro de empresa do token a uma consulta (docs/02-arquitetura.md, Segurança)."""
    escopo = escopo_empresa(usuario)
    return stmt if escopo is None else stmt.where(coluna == escopo)


def garantir_acesso_empresa(usuario: Usuario, empresa_id: uuid.UUID, entidade: str = "Registro") -> None:
    """404 (e não 403) quando o registro é de outra empresa, para não revelar que existe."""
    escopo = escopo_empresa(usuario)
    if escopo is not None and escopo != empresa_id:
        raise ErroNegocio(404, "NAO_ENCONTRADO", f"{entidade} não encontrado(a).")
