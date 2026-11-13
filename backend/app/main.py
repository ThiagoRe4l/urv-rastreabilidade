"""Aplicação FastAPI. Todos os routers já estão registrados: ninguém precisa editar este arquivo."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import configuracao
from app.core.config import get_settings
from app.core.erros import registrar_tratadores
from app.modules.auditoria import router as auditoria
from app.modules.auth import router as auth
from app.modules.documentos import router as documentos
from app.modules.empresas import router as empresas
from app.modules.mmv import router as mmv
from app.modules.pecas import router as pecas
from app.modules.portabilidade import router as portabilidade
from app.modules.relatorios import router as relatorios
from app.modules.residuos import router as residuos
from app.modules.urv import router as urv
from app.modules.veiculos import router as veiculos

PREFIXO_API = "/api/v1"

ROUTERS = [
    # fundação
    auth.router,
    empresas.router,
    auditoria.router,
    configuracao.router,
    # backend-fluxo
    veiculos.router,
    pecas.router,
    residuos.router,
    documentos.router,
    # backend-urv
    mmv.router,
    urv.router,
    relatorios.router,
    portabilidade.router,
]


def criar_app() -> FastAPI:
    app = FastAPI(
        title="URV Rastreabilidade",
        version="0.1.0",
        description=(
            "Rastreabilidade da desmontagem e reciclagem de veículos em fim de vida e livro de URV "
            "(Portaria GM/MDIC nº 325/2026). MVP de avaliação. Valores Decimal trafegam como string."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origens,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    registrar_tratadores(app)
    for r in ROUTERS:
        app.include_router(r, prefix=PREFIXO_API)

    @app.get("/saude", tags=["infra"], include_in_schema=False)
    def saude() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = criar_app()
