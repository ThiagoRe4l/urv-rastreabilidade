"""Relatório ao MDIC: contagens e volumes por ano. RF-24, art. 27 I e II. Somente leitura."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.decimais import quantizar, quantizar_peso
from app.models import (
    Certificado,
    Consumo,
    DestinoPesagem,
    Fracao,
    LancamentoTipo,
    Pesagem,
    UrvCredito,
    UrvLancamento,
    Veiculo,
)
from app.modules.relatorios.schemas import MaterialSaida, RelatorioMdicSaida
from app.modules.urv.relogio import inicio_do_dia


def relatorio_mdic(session: Session, ano: int) -> RelatorioMdicSaida:
    # O ano-calendário é o de Brasília.
    inicio, fim = inicio_do_dia(date(ano, 1, 1)), inicio_do_dia(date(ano + 1, 1, 1))

    # Art. 27 I: número de registros e de certificados de reciclagem emitidos.
    registros = session.scalar(
        select(func.count())
        .select_from(Veiculo)
        .where(Veiculo.data_entrada >= date(ano, 1, 1), Veiculo.data_entrada <= date(ano, 12, 31))
    )
    no_ano = (Certificado.emitido_em >= inicio, Certificado.emitido_em < fim)
    certificados = session.scalar(select(func.count()).select_from(Certificado).where(*no_ano))

    gerada = session.scalar(
        select(func.coalesce(func.sum(UrvCredito.quantidade), 0))
        .join(Certificado, Certificado.id == UrvCredito.certificado_id)
        .where(*no_ano)
    )
    # A saída da geradora existe em toda transferência conhecida pela plataforma, inclusive nas importadas.
    transferida = session.scalar(
        select(func.coalesce(func.sum(-UrvLancamento.quantidade), 0)).where(
            UrvLancamento.tipo == LancamentoTipo.TRANSFERENCIA_SAIDA,
            UrvLancamento.criado_em >= inicio,
            UrvLancamento.criado_em < fim,
        )
    )
    consumida = session.scalar(
        select(func.coalesce(func.sum(Consumo.urv_debito), 0)).where(
            Consumo.registrado_em >= inicio, Consumo.registrado_em < fim
        )
    )

    # Art. 27 II: volume de materiais rastreados e destinados.
    linhas = session.execute(
        select(Pesagem.fracao, Pesagem.destino, func.sum(Pesagem.peso_kg))
        .where(Pesagem.criado_em >= inicio, Pesagem.criado_em < fim)
        .group_by(Pesagem.fracao, Pesagem.destino)
    ).all()
    ordem_fracao, ordem_destino = list(Fracao), list(DestinoPesagem)
    materiais = sorted(
        (MaterialSaida(fracao=f, destino=d, peso_kg=quantizar_peso(Decimal(p))) for f, d, p in linhas),
        key=lambda m: (ordem_fracao.index(m.fracao), ordem_destino.index(m.destino)),
    )

    return RelatorioMdicSaida(
        ano=ano,
        registros=registros or 0,
        certificados_emitidos=certificados or 0,
        urv_gerada=quantizar(Decimal(gerada or 0)),
        urv_transferida=quantizar(Decimal(transferida or 0)),
        urv_consumida=quantizar(Decimal(consumida or 0)),
        materiais=materiais,
        peso_total_kg=quantizar_peso(sum((m.peso_kg for m in materiais), Decimal(0))),
    )
