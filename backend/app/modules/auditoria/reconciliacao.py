"""Reconciliação dos registros de negócio. GET /auditoria/reconciliar. RF-22, RNF-01, art. 20 V; art. 24 I.

`verificar_cadeia` confere a trilha contra ela mesma; esta conferência compara os dados com o
que os sustenta (achado A4 da revisão):

1. Crédito × certificado: a quantidade do crédito é o fator do certificado, e o fator é o
   vigente para o tipo na data da emissão (RF-16, art. 3º §§1º e 2º).
2. Livro × registros: cada lançamento vale o que o crédito ou o consumo que ele referencia diz,
   e o saldo de cada empresa (soma dos lançamentos) é igual à soma recalculada dos registros
   (RF-17, RF-19, art. 8º).
3. Registros × trilha: certificado, laudo, crédito, consumo e MMV conferem com o último evento
   que os gravou ou alterou.

Só leitura. Não detecta quem reescreve a trilha e recalcula os hashes: isso pede ancoragem
externa da cadeia (lacuna L-14).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.configuracao import fator_vigente
from app.core.erros import ErroNegocio
from app.core.relogio import data_operacao
from app.models import (
    Certificado,
    Consumo,
    EventoAuditoria,
    LancamentoTipo,
    Laudo,
    Mmv,
    UrvCredito,
    UrvCreditoStatus,
    UrvLancamento,
)
from app.modules.auditoria.service import normalizar

CREDITO_FATOR = "CREDITO_FATOR"
FATOR_VIGENTE = "FATOR_VIGENTE"
LANCAMENTO = "LANCAMENTO"
SALDO = "SALDO"
TRILHA = "TRILHA"

_EVENTOS = (
    "CERTIFICADO_EMITIDO",
    "CERTIFICADO_IMPORTADO",
    "LAUDO_ASSINADO",
    "VEICULO_IMPORTADO",
    "CREDITO_GERADO",
    "CREDITO_IMPORTADO",
    "CREDITO_TRANSFERIDO",
    "URV_CONSUMIDA",
    "CONSUMO_IMPORTADO",
    "MMV_CADASTRADO",
    "MMV_IMPORTADO",
)


@dataclass(frozen=True)
class Divergencia:
    verificacao: str  # CREDITO_FATOR, FATOR_VIGENTE, LANCAMENTO, SALDO ou TRILHA
    entidade: str
    entidade_id: uuid.UUID
    detalhe: str


@dataclass
class ResultadoReconciliacao:
    verificados: dict[str, int]
    divergencias: list[Divergencia] = field(default_factory=list)

    @property
    def conciliado(self) -> bool:
        return not self.divergencias


def _igual(esperado: Any, encontrado: Any) -> bool:
    """Compara como na trilha (texto normalizado); números comparam pelo valor ("0.4" == "0.40")."""
    a, b = normalizar(esperado), normalizar(encontrado)
    if a == b:
        return True
    if isinstance(a, str) and isinstance(b, str):
        try:
            return Decimal(a) == Decimal(b)
        except InvalidOperation:
            return False
    return False


class _Conferencia:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.divergencias: list[Divergencia] = []
        self.eventos: dict[tuple[str, uuid.UUID], EventoAuditoria] = {}
        for ev in session.scalars(
            select(EventoAuditoria)
            .where(EventoAuditoria.tipo.in_(_EVENTOS))
            .order_by(EventoAuditoria.sequencia)
        ):
            if ev.entidade_id is not None:
                self.eventos[(ev.tipo, ev.entidade_id)] = ev  # fica o último de cada tipo

    def divergir(self, verificacao: str, entidade: str, entidade_id: uuid.UUID, detalhe: str) -> None:
        self.divergencias.append(Divergencia(verificacao, entidade, entidade_id, detalhe))

    def evento(self, entidade_id: uuid.UUID, *tipos: str) -> EventoAuditoria | None:
        achados = [e for t in tipos if (e := self.eventos.get((t, entidade_id))) is not None]
        return max(achados, key=lambda e: e.sequencia) if achados else None

    def contra_evento(
        self, entidade: str, entidade_id: uuid.UUID, ev: EventoAuditoria | None, campos: dict[str, Any]
    ) -> None:
        """Cada campo da tabela tem de bater com o payload do evento que o gravou."""
        if ev is None:
            self.divergir(TRILHA, entidade, entidade_id, "Registro sem evento correspondente na trilha.")
            return
        for nome, valor in campos.items():
            if nome in ev.payload and not _igual(valor, ev.payload[nome]):
                self.divergir(
                    TRILHA,
                    entidade,
                    entidade_id,
                    f"{nome} = {normalizar(valor)!r} na tabela, {ev.payload[nome]!r} no evento "
                    f"{ev.tipo} (sequência {ev.sequencia}).",
                )


def _ler(session: Session, modelo: type) -> list:
    # populate_existing: confere o que está no banco, não o que a sessão já tinha carregado.
    return list(session.scalars(select(modelo).execution_options(populate_existing=True)))


def reconciliar(session: Session) -> ResultadoReconciliacao:
    c = _Conferencia(session)
    certificados = {x.id: x for x in _ler(session, Certificado)}
    creditos = _ler(session, UrvCredito)
    laudos = _ler(session, Laudo)
    consumos = {x.id: x for x in _ler(session, Consumo)}
    mmvs = _ler(session, Mmv)
    lancamentos = _ler(session, UrvLancamento)

    # 1. Crédito × certificado (RF-16, art. 3º §§1º e 2º).
    for cert in certificados.values():
        try:
            vigente = fator_vigente(session, cert.tipo_veiculo, data_operacao(cert.emitido_em))
        except ErroNegocio:
            vigente = None
        if vigente != cert.fator:
            c.divergir(
                FATOR_VIGENTE,
                "certificado",
                cert.id,
                f"Fator {cert.fator} difere do vigente para {cert.tipo_veiculo} na emissão ({vigente}).",
            )
    for cred in creditos:
        cert = certificados[cred.certificado_id]
        if cred.quantidade != cert.fator:
            c.divergir(
                CREDITO_FATOR,
                "urv_credito",
                cred.id,
                f"Quantidade {cred.quantidade} difere do fator {cert.fator} do certificado {cert.numero}.",
            )

    # 2. Livro × registros (RF-17, RF-19, art. 8º).
    por_credito: dict[uuid.UUID, dict[LancamentoTipo, UrvLancamento]] = defaultdict(dict)
    por_consumo: dict[uuid.UUID, list[UrvLancamento]] = defaultdict(list)
    for lanc in lancamentos:
        if lanc.credito_id is not None:
            por_credito[lanc.credito_id][lanc.tipo] = lanc
        if lanc.consumo_id is not None:
            por_consumo[lanc.consumo_id].append(lanc)

    def conferir_lancamento(
        cred: UrvCredito, tipo: LancamentoTipo, valor: Decimal, empresa_id: uuid.UUID, obrigatorio: bool
    ) -> None:
        lanc = por_credito[cred.id].get(tipo)
        if lanc is None:
            if obrigatorio:
                c.divergir(LANCAMENTO, "urv_credito", cred.id, f"Falta o lançamento {tipo} do crédito.")
            return
        if lanc.quantidade != valor or lanc.empresa_id != empresa_id:
            c.divergir(
                LANCAMENTO,
                "urv_lancamento",
                lanc.id,
                f"Lançamento {tipo} de {lanc.quantidade} para {lanc.empresa_id}; o crédito pede {valor} "
                f"para {empresa_id}.",
            )

    transferido = UrvCreditoStatus.TRANSFERIDO
    for cred in creditos:
        q = cred.quantidade
        conferir_lancamento(cred, LancamentoTipo.CREDITO, q, cred.geradora_id, obrigatorio=True)
        saiu = cred.status == transferido
        conferir_lancamento(cred, LancamentoTipo.TRANSFERENCIA_SAIDA, -q, cred.geradora_id, obrigatorio=saiu)
        # Crédito importado já transferido: a entrada do fabricante só existe depois que o arquivo
        # dele também é importado (L-URV-08).
        importado = c.evento(cred.id, "CREDITO_IMPORTADO") is not None
        conferir_lancamento(
            cred, LancamentoTipo.TRANSFERENCIA_ENTRADA, q, cred.titular_id, obrigatorio=saiu and not importado
        )
        if not saiu and por_credito[cred.id].keys() - {LancamentoTipo.CREDITO}:
            c.divergir(
                LANCAMENTO, "urv_credito", cred.id, "Crédito disponível com lançamento de transferência."
            )

    for consumo in consumos.values():
        debitos = por_consumo[consumo.id]
        esperado = [-consumo.urv_debito] if consumo.urv_debito > 0 else []
        if [d.quantidade for d in debitos] != esperado or any(
            d.empresa_id != consumo.fabricante_id for d in debitos
        ):
            c.divergir(
                LANCAMENTO,
                "consumo",
                consumo.id,
                f"Débito do consumo {consumo.urv_debito}; no livro {[str(d.quantidade) for d in debitos]}.",
            )

    # Saldo de cada empresa: soma dos lançamentos × soma do que os registros dizem que eles valem.
    valor_credito = {cred.id: cred.quantidade for cred in creditos}
    sinal = {
        LancamentoTipo.CREDITO: 1,
        LancamentoTipo.TRANSFERENCIA_ENTRADA: 1,
        LancamentoTipo.TRANSFERENCIA_SAIDA: -1,
    }
    saldo_livro: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    saldo_registros: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for lanc in lancamentos:
        saldo_livro[lanc.empresa_id] += lanc.quantidade
        if lanc.tipo == LancamentoTipo.DEBITO:
            saldo_registros[lanc.empresa_id] -= consumos[lanc.consumo_id].urv_debito
        else:
            saldo_registros[lanc.empresa_id] += sinal[lanc.tipo] * valor_credito[lanc.credito_id]
    for empresa_id, saldo in saldo_livro.items():
        if saldo != saldo_registros[empresa_id]:
            c.divergir(
                SALDO,
                "empresa",
                empresa_id,
                f"Saldo do livro {saldo}; pelos créditos e consumos {saldo_registros[empresa_id]}.",
            )

    # 3. Registros × trilha (RF-22, art. 20 V).
    for cert in certificados.values():
        campos = {
            "numero": cert.numero,
            "tipo_veiculo": cert.tipo_veiculo,
            "fator": cert.fator,
            "hash_conteudo": cert.hash_conteudo,
        }
        c.contra_evento(
            "certificado", cert.id, c.evento(cert.id, "CERTIFICADO_EMITIDO", "CERTIFICADO_IMPORTADO"), campos
        )
    for laudo in laudos:
        ev = c.evento(laudo.id, "LAUDO_ASSINADO")
        if ev is not None:
            campos = {
                "hash_conteudo": laudo.hash_conteudo,
                "responsavel_nome": laudo.responsavel_nome,
                "responsavel_registro": laudo.responsavel_registro,
            }
            c.contra_evento("laudo", laudo.id, ev, campos)
        else:  # laudo importado: o hash está no evento do veículo
            c.contra_evento(
                "laudo",
                laudo.id,
                c.evento(laudo.veiculo_id, "VEICULO_IMPORTADO"),
                {"laudo_hash": laudo.hash_conteudo},
            )
    for cred in creditos:
        origem = c.evento(cred.id, "CREDITO_GERADO", "CREDITO_IMPORTADO")
        c.contra_evento(
            "urv_credito", cred.id, origem, {"quantidade": cred.quantidade, "geradora_id": cred.geradora_id}
        )
        transferencia = c.evento(cred.id, "CREDITO_TRANSFERIDO")
        if transferencia is not None:
            esperado_status, esperado_titular = transferido, transferencia.payload.get("fabricante_id")
        elif origem is not None and origem.tipo == "CREDITO_IMPORTADO":
            esperado_status, esperado_titular = origem.payload.get("status"), origem.payload.get("titular_id")
        else:
            esperado_status, esperado_titular = UrvCreditoStatus.DISPONIVEL, cred.geradora_id
        if not _igual(cred.status, esperado_status) or not _igual(cred.titular_id, esperado_titular):
            c.divergir(
                TRILHA,
                "urv_credito",
                cred.id,
                f"Status {cred.status} e titular {cred.titular_id} na tabela; a trilha diz "
                f"{normalizar(esperado_status)} e {normalizar(esperado_titular)}.",
            )
    for consumo in consumos.values():
        campos = {
            "periodo": consumo.periodo,
            "qv": consumo.qv,
            "rm": consumo.rm,
            "pm": consumo.pm,
            "pb": consumo.pb,
            "urv_debito": consumo.urv_debito,
        }
        c.contra_evento(
            "consumo", consumo.id, c.evento(consumo.id, "URV_CONSUMIDA", "CONSUMO_IMPORTADO"), campos
        )
    for mmv in mmvs:
        campos = {"codigo": mmv.codigo, "ncm": mmv.ncm, "nivel": mmv.nivel}
        c.contra_evento("mmv", mmv.id, c.evento(mmv.id, "MMV_CADASTRADO", "MMV_IMPORTADO"), campos)

    return ResultadoReconciliacao(
        verificados={
            "certificados": len(certificados),
            "laudos": len(laudos),
            "creditos": len(creditos),
            "lancamentos": len(lancamentos),
            "consumos": len(consumos),
            "mmvs": len(mmvs),
            "empresas": len(saldo_livro),
        },
        divergencias=c.divergencias,
    )
