"""Montagem de dados para os testes do agente 02 (backend-urv).

O certificado é do agente 01; aqui ele é criado direto no banco, só com o que o livro de URV lê.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.seguranca import hash_senha
from app.models import (
    Certificado,
    CredenciamentoStatus,
    DocumentoEntradaTipo,
    Empresa,
    EstadoVeiculo,
    Mmv,
    OrigemAquisicao,
    Papel,
    TipoEmpresa,
    TipoVeiculo,
    UrvCredito,
    Usuario,
    Veiculo,
)
from app.modules.urv.service import gerar_credito
from scripts.seed import SENHA_DEMO

# Sexta-feira, 13h em Brasília: depois da vigência da portaria (09/11/2026).
HOJE = datetime(2026, 11, 13, 16, 0, tzinfo=UTC)

CNPJ_RECICLA = "11222333000181"
CNPJ_IMPORTADORA = "11444777000161"


def vin(n: int) -> str:
    """VIN sintético de 17 caracteres para veículo novo."""
    return f"9BW{n:014d}"


def vins(quantidade: int, inicio: int = 1) -> list[str]:
    return [vin(n) for n in range(inicio, inicio + quantidade)]


def criar_certificado(
    session: Session,
    empresa_id: uuid.UUID,
    chassi: str,
    *,
    tipo: TipoVeiculo = TipoVeiculo.LICENCIADO_RODAGEM,
    fator: Decimal = Decimal("1.00"),
    emitido_em: datetime = HOJE,
    numero: str | None = None,
) -> Certificado:
    veiculo = Veiculo(
        empresa_id=empresa_id,
        chassi=chassi,
        data_entrada=date(2026, 11, 10),
        tipo_declarado=tipo,
        tipo=tipo,
        origem_aquisicao=OrigemAquisicao.COMPRA_DIRETA,
        documento_entrada_tipo=DocumentoEntradaTipo.NF_ENTRADA,
        documento_entrada_numero="NF-1",
        estado=EstadoVeiculo.CERTIFICADO,
    )
    session.add(veiculo)
    session.flush()
    certificado = Certificado(
        veiculo_id=veiculo.id,
        numero=numero or f"CRV-{chassi}",
        empresa_id=empresa_id,
        tipo_veiculo=tipo,
        fator=fator,
        emitido_em=emitido_em,
        hash_conteudo="a" * 64,
    )
    session.add(certificado)
    session.flush()
    return certificado


def creditar(session: Session, empresa_id: uuid.UUID, chassi: str, **kwargs) -> UrvCredito:
    """Certificado + crédito, como o fluxo do veículo faz ao emitir o certificado."""
    return gerar_credito(session, criar_certificado(session, empresa_id, chassi, **kwargs))


def criar_mmv(
    session: Session,
    fabricante_id: uuid.UUID,
    *,
    codigo: str = "HATCH-1.0-FLEX",
    nivel: int = 1,
    ja_comercializado: bool = False,
    efeitos: date = date(2026, 11, 9),
) -> Mmv:
    mmv = Mmv(
        fabricante_id=fabricante_id,
        codigo=codigo,
        ncm="87032100",
        nivel=nivel,
        percentual_reciclabilidade=Decimal("85.00"),
        ja_comercializado=ja_comercializado,
        efeitos_a_partir_de=efeitos,
    )
    session.add(mmv)
    session.flush()
    return mmv


def criar_empresa_com_usuario(
    session: Session,
    *,
    cnpj: str,
    razao_social: str,
    tipo: TipoEmpresa,
    email: str,
    compromissos: bool = True,
) -> Usuario:
    """Uma segunda empresa, com usuário que entra com a senha do seed."""
    fabricante = tipo == TipoEmpresa.FABRICANTE
    empresa = Empresa(
        cnpj=cnpj,
        razao_social=razao_social,
        tipo=tipo,
        credenciamento_status=None if fabricante else CredenciamentoStatus.ATIVO,
        credenciamento_validade=None if fabricante else date(2028, 11, 1),
        registro_compromissos=fabricante and compromissos,
    )
    session.add(empresa)
    session.flush()
    usuario = Usuario(
        email=email,
        nome=f"Usuário de {razao_social}",
        papel=Papel(tipo.value),
        empresa_id=empresa.id,
        senha_hash=hash_senha(SENHA_DEMO),
    )
    session.add(usuario)
    session.flush()
    return usuario
