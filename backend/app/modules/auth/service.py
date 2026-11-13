from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.erros import ErroNegocio
from app.core.seguranca import hash_senha, verificar_senha
from app.models import Usuario

# Hash fixo usado quando o e-mail não existe, para o tempo de resposta não revelar isso.
_HASH_FICTICIO = hash_senha("senha-ficticia-para-tempo-constante")


def autenticar(session: Session, email: str, senha: str) -> Usuario:
    usuario = session.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
    if usuario is None:
        verificar_senha(senha, _HASH_FICTICIO)
        raise ErroNegocio(401, "CREDENCIAIS_INVALIDAS", "E-mail ou senha incorretos.")
    if not verificar_senha(senha, usuario.senha_hash):
        raise ErroNegocio(401, "CREDENCIAIS_INVALIDAS", "E-mail ou senha incorretos.")
    return usuario
