from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import usuario_atual
from app.core.erros import Erro
from app.core.seguranca import criar_token
from app.models import Usuario
from app.modules.auth import service
from app.modules.auth.schemas import LoginEntrada, LoginSaida, UsuarioSaida

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginSaida,
    responses={401: {"model": Erro}},
    summary="Autentica e devolve o token JWT",
)
def login(dados: LoginEntrada, session: Session = Depends(obter_sessao)) -> LoginSaida:
    usuario = service.autenticar(session, dados.email, dados.senha)  # RNF-03, art. 20 VII
    token = criar_token(usuario.id, usuario.papel.value, usuario.empresa_id)
    return LoginSaida(access_token=token, usuario=UsuarioSaida.model_validate(usuario))


@router.get("/me", response_model=UsuarioSaida, summary="Usuário do token")
def me(usuario: Usuario = Depends(usuario_atual)) -> UsuarioSaida:
    return UsuarioSaida.model_validate(usuario)
