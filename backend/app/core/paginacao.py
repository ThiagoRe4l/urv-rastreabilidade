"""Paginação do contrato: `?pagina=1&tamanho=20` → `{"itens": [], "total": 0}`."""

from dataclasses import dataclass
from typing import Any

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

TAMANHO_MAXIMO = 100


@dataclass(frozen=True)
class Paginacao:
    pagina: int = 1
    tamanho: int = 20

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.tamanho


def paginacao(
    pagina: int = Query(1, ge=1, description="Página, a partir de 1"),
    tamanho: int = Query(20, ge=1, le=TAMANHO_MAXIMO, description="Itens por página"),
) -> Paginacao:
    """Dependência FastAPI: `pag: Paginacao = Depends(paginacao)`."""
    return Paginacao(pagina=pagina, tamanho=tamanho)


class Pagina[T](BaseModel):
    itens: list[T]
    total: int


def paginar(session: Session, stmt: Select[Any], pag: Paginacao) -> tuple[list[Any], int]:
    """Executa `stmt` com offset/limit e devolve (itens, total sem paginação)."""
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    itens = list(session.scalars(stmt.offset(pag.offset).limit(pag.tamanho)).all())
    return itens, total
