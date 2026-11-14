"""Fixtures dos testes do fluxo do veículo (agente 01)."""

from datetime import date

import pytest

from app.core.config import get_settings
from app.core.seguranca import hash_senha
from app.models import CredenciamentoStatus, Papel, TipoEmpresa, Usuario
from app.modules.empresas import service as empresas
from app.modules.empresas.schemas import CredenciamentoAtualizar, EmpresaCriar
from app.modules.urv import service as urv_service
from scripts.seed import EMAIL_DESMONTADORA, SENHA_DEMO
from tests.unit.fluxo.apoio import CNPJ_OUTRA, EMAIL_OUTRA


@pytest.fixture(autouse=True)
def pasta_uploads(tmp_path, monkeypatch):
    """Anexos dos testes vão para uma pasta temporária, não para /data/uploads."""
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


class Chamadas(list):
    """Certificados passados a `gerar_credito`, na ordem; `usuarios` guarda o autor de cada um."""

    def __init__(self) -> None:
        super().__init__()
        self.usuarios: list = []


@pytest.fixture(autouse=True)
def credito_substituto(monkeypatch) -> Chamadas:
    """Espião de `urv.service.gerar_credito`: chama a implementação real e guarda as chamadas.

    Até a integração era um substituto, porque a função ainda não existia nesta branch. Agora
    o crédito é o real, e o espião confere que o fluxo informa quem emitiu (PM-URV-02).
    """
    chamadas = Chamadas()
    real = urv_service.gerar_credito

    def _espiao(session, certificado, *, usuario=None):
        chamadas.append(certificado)
        chamadas.usuarios.append(usuario)
        return real(session, certificado, usuario=usuario)

    monkeypatch.setattr("app.modules.urv.service.gerar_credito", _espiao)
    return chamadas


@pytest.fixture
def h(auth):
    """Cabeçalho do operador da desmontadora do seed."""
    return auth(EMAIL_DESMONTADORA)


@pytest.fixture
def h_outra(db_session, dados_demo, auth):
    """Cabeçalho do operador de uma segunda desmontadora credenciada."""
    empresa = empresas.criar_empresa(
        db_session,
        None,
        EmpresaCriar(cnpj=CNPJ_OUTRA, razao_social="Outra Desmontagem Ltda.", tipo=TipoEmpresa.DESMONTADORA),
    )
    empresas.alterar_credenciamento(
        db_session,
        None,
        empresa.id,
        CredenciamentoAtualizar(
            status=CredenciamentoStatus.ATIVO, validade=empresas.somar_anos(date.today(), 1)
        ),
    )
    db_session.add(
        Usuario(
            email=EMAIL_OUTRA,
            nome="Operador da Outra",
            papel=Papel.DESMONTADORA,
            empresa_id=empresa.id,
            senha_hash=hash_senha(SENHA_DEMO),
        )
    )
    db_session.flush()
    return auth(EMAIL_OUTRA)
