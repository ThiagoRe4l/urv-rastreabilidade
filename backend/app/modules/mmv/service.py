"""Cadastro de MMV (Marca/Modelo/Versão). RF-03 e RF-04, art. 5º.

Services não fazem commit; a rota faz (ver app/core/db.py).
"""

import uuid
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.erros import ErroNegocio
from app.models import Mmv, MmvStatus, Usuario
from app.modules.auditoria.service import registrar_evento
from app.modules.mmv.schemas import MmvCriar


def efeitos_a_partir_de(data_cadastro: date, ja_comercializado: bool) -> date:
    """Data de início de efeitos do MMV. RF-04, art. 5º §2º.

    I - MMV já comercializado no País: 1º de janeiro do ano-calendário seguinte ao cadastro.
    II - MMV ainda não comercializado: a data do cadastro.
    """
    if ja_comercializado:
        return date(data_cadastro.year + 1, 1, 1)
    return data_cadastro


def cadastrar_mmv(session: Session, usuario: Usuario, dados: MmvCriar, data_cadastro: date) -> Mmv:
    """RF-03, art. 5º, caput e incisos I a III."""
    fabricante_id = usuario.empresa_id
    if fabricante_id is None:
        raise ErroNegocio(403, "PAPEL_NAO_PERMITIDO", "Ação permitida apenas para fabricante ou importador.")
    duplicado = session.scalar(
        select(Mmv.id).where(Mmv.fabricante_id == fabricante_id, Mmv.codigo == dados.codigo)
    )
    if duplicado is not None:
        raise ErroNegocio(409, "MMV_DUPLICADO", "Este código de MMV já está cadastrado para a empresa.")

    mmv = Mmv(
        fabricante_id=fabricante_id,
        codigo=dados.codigo,
        ncm=dados.ncm,
        nivel=dados.nivel,
        percentual_reciclabilidade=dados.percentual_reciclabilidade,
        ja_comercializado=dados.ja_comercializado,
        efeitos_a_partir_de=efeitos_a_partir_de(data_cadastro, dados.ja_comercializado),  # RF-04
        status=MmvStatus.ATIVO,
    )
    session.add(mmv)
    session.flush()
    registrar_evento(
        session,
        usuario,
        "MMV_CADASTRADO",
        "mmv",
        mmv.id,
        {
            "codigo": mmv.codigo,
            "ncm": mmv.ncm,
            "nivel": mmv.nivel,
            "percentual_reciclabilidade": mmv.percentual_reciclabilidade,
            "ja_comercializado": mmv.ja_comercializado,
            "efeitos_a_partir_de": mmv.efeitos_a_partir_de,
        },
    )
    return mmv


def consulta_mmvs(fabricante_id: uuid.UUID | None) -> Select:
    stmt = select(Mmv).order_by(Mmv.codigo, Mmv.id)
    if fabricante_id is not None:
        stmt = stmt.where(Mmv.fabricante_id == fabricante_id)
    return stmt
