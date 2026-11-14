"""Pesagens por fração, meta de aproveitamento e DMR. RF-11 a RF-13.

Services não fazem commit; a rota faz (ver app/core/db.py).
"""

import uuid
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.decimais import quantizar, quantizar_peso
from app.core.erros import ErroNegocio
from app.core.integracoes import EmissorMTR
from app.models import DestinoPesagem, Dmr, Empresa, Pesagem, Usuario
from app.modules.auditoria.service import registrar_evento
from app.modules.residuos.schemas import DmrCriar, PesagemCriar
from app.modules.veiculos import service as veiculos

CEM = Decimal("100")


# --- Aproveitamento e meta ---------------------------------------------------------------------


def percentual_aproveitado(pesagens: Iterable[Pesagem]) -> Decimal | None:
    """RF-12, art. 18 §5º: soma(peso com destino ≠ REJEITO) / soma(peso), em pontos (0 a 100).

    Duas casas, ROUND_HALF_UP. `None` sem pesagens.
    """
    total = Decimal(0)
    aproveitado = Decimal(0)
    for p in pesagens:
        total += p.peso_kg
        if p.destino != DestinoPesagem.REJEITO:
            aproveitado += p.peso_kg
    if total == 0:
        return None
    return quantizar(aproveitado * CEM / total)


def meta_do_ano(ano: int) -> Decimal | None:
    """Meta de aproveitamento em pontos. RF-12, art. 18 §§5º e 7º: em 2026 só há registro."""
    if ano <= 2026:
        return None
    if ano <= 2028:
        return Decimal("80.00")
    if ano <= 2030:
        return Decimal("85.00")
    if ano <= 2032:
        return Decimal("90.00")
    return Decimal("95.00")


def atende_meta(percentual: Decimal | None, meta: Decimal | None) -> bool | None:
    """Abaixo da meta é alerta, não bloqueio: o descumprimento é apurado pelo MDIC (art. 17 §2º)."""
    if percentual is None or meta is None:
        return None
    return percentual >= meta


def pesagens_do_veiculo(session: Session, veiculo_id: uuid.UUID) -> list[Pesagem]:
    return list(
        session.scalars(
            select(Pesagem).where(Pesagem.veiculo_id == veiculo_id).order_by(Pesagem.criado_em, Pesagem.id)
        )
    )


# --- Pesagens ----------------------------------------------------------------------------------


def registrar_pesagem(
    session: Session, usuario: Usuario, veiculo_id: uuid.UUID, dados: PesagemCriar
) -> Pesagem:
    """RF-11, art. 18 §6º; Anexo III 14.c: peso por fração de material e por veículo."""
    veiculo = veiculos.obter_veiculo(session, usuario, veiculo_id, bloquear=True)
    # O certificado grava o percentual aproveitado; pesagem posterior o tornaria falso.
    veiculos.exigir_sem_certificado(veiculo)

    pesagem = Pesagem(
        veiculo=veiculo, fracao=dados.fracao, destino=dados.destino, peso_kg=quantizar_peso(dados.peso_kg)
    )
    session.add(pesagem)
    veiculos.marcar_em_processo(veiculo)
    session.flush()
    registrar_evento(
        session,
        usuario,
        "PESAGEM_REGISTRADA",
        "pesagem",
        pesagem.id,
        {
            "veiculo_id": veiculo.id,
            "fracao": pesagem.fracao,
            "destino": pesagem.destino,
            "peso_kg": pesagem.peso_kg,
        },
    )
    return pesagem


# --- DMR ---------------------------------------------------------------------------------------


def dmrs_do_veiculo(session: Session, veiculo_id: uuid.UUID) -> list[Dmr]:
    return list(session.scalars(select(Dmr).where(Dmr.veiculo_id == veiculo_id).order_by(Dmr.emitida_em)))


def emitir_dmr(
    session: Session, usuario: Usuario, veiculo_id: uuid.UUID, dados: DmrCriar, emissor: EmissorMTR
) -> Dmr:
    """RF-13, art. 6º III d; Anexo III 13 e 14.d: destinatário por tipo de material, com MTR."""
    veiculo = veiculos.obter_veiculo(session, usuario, veiculo_id, bloquear=True)
    if session.scalar(select(Dmr.id).where(Dmr.veiculo_id == veiculo.id, Dmr.numero == dados.numero)):
        raise ErroNegocio(409, "DMR_DUPLICADA", "Este veículo já tem DMR com este número.")

    empresa = session.get(Empresa, veiculo.empresa_id)
    # O número do MTR vem do SINIR, simulado atrás de EmissorMTR (app/core/integracoes.py).
    mtr = emissor.emitir(
        gerador_cnpj=empresa.cnpj,
        destinatario_cnpj=dados.destinatario_cnpj,
        tipo_material=dados.tipo_material,
        peso_kg=dados.peso_kg,
    )
    dmr = Dmr(
        veiculo=veiculo,
        numero=dados.numero,
        mtr_numero=mtr.numero,
        destinatario_nome=dados.destinatario_nome,
        destinatario_cnpj=dados.destinatario_cnpj,
        tipo_material=dados.tipo_material,
        peso_kg=quantizar_peso(dados.peso_kg),
        emitida_em=mtr.emitido_em,
    )
    session.add(dmr)
    veiculos.marcar_em_processo(veiculo)
    session.flush()
    registrar_evento(
        session,
        usuario,
        "DMR_EMITIDA",
        "dmr",
        dmr.id,
        {
            "veiculo_id": veiculo.id,
            "numero": dmr.numero,
            "mtr_numero": dmr.mtr_numero,
            "destinatario_nome": dmr.destinatario_nome,
            "destinatario_cnpj": dmr.destinatario_cnpj,
            "tipo_material": dmr.tipo_material,
            "peso_kg": dmr.peso_kg,
        },
    )
    veiculos.encerrar_se_destinado(session, usuario, veiculo)
    return dmr
