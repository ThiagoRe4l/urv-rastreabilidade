"""Empresas, credenciamento e vínculos. RF-01 e RF-02.

Services não fazem commit; a rota faz (ver app/core/db.py).
"""

import uuid
from datetime import date

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core import relogio
from app.core.deps import escopo_empresa
from app.core.erros import ErroNegocio, NaoEncontrado
from app.models import CredenciamentoStatus, Empresa, TipoEmpresa, Usuario, Vinculo
from app.modules.auditoria.service import registrar_evento
from app.modules.empresas.schemas import CredenciamentoAtualizar, EmpresaCriar

TIPOS_GERADORA = (TipoEmpresa.DESMONTADORA, TipoEmpresa.RECICLADORA)
VALIDADE_MAXIMA_ANOS = 2  # art. 16


# --- Consultas para outros módulos ------------------------------------------------------------


def credenciamento_vigente(empresa: Empresa, em: date) -> bool:
    """ATIVO e dentro da validade na data. RF-01, art. 11; art. 16; art. 8º I."""
    return (
        empresa.tipo in TIPOS_GERADORA
        and empresa.credenciamento_status == CredenciamentoStatus.ATIVO
        and empresa.credenciamento_validade is not None
        and empresa.credenciamento_validade >= em
    )


def vinculo_ativo(session: Session, geradora_id: uuid.UUID, fabricante_id: uuid.UUID) -> bool:
    """RF-02 e RF-17, art. 8º II; art. 13 §2º."""
    return bool(
        session.scalar(
            select(Vinculo.id).where(
                Vinculo.geradora_id == geradora_id,
                Vinculo.fabricante_id == fabricante_id,
                Vinculo.ativo.is_(True),
            )
        )
    )


def obter_empresa(session: Session, empresa_id: uuid.UUID) -> Empresa:
    empresa = session.get(Empresa, empresa_id)
    if empresa is None:
        raise NaoEncontrado("Empresa")
    return empresa


# --- Empresas ---------------------------------------------------------------------------------


def somar_anos(d: date, anos: int) -> date:
    try:
        return d.replace(year=d.year + anos)
    except ValueError:  # 29 de fevereiro
        return d.replace(year=d.year + anos, day=28)


def _dados_empresa(e: Empresa) -> dict:
    return {
        "cnpj": e.cnpj,
        "razao_social": e.razao_social,
        "tipo": e.tipo,
        "credenciamento_status": e.credenciamento_status,
        "credenciamento_validade": e.credenciamento_validade,
        "registro_compromissos": e.registro_compromissos,
    }


def criar_empresa(session: Session, usuario: Usuario | None, dados: EmpresaCriar) -> Empresa:
    if session.scalar(select(Empresa.id).where(Empresa.cnpj == dados.cnpj)):
        raise ErroNegocio(409, "CNPJ_DUPLICADO", "Já existe empresa com este CNPJ.")
    fabricante = dados.tipo == TipoEmpresa.FABRICANTE
    if not fabricante and dados.registro_compromissos:
        raise ErroNegocio(
            422,
            "REGISTRO_COMPROMISSOS_SO_FABRICANTE",
            "Registro de compromissos se aplica só a fabricante ou importador (art. 8º II).",
        )
    empresa = Empresa(
        cnpj=dados.cnpj,
        razao_social=dados.razao_social,
        tipo=dados.tipo,
        # RF-01: geradora nasce PENDENTE; fabricante não tem credenciamento (art. 11).
        credenciamento_status=None if fabricante else CredenciamentoStatus.PENDENTE,
        registro_compromissos=bool(dados.registro_compromissos) if fabricante else False,
    )
    session.add(empresa)
    session.flush()
    registrar_evento(
        session,
        usuario,
        "EMPRESA_CRIADA",
        "empresa",
        empresa.id,
        _dados_empresa(empresa),
        empresa_id=empresa.id,
    )
    return empresa


def atualizar_registro_compromissos(
    session: Session, usuario: Usuario, empresa_id: uuid.UUID, registro_compromissos: bool
) -> Empresa:
    """Art. 8º II: só fabricante com registro de compromissos recebe URV."""
    empresa = obter_empresa(session, empresa_id)
    if empresa.tipo != TipoEmpresa.FABRICANTE:
        raise ErroNegocio(
            422,
            "REGISTRO_COMPROMISSOS_SO_FABRICANTE",
            "Registro de compromissos se aplica só a fabricante ou importador (art. 8º II).",
        )
    antes = empresa.registro_compromissos
    empresa.registro_compromissos = registro_compromissos
    session.flush()
    registrar_evento(
        session,
        usuario,
        "EMPRESA_ATUALIZADA",
        "empresa",
        empresa.id,
        {"registro_compromissos": {"antes": antes, "depois": registro_compromissos}},
        empresa_id=empresa.id,
    )
    return empresa


