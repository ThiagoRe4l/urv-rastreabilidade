"""Formato único de erro do contrato: {"detail", "codigo", "pendencias"?}.

`pendencias` só aparece em 422 de pré-condição (docs/03-contrato-api.md).
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


class Erro(BaseModel):
    """Corpo de erro, para documentar respostas no OpenAPI."""

    detail: str
    codigo: str
    pendencias: list[str] | None = None


class ErroNegocio(Exception):
    """Erro com código estável. Levante nos services; o tratador converte em JSON."""

    def __init__(
        self,
        status_code: int,
        codigo: str,
        detail: str,
        pendencias: list[str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.codigo = codigo
        self.detail = detail
        self.pendencias = pendencias


class NaoEncontrado(ErroNegocio):
    def __init__(self, entidade: str) -> None:
        super().__init__(404, "NAO_ENCONTRADO", f"{entidade} não encontrado(a).")


_CODIGOS_HTTP = {
    400: "REQUISICAO_INVALIDA",
    401: "NAO_AUTENTICADO",
    403: "PROIBIDO",
    404: "NAO_ENCONTRADO",
    405: "METODO_NAO_PERMITIDO",
    409: "CONFLITO",
    413: "ARQUIVO_GRANDE_DEMAIS",
    415: "TIPO_DE_ARQUIVO_NAO_PERMITIDO",
}


def _corpo(detail: str, codigo: str, pendencias: list[str] | None = None) -> dict:
    corpo: dict = {"detail": detail, "codigo": codigo}
    if pendencias is not None:
        corpo["pendencias"] = pendencias
    return corpo


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(ErroNegocio)
    async def _erro_negocio(_: Request, exc: ErroNegocio) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_corpo(exc.detail, exc.codigo, exc.pendencias),
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _erro_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codigo = _CODIGOS_HTTP.get(exc.status_code, "ERRO_HTTP")
        return JSONResponse(
            status_code=exc.status_code,
            content=_corpo(str(exc.detail), codigo),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _erro_validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
        partes = []
        for e in exc.errors():
            campo = ".".join(str(p) for p in e.get("loc", ()) if p not in ("body", "query", "path"))
            partes.append(f"{campo}: {e.get('msg')}" if campo else str(e.get("msg")))
        return JSONResponse(
            status_code=422,
            content=_corpo("Entrada inválida. " + "; ".join(partes), "ENTRADA_INVALIDA"),
        )

    @app.exception_handler(IntegrityError)
    async def _erro_integridade(_: Request, exc: IntegrityError) -> JSONResponse:
        # Rede de segurança: os services devem checar unicidade antes e devolver código próprio.
        return JSONResponse(
            status_code=409,
            content=_corpo("Operação viola uma restrição de integridade do banco.", "VIOLACAO_INTEGRIDADE"),
        )
