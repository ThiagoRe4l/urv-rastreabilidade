"""Fixtures dos testes do fluxo do veículo (agente 01)."""

from datetime import date

import pytest

from app.core.config import get_settings
from app.core.seguranca import hash_senha
from app.models import (
    CredenciamentoStatus,
    LancamentoTipo,
    Papel,
    TipoEmpresa,
    UrvCredito,
    UrvLancamento,
    Usuario,
)
from app.modules.empresas import service as empresas
from app.modules.empresas.schemas import CredenciamentoAtualizar, EmpresaCriar
from scripts.seed import EMAIL_DESMONTADORA, SENHA_DEMO
from tests.unit.fluxo.apoio import CNPJ_OUTRA, EMAIL_OUTRA


@pytest.fixture(autouse=True)
def pasta_uploads(tmp_path, monkeypatch):
    """Anexos dos testes vão para uma pasta temporária, não para /data/uploads."""
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


def gerar_credito_substituto(session, certificado) -> UrvCredito:
    """Substituto de `urv.service.gerar_credito` (agente 02), só com o que a assinatura promete."""
    credito = UrvCredito(
        certificado_id=certificado.id,
        geradora_id=certificado.empresa_id,
        titular_id=certificado.empresa_id,
        quantidade=certificado.fator,
    )
    session.add(credito)
    session.flush()
    session.add(
        UrvLancamento(
            empresa_id=certificado.empresa_id,
            tipo=LancamentoTipo.CREDITO,
            quantidade=certificado.fator,
            credito_id=credito.id,
        )
    )
    session.flush()
    return credito


@pytest.fixture(autouse=True)
def credito_substituto(monkeypatch):
    """O fluxo só chama `gerar_credito`; a lógica do crédito não é testada aqui."""
    chamadas: list = []

    def _substituto(session, certificado):
        chamadas.append(certificado)
        return gerar_credito_substituto(session, certificado)

    monkeypatch.setattr("app.modules.urv.service.gerar_credito", _substituto)
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
