"""Dados de demonstração (docs/03-contrato-api.md, "Usuários de demonstração").

Idempotente: se o admin já existe, não faz nada. Uso: `python -m scripts.seed`.
Todas as escritas passam pela trilha de auditoria.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.core.seguranca import hash_senha
from app.models import (
    ChaveParametro,
    ConfigFator,
    ConfigParametro,
    CredenciamentoStatus,
    Papel,
    TipoEmpresa,
    TipoVeiculo,
    Usuario,
    Vinculo,
)
from app.modules.auditoria.service import registrar_evento
from app.modules.empresas import service as empresas
from app.modules.empresas.schemas import CredenciamentoAtualizar, EmpresaCriar

SENHA_DEMO = "demo1234"

EMAIL_ADMIN = "admin@urv.local"
EMAIL_AUDITOR = "auditor@mdic.local"
EMAIL_DESMONTADORA = "operador@desmonte.local"
EMAIL_FABRICANTE = "fiscal@montadora.local"

CNPJ_DESMONTE = "12345678000195"
CNPJ_MONTADORA = "98765432000198"

# Portaria publicada no DOU em 09/11/2026, vigente na publicação (art. 34).
VIGENCIA_PORTARIA = date(2026, 11, 9)

# Art. 3º §2º e Anexo I, item 5.
FATORES: dict[TipoVeiculo, Decimal] = {
    TipoVeiculo.LICENCIADO_RODAGEM: Decimal("1.00"),
    TipoVeiculo.SINISTRADO_PEQUENA_MEDIA: Decimal("0.94"),
    TipoVeiculo.SUCATA_APROVEITAVEL: Decimal("0.85"),
    TipoVeiculo.SINISTRADO_GRANDE: Decimal("0.79"),
    TipoVeiculo.SUCATA_MOTOR_INSERVIVEL: Decimal("0.68"),
    TipoVeiculo.SUCATA_INSERVIVEL: Decimal("0.38"),
}

PARAMETROS: dict[ChaveParametro, str] = {
    ChaveParametro.PRECO_BASE: "150000.00",  # art. 3º §5º
    ChaveParametro.FIM_SALDO_NEGATIVO: "2027-12-31",  # art. 8º §1º
}


@dataclass(frozen=True)
class DadosDemo:
    admin_id: uuid.UUID
    auditor_id: uuid.UUID
    operador_id: uuid.UUID
    fiscal_id: uuid.UUID
    desmonte_id: uuid.UUID
    montadora_id: uuid.UUID
    vinculo_id: uuid.UUID


def _criar_usuario(
    session: Session,
    autor: Usuario | None,
    email: str,
    nome: str,
    papel: Papel,
    empresa_id: uuid.UUID | None,
) -> Usuario:
    usuario = Usuario(
        email=email, nome=nome, papel=papel, empresa_id=empresa_id, senha_hash=hash_senha(SENHA_DEMO)
    )
    session.add(usuario)
    session.flush()
    registrar_evento(
        session,
        autor,
        "USUARIO_CRIADO",
        "usuario",
        usuario.id,
        {"email": email, "papel": papel, "empresa_id": empresa_id},
        empresa_id=empresa_id,
    )
    return usuario


def _dados_existentes(session: Session) -> DadosDemo | None:
    admin = session.scalar(select(Usuario).where(Usuario.email == EMAIL_ADMIN))
    if admin is None:
        return None
    por_email = {u.email: u for u in session.scalars(select(Usuario)).all()}
    desmonte = por_email[EMAIL_DESMONTADORA].empresa_id
    montadora = por_email[EMAIL_FABRICANTE].empresa_id
    assert desmonte and montadora
    vinculo = session.scalar(
        select(Vinculo.id).where(Vinculo.geradora_id == desmonte, Vinculo.fabricante_id == montadora)
    )
    assert vinculo
    return DadosDemo(
        admin.id,
        por_email[EMAIL_AUDITOR].id,
        por_email[EMAIL_DESMONTADORA].id,
        por_email[EMAIL_FABRICANTE].id,
        desmonte,
        montadora,
        vinculo,
    )


def semear(session: Session) -> DadosDemo:
    """Cria os dados de demonstração na sessão, sem commit. Devolve os ids criados."""
    existentes = _dados_existentes(session)
    if existentes is not None:
        return existentes

    admin = _criar_usuario(session, None, EMAIL_ADMIN, "Administrador da Plataforma", Papel.ADMIN, None)
    auditor = _criar_usuario(session, admin, EMAIL_AUDITOR, "Auditoria MDIC", Papel.AUDITOR, None)

    for tipo, fator in FATORES.items():
        cfg = ConfigFator(tipo_veiculo=tipo, fator=fator, vigente_desde=VIGENCIA_PORTARIA)
        session.add(cfg)
        session.flush()
        registrar_evento(
            session,
            admin,
            "FATOR_CONFIGURADO",
            "config_fator",
            cfg.id,
            {"tipo_veiculo": tipo, "fator": fator, "vigente_desde": VIGENCIA_PORTARIA},
        )
    for chave, valor in PARAMETROS.items():
        par = ConfigParametro(chave=chave, valor=valor, vigente_desde=VIGENCIA_PORTARIA)
        session.add(par)
        session.flush()
        registrar_evento(
            session,
            admin,
            "PARAMETRO_CONFIGURADO",
            "config_parametro",
            par.id,
            {"chave": chave, "valor": valor, "vigente_desde": VIGENCIA_PORTARIA},
        )

    desmonte = empresas.criar_empresa(
        session,
        admin,
        EmpresaCriar(cnpj=CNPJ_DESMONTE, razao_social="Desmonte Paraná S.A.", tipo=TipoEmpresa.DESMONTADORA),
    )
    empresas.alterar_credenciamento(
        session,
        admin,
        desmonte.id,
        CredenciamentoAtualizar(status=CredenciamentoStatus.ATIVO, validade=empresas.somar_anos(hoje(), 2)),
    )
    montadora = empresas.criar_empresa(
        session,
        admin,
        EmpresaCriar(
            cnpj=CNPJ_MONTADORA,
            razao_social="Montadora Exemplo S.A.",
            tipo=TipoEmpresa.FABRICANTE,
            registro_compromissos=True,
        ),
    )
    vinculo = empresas.criar_vinculo(session, admin, desmonte.id, montadora.id)

    operador = _criar_usuario(
        session, admin, EMAIL_DESMONTADORA, "Operador da Desmontagem", Papel.DESMONTADORA, desmonte.id
    )
    fiscal = _criar_usuario(
        session, admin, EMAIL_FABRICANTE, "Fiscal da Montadora", Papel.FABRICANTE, montadora.id
    )
    return DadosDemo(admin.id, auditor.id, operador.id, fiscal.id, desmonte.id, montadora.id, vinculo.id)


def main() -> None:
    from app.core.db import SessionLocal

    with SessionLocal() as session:
        ja_existia = _dados_existentes(session) is not None
        semear(session)
        session.commit()
    print(
        "Seed: dados de demonstração já existiam." if ja_existia else "Seed: dados de demonstração criados."
    )


if __name__ == "__main__":
    main()
