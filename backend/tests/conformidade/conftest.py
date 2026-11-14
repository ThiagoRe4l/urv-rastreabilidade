"""Fixtures dos testes de conformidade (dono: qa-conformidade).

- `api`: cliente do contrato, já com o seed carregado. Rota que ainda não existe vira `xfail`
  com o motivo (ver `apoio.Api`).
- `nova_empresa`: cria outra empresa pela API e um usuário para ela. O usuário é gravado
  direto no banco porque não há rota de usuários (lacuna L-02).
- `encerrar_saldo_negativo`, `antecipar_efeitos_mmv` e `vencer_credenciamento`: preparam pelo
  banco o que o contrato não deixa preparar por HTTP (a data de hoje não é controlável pela API).
"""

import uuid
from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.seguranca import hash_senha
from app.models import ChaveParametro, ConfigParametro, Empresa, Mmv, Papel, Usuario
from scripts.seed import SENHA_DEMO, DadosDemo
from tests.conformidade.apoio import ADMIN, Api, EmpresaTeste, cnpj_aleatorio, ok


@pytest.fixture
def api(client: TestClient, auth: Callable[[str], dict[str, str]], dados_demo: DadosDemo) -> Api:
    return Api(client, auth)


@pytest.fixture
def demo(dados_demo: DadosDemo) -> DadosDemo:
    return dados_demo


@pytest.fixture
def nova_empresa(api: Api, db_session: Session) -> Callable[..., EmpresaTeste]:
    """`nova_empresa("DESMONTADORA")`, `nova_empresa("FABRICANTE", vinculo_com=geradora_id)`."""

    def _criar(
        tipo: str,
        *,
        credenciada: bool = True,
        registro_compromissos: bool = True,
        vinculo_com: str | uuid.UUID | None = None,
    ) -> EmpresaTeste:
        cnpj = cnpj_aleatorio()
        corpo: dict[str, object] = {
            "cnpj": cnpj,
            "razao_social": f"{tipo.title()} de Teste {cnpj[:5]}",
            "tipo": tipo,
        }
        if tipo == "FABRICANTE":
            corpo["registro_compromissos"] = registro_compromissos
        empresa = ok(api.post("/empresas", ADMIN, json=corpo))
        if tipo != "FABRICANTE" and credenciada:
            validade = (date.today() + timedelta(days=730)).isoformat()
            ok(
                api.patch(
                    f"/empresas/{empresa['id']}/credenciamento",
                    ADMIN,
                    json={"status": "ATIVO", "validade": validade},
                )
            )
        if vinculo_com is not None:
            par = (
                {"geradora_id": str(vinculo_com), "fabricante_id": empresa["id"]}
                if tipo == "FABRICANTE"
                else {"geradora_id": empresa["id"], "fabricante_id": str(vinculo_com)}
            )
            ok(api.post("/vinculos", ADMIN, json=par))
        email = f"usuario-{uuid.uuid4().hex[:10]}@teste.local"
        db_session.add(
            Usuario(
                email=email,
                nome="Usuário de teste",
                papel=Papel(tipo),
                empresa_id=uuid.UUID(empresa["id"]),
                senha_hash=hash_senha(SENHA_DEMO),
            )
        )
        db_session.flush()
        return EmpresaTeste(id=empresa["id"], cnpj=cnpj, email=email)

    return _criar


@pytest.fixture
def encerrar_saldo_negativo(db_session: Session) -> Callable[[], None]:
    """Simula uma operação posterior a 31/12/2027 (art. 8º §1º).

    A API não deixa escolher a data da operação, então o teste grava uma nova vigência do
    parâmetro FIM_SALDO_NEGATIVO com uma data já passada.
    """

    def _encerrar() -> None:
        db_session.add(
            ConfigParametro(
                chave=ChaveParametro.FIM_SALDO_NEGATIVO,
                valor=(date.today() - timedelta(days=2)).isoformat(),
                vigente_desde=date.today() - timedelta(days=1),
            )
        )
        db_session.flush()

    return _encerrar


@pytest.fixture
def vencer_credenciamento(db_session: Session) -> Callable[[str | uuid.UUID], None]:
    """Faz um credenciamento ATIVO vencer: a validade passa a ser de dois dias atrás (art. 16).

    A API recusa gravar credenciamento ATIVO com validade já passada (422), e não deixa
    escolher a data da operação; vencer é a passagem do tempo, então o teste recua a validade.
    """

    def _vencer(empresa_id: str | uuid.UUID) -> None:
        empresa = db_session.get(Empresa, uuid.UUID(str(empresa_id)))
        assert empresa is not None
        empresa.credenciamento_validade = date.today() - timedelta(days=2)
        db_session.flush()

    return _vencer


@pytest.fixture
def antecipar_efeitos_mmv(db_session: Session) -> Callable[[str, date], None]:
    """Recua `efeitos_a_partir_de` de um MMV, para registrar consumo de período passado."""

    def _antecipar(mmv_id: str, desde: date) -> None:
        mmv = db_session.get(Mmv, uuid.UUID(mmv_id))
        assert mmv is not None
        mmv.efeitos_a_partir_de = desde
        db_session.flush()

    return _antecipar