def alterar_credenciamento(
    session: Session, usuario: Usuario, empresa_id: uuid.UUID, dados: CredenciamentoAtualizar
) -> Empresa:
    """RF-01, arts. 11, 16 e 17: credenciamento lançado pelo admin, validade de até 2 anos."""
    empresa = obter_empresa(session, empresa_id)
    if empresa.tipo not in TIPOS_GERADORA:
        raise ErroNegocio(
            422,
            "FABRICANTE_SEM_CREDENCIAMENTO",
            "Fabricante ou importador não tem credenciamento; use registro_compromissos (art. 8º II).",
        )
    validade = dados.validade if dados.validade is not None else empresa.credenciamento_validade
    hoje = relogio.hoje()  # PM-URV-06: validade na data de Brasília (art. 16)
    if dados.status == CredenciamentoStatus.ATIVO:
        if validade is None:
            raise ErroNegocio(422, "VALIDADE_OBRIGATORIA", "Credenciamento ATIVO exige validade (art. 16).")
        if validade < hoje:
            raise ErroNegocio(422, "VALIDADE_VENCIDA", "A validade informada já passou.")
    if dados.validade is not None and dados.validade > somar_anos(hoje, VALIDADE_MAXIMA_ANOS):
        raise ErroNegocio(
            422, "VALIDADE_ACIMA_DE_DOIS_ANOS", "O credenciamento vale no máximo 2 anos (art. 16)."
        )

    antes = {"status": empresa.credenciamento_status, "validade": empresa.credenciamento_validade}
    empresa.credenciamento_status = dados.status
    empresa.credenciamento_validade = validade
    session.flush()
    registrar_evento(
        session,
        usuario,
        "CREDENCIAMENTO_ALTERADO",
        "empresa",
        empresa.id,
        {"antes": antes, "depois": {"status": dados.status, "validade": validade}},
        empresa_id=empresa.id,
    )
    return empresa


def consulta_empresas(session: Session, usuario: Usuario, tipo: TipoEmpresa | None) -> Select:
    """ADMIN e AUDITOR veem todas; os demais veem a própria empresa e as contrapartes com vínculo ativo."""
    stmt = select(Empresa).order_by(Empresa.razao_social)
    if tipo is not None:
        stmt = stmt.where(Empresa.tipo == tipo)
    escopo = escopo_empresa(usuario)
    if escopo is not None:
        contrapartes = (
            select(Vinculo.fabricante_id)
            .where(Vinculo.geradora_id == escopo, Vinculo.ativo.is_(True))
            .union(
                select(Vinculo.geradora_id).where(Vinculo.fabricante_id == escopo, Vinculo.ativo.is_(True))
            )
        )
        stmt = stmt.where(or_(Empresa.id == escopo, Empresa.id.in_(contrapartes)))
    return stmt


# --- Vínculos ---------------------------------------------------------------------------------


def criar_vinculo(
    session: Session, usuario: Usuario | None, geradora_id: uuid.UUID, fabricante_id: uuid.UUID
) -> Vinculo:
    """RF-02, art. 13 §1º VI e §2º: um vínculo por par geradora × fabricante."""
    geradora = obter_empresa(session, geradora_id)
    fabricante = obter_empresa(session, fabricante_id)
    if geradora.tipo not in TIPOS_GERADORA:
        raise ErroNegocio(
            422, "GERADORA_INVALIDA", "A geradora precisa ser empresa de desmontagem ou reciclagem."
        )
    if fabricante.tipo != TipoEmpresa.FABRICANTE:
        raise ErroNegocio(422, "FABRICANTE_INVALIDO", "A contraparte precisa ser fabricante ou importador.")
    existente = session.scalar(
        select(Vinculo).where(Vinculo.geradora_id == geradora_id, Vinculo.fabricante_id == fabricante_id)
    )
    if existente is not None:
        raise ErroNegocio(
            409, "VINCULO_DUPLICADO", "Já existe vínculo entre estas empresas; use PATCH /vinculos/{id}."
        )
    vinculo = Vinculo(geradora_id=geradora_id, fabricante_id=fabricante_id, ativo=True)
    session.add(vinculo)
    session.flush()
    registrar_evento(
        session,
        usuario,
        "VINCULO_CRIADO",
        "vinculo",
        vinculo.id,
        {"geradora_id": geradora_id, "fabricante_id": fabricante_id, "ativo": True},
        empresa_id=geradora_id,
    )
    return vinculo


def alterar_vinculo(session: Session, usuario: Usuario | None, vinculo_id: uuid.UUID, ativo: bool) -> Vinculo:
    vinculo = session.get(Vinculo, vinculo_id)
    if vinculo is None:
        raise NaoEncontrado("Vínculo")
    antes = vinculo.ativo
    vinculo.ativo = ativo
    session.flush()
    registrar_evento(
        session,
        usuario,
        "VINCULO_ALTERADO",
        "vinculo",
        vinculo.id,
        {
            "geradora_id": vinculo.geradora_id,
            "fabricante_id": vinculo.fabricante_id,
            "ativo": {"antes": antes, "depois": ativo},
        },
        empresa_id=vinculo.geradora_id,
    )
    return vinculo


def consulta_vinculos(usuario: Usuario) -> Select:
    stmt = select(Vinculo).order_by(Vinculo.criado_em)
    escopo = escopo_empresa(usuario)
    if escopo is not None:
        stmt = stmt.where(or_(Vinculo.geradora_id == escopo, Vinculo.fabricante_id == escopo))
    return stmt
