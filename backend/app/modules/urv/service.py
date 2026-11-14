"""Livro de URV. Dono: backend-urv (agente 02).

`gerar_credito` é o ponto de contato com o fluxo do veículo (docs/02-arquitetura.md):
a fundação fixa a assinatura; o agente 02 implementa; o agente 01 só chama.

O saldo nunca é um campo: é a soma de `urv_lancamento`, tabela só de inserção.
Services não fazem commit; a rota faz (ver app/core/db.py).

Ordem de bloqueios, igual em todas as operações, para não haver deadlock:
linha do crédito → linhas de empresa (em ordem de id) → cadeia de auditoria (`registrar_evento`).
"""

import uuid
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.configuracao import fim_saldo_negativo, preco_base_vigente, rm_vigente
from app.core.decimais import quantizar
from app.core.erros import ErroNegocio, NaoEncontrado
from app.core.relogio import data_operacao
from app.models import (
    Certificado,
    Consumo,
    ConsumoChassi,
    Empresa,
    LancamentoTipo,
    Mmv,
    MmvStatus,
    TipoEmpresa,
    UrvCredito,
    UrvCreditoStatus,
    UrvLancamento,
    Usuario,
)
from app.modules.auditoria.service import registrar_evento
from app.modules.empresas.schemas import EmpresaResumo
from app.modules.empresas.service import vinculo_ativo
from app.modules.urv.calculo import (
    calcular_debito,
    decimo_dia_util,
    multiplicador_preco,
    regularizar_ate,
)
from app.modules.urv.schemas import (
    CertificadoResumo,
    ConsumoCriar,
    ConsumoSaida,
    ConsumoSimular,
    CreditoSaida,
    LancamentoSaida,
    MemoriaCalculo,
    SaldoSaida,
    SimulacaoSaida,
    normalizar_chassi,
)

FORMULA_DEBITO = "urv_debito = (qv_periodo / rm) * max(1, pm / pb) - debito_ja_registrado_no_periodo"
QUATRO_CASAS = Decimal("0.0001")
_UNICIDADE_CHASSI = "uq_consumo_chassi_chassi"


# --- Saldo e bloqueios ------------------------------------------------------------------------


def travar_empresas(session: Session, *empresa_ids: uuid.UUID) -> None:
    """Trava as linhas das empresas até o fim da transação, sempre em ordem de id. RF-19.

    `FOR NO KEY UPDATE` serializa quem lê e altera o saldo sem barrar as chaves estrangeiras
    que apontam para a empresa (um certificado sendo emitido, por exemplo).
    """
    for empresa_id in sorted(set(empresa_ids)):
        session.execute(select(Empresa.id).where(Empresa.id == empresa_id).with_for_update(key_share=True))


def saldo_empresa(session: Session, empresa_id: uuid.UUID) -> Decimal:
    """Soma dos lançamentos da empresa. RF-19, art. 8º III. Para decidir, trave a empresa antes."""
    total = session.scalar(
        select(func.coalesce(func.sum(UrvLancamento.quantidade), 0)).where(
            UrvLancamento.empresa_id == empresa_id
        )
    )
    return quantizar(Decimal(total or 0))


def prazo_de_regularizacao(session: Session, empresa_id: uuid.UUID, saldo: Decimal) -> date | None:
    """Prazo do saldo devedor em aberto: o do consumo que levou o saldo de >= 0 para < 0.

    RF-19, art. 8º §1º. O saldo de um fabricante só diminui por consumo, então o saldo devedor
    atual começou no consumo mais recente que cruzou o zero; os consumos seguintes têm prazo maior.
    """
    if saldo >= 0:
        return None
    return session.scalar(
        select(Consumo.regularizar_ate)
        .where(
            Consumo.fabricante_id == empresa_id,
            Consumo.saldo_apos < 0,
            Consumo.saldo_apos + Consumo.urv_debito >= 0,
        )
        .order_by(Consumo.registrado_em.desc(), Consumo.criado_em.desc())
        .limit(1)
    )


def consultar_saldo(session: Session, empresa_id: uuid.UUID) -> SaldoSaida:
    if session.get(Empresa, empresa_id) is None:
        raise NaoEncontrado("Empresa")
    saldo = saldo_empresa(session, empresa_id)
    return SaldoSaida(
        empresa_id=empresa_id,
        saldo=saldo,
        regularizar_ate=prazo_de_regularizacao(session, empresa_id, saldo),
    )


def _empresa_do_usuario(usuario: Usuario) -> uuid.UUID:
    if usuario.empresa_id is None:
        raise ErroNegocio(403, "PAPEL_NAO_PERMITIDO", "Ação permitida apenas para usuário de empresa.")
    return usuario.empresa_id


# --- Crédito (RF-16) --------------------------------------------------------------------------


def gerar_credito(
    session: Session, certificado: Certificado, *, usuario: Usuario | None = None
) -> UrvCredito:
    """Cria o crédito do certificado e o lançamento CREDITO da geradora, sem commit.

    RF-16, art. 3º §§1º e 2º; art. 18 §3º; art. 8º I.

    - `quantidade` = `certificado.fator` (crédito indivisível, um por certificado).
    - `geradora_id` = `titular_id` = `certificado.empresa_id`; status DISPONIVEL.
    - Um `UrvLancamento` tipo CREDITO, quantidade positiva, `credito_id` preenchido.
    - Registra evento de auditoria na mesma transação.
    - Rejeita certificado que já tem crédito.

    `usuario` é opcional e só identifica o autor no evento de auditoria.
    Não trava linhas de empresa: quem chama pode já ter registrado eventos na transação.
    """
    if certificado.id is None:
        session.flush()
    if certificado.id is None:
        raise ValueError("O certificado precisa estar na sessão antes de gerar o crédito.")

    # RF-21, arts. 28 e 29: um certificado (um chassi) gera crédito uma única vez.
    ja_existe = session.scalar(select(UrvCredito.id).where(UrvCredito.certificado_id == certificado.id))
    if ja_existe is not None:
        raise ErroNegocio(
            409, "CERTIFICADO_JA_CREDITADO", "Este certificado já gerou crédito de URV (arts. 28 e 29)."
        )

    quantidade = quantizar(certificado.fator)  # RF-16, art. 3º §§1º e 2º
    if quantidade <= 0:
        raise ErroNegocio(422, "FATOR_INVALIDO", "O fator do certificado precisa ser positivo.")

    credito = UrvCredito(
        certificado_id=certificado.id,
        certificado=certificado,
        geradora_id=certificado.empresa_id,
        titular_id=certificado.empresa_id,  # premissa: o titular é quem emite o certificado
        quantidade=quantidade,
        status=UrvCreditoStatus.DISPONIVEL,
    )
    session.add(credito)
    session.flush()
    session.add(
        UrvLancamento(
            empresa_id=certificado.empresa_id,
            tipo=LancamentoTipo.CREDITO,
            quantidade=quantidade,
            credito_id=credito.id,
            criado_em=certificado.emitido_em,
        )
    )
    session.flush()
    registrar_evento(
        session,
        usuario,
        "CREDITO_GERADO",
        "urv_credito",
        credito.id,
        {
            "certificado_id": certificado.id,
            "certificado_numero": certificado.numero,
            "veiculo_id": certificado.veiculo_id,
            "tipo_veiculo": certificado.tipo_veiculo,
            "quantidade": quantidade,
            "geradora_id": certificado.empresa_id,
        },
        empresa_id=certificado.empresa_id,
    )
    return credito


# --- Transferência (RF-17) --------------------------------------------------------------------


def transferir_credito(
    session: Session,
    usuario: Usuario,
    credito_id: uuid.UUID,
    fabricante_id: uuid.UUID,
    *,
    agora: datetime | None = None,
) -> UrvCredito:
    """Transfere o crédito inteiro, uma única vez, da geradora ao fabricante com vínculo.

    RF-17, art. 8º II e §3º: direta, sem intermediário. Só a geradora transfere, e só enquanto
    é a titular; quem recebe é fabricante, que não tem rota de transferência.
    """
    agora = agora or datetime.now(UTC)
    solicitante_id = _empresa_do_usuario(usuario)

    # SELECT ... FOR UPDATE: a segunda transferência concorrente espera a primeira e relê o status.
    credito = session.scalar(
        select(UrvCredito)
        .where(UrvCredito.id == credito_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if credito is None or credito.geradora_id != solicitante_id:
        raise NaoEncontrado("Crédito")
    if credito.status != UrvCreditoStatus.DISPONIVEL or credito.titular_id != solicitante_id:
        raise ErroNegocio(
            409,
            "CREDITO_JA_TRANSFERIDO",
            "Este crédito já foi transferido; a transferência é única (art. 8º §3º).",
        )

    fabricante = session.get(Empresa, fabricante_id)
    if (
        fabricante is None
        or fabricante.tipo != TipoEmpresa.FABRICANTE
        or not vinculo_ativo(session, solicitante_id, fabricante_id)
    ):
        raise ErroNegocio(
            422,
            "SEM_VINCULO",
            "Não há vínculo ativo com este fabricante ou importador (art. 8º II; art. 13 §2º).",
        )
    if not fabricante.registro_compromissos:
        raise ErroNegocio(
            422,
            "FABRICANTE_SEM_REGISTRO_COMPROMISSOS",
            "O fabricante ou importador não tem ato de registro de compromissos no MDIC (art. 8º II).",
        )

    travar_empresas(session, solicitante_id, fabricante.id)

    credito.status = UrvCreditoStatus.TRANSFERIDO
    credito.titular_id = fabricante.id  # art. 8º II: o fabricante adquire a titularidade
    session.add_all(
        [
            UrvLancamento(
                empresa_id=solicitante_id,
                tipo=LancamentoTipo.TRANSFERENCIA_SAIDA,
                quantidade=-credito.quantidade,
                credito_id=credito.id,
                contraparte_id=fabricante.id,
                criado_em=agora,
            ),
            UrvLancamento(
                empresa_id=fabricante.id,
                tipo=LancamentoTipo.TRANSFERENCIA_ENTRADA,
                quantidade=credito.quantidade,
                credito_id=credito.id,
                contraparte_id=solicitante_id,
                criado_em=agora,
            ),
        ]
    )
    session.flush()
    registrar_evento(
        session,
        usuario,
        "CREDITO_TRANSFERIDO",
        "urv_credito",
        credito.id,
        {
            "certificado_id": credito.certificado_id,
            "quantidade": credito.quantidade,
            "geradora_id": solicitante_id,
            "fabricante_id": fabricante.id,
        },
    )
    return credito


# --- Consumo (RF-18 a RF-21) ------------------------------------------------------------------


def _mmv_do_fabricante(session: Session, mmv_id: uuid.UUID, fabricante_id: uuid.UUID) -> Mmv:
    mmv = session.get(Mmv, mmv_id)
    if mmv is None or mmv.fabricante_id != fabricante_id:
        raise NaoEncontrado("MMV")
    return mmv


@dataclass(frozen=True)
class DebitoNoPeriodo:
    """Débito de um consumo dentro do acumulado do MMV no período. RF-18, art. 3º §§3º e 4º."""

    debito: Decimal
    qv_periodo: int  # Qv acumulado, contando este consumo
    ja_debitado: Decimal
    rm: int
    pm: Decimal
    pb: Decimal


def debito_no_periodo(
    session: Session,
    fabricante_id: uuid.UUID,
    mmv: Mmv,
    periodo: str,
    qv: int,
    pm: Decimal,
    *,
    rm: int,
    pb: Decimal,
) -> DebitoNoPeriodo:
    """Débito do consumo = débito do Qv acumulado do MMV no período menos o já debitado nele.

    RF-18, art. 3º §3º: Qv é a quantidade comercializada do MMV, não o lote que o fabricante
    escolhe registrar; o arredondamento é um só, sobre o acumulado (achado A3 da revisão).
    Art. 3º §4º: Pm é um só por MMV e período; Pm diferente é rejeitado (422 PM_DIVERGENTE_NO_PERIODO).
    RM e Pb ficam os do primeiro consumo do período, para o acumulado ser uma conta só.
    Para valer sob concorrência, trave a linha do fabricante antes (`travar_empresas`).
    """
    anteriores = session.scalars(
        select(Consumo)
        .where(Consumo.fabricante_id == fabricante_id, Consumo.mmv_id == mmv.id, Consumo.periodo == periodo)
        .order_by(Consumo.registrado_em, Consumo.criado_em)
    ).all()
    pm = quantizar(pm)
    if anteriores:
        primeiro = anteriores[0]
        if pm != primeiro.pm:
            raise ErroNegocio(
                422,
                "PM_DIVERGENTE_NO_PERIODO",
                f"O MMV {mmv.codigo} já tem consumo em {periodo} com Pm {primeiro.pm}; o preço médio é um "
                "só por MMV e período (art. 3º §4º).",
            )
        rm, pb = primeiro.rm, primeiro.pb
    qv_periodo = sum(c.qv for c in anteriores) + qv
    ja_debitado = sum((c.urv_debito for c in anteriores), Decimal("0.00"))
    debito = calcular_debito(qv_periodo, rm, pm, pb) - ja_debitado
    return DebitoNoPeriodo(
        debito=quantizar(debito),
        qv_periodo=qv_periodo,
        ja_debitado=ja_debitado,
        rm=rm,
        pm=pm,
        pb=quantizar(pb),
    )


def _memoria(qv_consumo: int, mmv: Mmv, d: DebitoNoPeriodo) -> MemoriaCalculo:
    return MemoriaCalculo(
        formula=FORMULA_DEBITO,
        qv=d.qv_periodo,
        qv_consumo=qv_consumo,
        debito_ja_registrado=d.ja_debitado,
        nivel=mmv.nivel,
        rm=d.rm,
        pm=d.pm,
        pb=d.pb,
        razao_preco=quantizar(d.pm / d.pb, QUATRO_CASAS),
        multiplicador=quantizar(multiplicador_preco(d.pm, d.pb), QUATRO_CASAS),
    )


def simular_consumo(
    session: Session, usuario: Usuario, dados: ConsumoSimular, *, agora: datetime
) -> SimulacaoSaida:
    """Calcula o débito e o saldo resultante sem gravar nada. RF-18, art. 3º §3º."""
    fabricante_id = _empresa_do_usuario(usuario)
    mmv = _mmv_do_fabricante(session, dados.mmv_id, fabricante_id)
    hoje = data_operacao(agora)
    pb = preco_base_vigente(session, hoje)
    rm = rm_vigente(session, mmv.nivel, hoje)  # RF-18, art. 3º §3º; L-01
    if dados.periodo is not None:  # RF-18, art. 3º §3º: no acumulado do MMV no período
        calculo = debito_no_periodo(
            session, fabricante_id, mmv, dados.periodo, dados.quantidade, dados.preco_medio, rm=rm, pb=pb
        )
    else:
        bruto = calcular_debito(dados.quantidade, rm, dados.preco_medio, pb)
        calculo = DebitoNoPeriodo(
            bruto, dados.quantidade, Decimal("0.00"), rm, quantizar(dados.preco_medio), quantizar(pb)
        )
    debito = calculo.debito
    saldo = saldo_empresa(session, fabricante_id)
    limite = fim_saldo_negativo(session, hoje)
    suficiente = saldo >= debito
    permitido = suficiente or hoje <= limite  # RF-19, art. 8º III e §1º
    return SimulacaoSaida(
        urv_debito=debito,
        saldo_atual=saldo,
        saldo_apos=saldo - debito,
        saldo_suficiente=suficiente,
        permitido=permitido,
        regularizar_ate=regularizar_ate(hoje) if (not suficiente and permitido) else None,
        prazo_saldo_negativo=limite,
        memoria_calculo=_memoria(dados.quantidade, mmv, calculo),
    )


def registrar_consumo(
    session: Session, usuario: Usuario, dados: ConsumoCriar, *, agora: datetime | None = None
) -> Consumo:
    """Registra o consumo de URV pelos chassis de veículos novos de um MMV. RF-18 a RF-21."""
    agora = agora or datetime.now(UTC)
    hoje = data_operacao(agora)
    fabricante_id = _empresa_do_usuario(usuario)
    mmv = _mmv_do_fabricante(session, dados.mmv_id, fabricante_id)

    # RF-04, art. 5º §§2º a 4º: o MMV precisa estar no programa e já produzir efeitos.
    if mmv.status != MmvStatus.ATIVO:
        raise ErroNegocio(422, "MMV_SEM_EFEITOS", "O MMV foi retirado do programa (art. 5º §4º).")
    if hoje < mmv.efeitos_a_partir_de:
        raise ErroNegocio(
            422,
            "MMV_SEM_EFEITOS",
            f"O MMV só produz efeitos a partir de {mmv.efeitos_a_partir_de.isoformat()} (art. 5º §2º).",
        )

    chassis = list(dados.chassis)
    repetidos = sorted(c for c, n in Counter(chassis).items() if n > 1)
    if repetidos:
        raise ErroNegocio(
            422, "CHASSI_REPETIDO_NA_LISTA", "Chassi informado mais de uma vez: " + _resumir(repetidos)
        )

    # RF-19: o saldo é lido com a linha da empresa travada, até o commit.
    travar_empresas(session, fabricante_id)

    # RF-21, arts. 28 e 29: cada chassi de veículo novo consome uma única vez.
    ja_consumidos = session.scalars(
        select(ConsumoChassi.chassi).where(ConsumoChassi.chassi.in_(chassis)).order_by(ConsumoChassi.chassi)
    ).all()
    if ja_consumidos:
        raise _chassi_ja_consumido(ja_consumidos)

    # RF-18, art. 3º §§3º a 5º: débito no acumulado do MMV no período, com Pm único (A3 da revisão).
    calculo = debito_no_periodo(
        session,
        fabricante_id,
        mmv,
        dados.periodo,
        len(chassis),
        dados.preco_medio,
        rm=rm_vigente(session, mmv.nivel, hoje),  # L-01
        pb=preco_base_vigente(session, hoje),  # art. 3º §5º
    )
    debito, rm, pb = calculo.debito, calculo.rm, calculo.pb

    saldo = saldo_empresa(session, fabricante_id)
    prazo_regularizacao: date | None = None
    if saldo < debito:
        # RF-19, art. 8º III e §1º: saldo negativo só até a data de config_parametro.
        if hoje > fim_saldo_negativo(session, hoje):
            raise ErroNegocio(
                409,
                "SALDO_INSUFICIENTE",
                f"Saldo de {saldo} URV insuficiente para o débito de {debito} URV (art. 8º III).",
            )
        prazo_regularizacao = regularizar_ate(hoje)

    consumo = Consumo(
        fabricante_id=fabricante_id,
        mmv_id=mmv.id,
        periodo=dados.periodo,
        qv=len(chassis),
        rm=rm,
        pm=calculo.pm,
        pb=pb,
        urv_debito=debito,
        saldo_apos=saldo - debito,
        regularizar_ate=prazo_regularizacao,
        prazo_reporte=decimo_dia_util(dados.periodo),  # RF-20, art. 7º, parágrafo único
        registrado_em=agora,
        chassis=[ConsumoChassi(chassi=c) for c in chassis],
    )
    try:
        with session.begin_nested():
            session.add(consumo)
            session.flush()
    except IntegrityError as exc:
        # Outra transação consumiu um dos chassis entre a consulta e a gravação.
        if _UNICIDADE_CHASSI in str(exc.orig):
            raise _chassi_ja_consumido([]) from exc
        raise

    if debito > 0:  # o acumulado só cresce; débito zero não tem lançamento (sinal do livro)
        session.add(
            UrvLancamento(
                empresa_id=fabricante_id,
                tipo=LancamentoTipo.DEBITO,
                quantidade=-debito,
                consumo_id=consumo.id,
                criado_em=agora,
            )
        )
    session.flush()
    registrar_evento(
        session,
        usuario,
        "URV_CONSUMIDA",
        "consumo",
        consumo.id,
        {
            "mmv_id": mmv.id,
            "mmv_codigo": mmv.codigo,
            "periodo": consumo.periodo,
            "qv": consumo.qv,
            "rm": rm,
            "pm": consumo.pm,
            "pb": consumo.pb,
            "urv_debito": debito,
            "qv_periodo": calculo.qv_periodo,
            "debito_ja_registrado_no_periodo": calculo.ja_debitado,
            "saldo_antes": saldo,
            "saldo_apos": consumo.saldo_apos,
            "regularizar_ate": prazo_regularizacao,
            "prazo_reporte": consumo.prazo_reporte,
            "fora_do_prazo": fora_do_prazo(consumo),
            "chassis": chassis,
        },
    )
    return consumo


def fora_do_prazo(consumo: Consumo) -> bool:
    """RF-20, art. 7º: registrado depois do décimo dia útil do mês seguinte ao período."""
    return data_operacao(consumo.registrado_em) > consumo.prazo_reporte


def _resumir(chassis: Sequence[str], limite: int = 10) -> str:
    texto = ", ".join(chassis[:limite])
    return texto if len(chassis) <= limite else f"{texto} e mais {len(chassis) - limite}"


def _chassi_ja_consumido(chassis: Sequence[str]) -> ErroNegocio:
    detalhe = f": {_resumir(chassis)}" if chassis else ""
    return ErroNegocio(
        409,
        "CHASSI_JA_CONSUMIDO",
        f"Chassi de veículo novo já usado em outro consumo{detalhe} (arts. 28 e 29).",
    )


# --- Consultas --------------------------------------------------------------------------------


def consulta_lancamentos(empresa_id: uuid.UUID | None, tipo: LancamentoTipo | None) -> Select:
    stmt = select(UrvLancamento).order_by(UrvLancamento.criado_em.desc(), UrvLancamento.id)
    if empresa_id is not None:
        stmt = stmt.where(UrvLancamento.empresa_id == empresa_id)
    if tipo is not None:
        stmt = stmt.where(UrvLancamento.tipo == tipo)
    return stmt


def consulta_creditos(empresa_id: uuid.UUID | None, status: UrvCreditoStatus | None) -> Select:
    """Créditos gerados pela empresa ou de que ela é titular."""
    stmt = (
        select(UrvCredito)
        .options(selectinload(UrvCredito.certificado).selectinload(Certificado.veiculo))
        .order_by(UrvCredito.criado_em.desc(), UrvCredito.id)
    )
    if empresa_id is not None:
        stmt = stmt.where(or_(UrvCredito.geradora_id == empresa_id, UrvCredito.titular_id == empresa_id))
    if status is not None:
        stmt = stmt.where(UrvCredito.status == status)
    return stmt


def consulta_consumos(fabricante_id: uuid.UUID | None, chassi: str | None = None) -> Select:
    stmt = (
        select(Consumo)
        .options(selectinload(Consumo.chassis))
        .order_by(Consumo.registrado_em.desc(), Consumo.id)
    )
    if fabricante_id is not None:
        stmt = stmt.where(Consumo.fabricante_id == fabricante_id)
    if chassi and chassi.strip():
        # PM-WEB-06, RF-23: em que consumo um chassi de veículo novo foi usado (RF-21: no máximo um).
        stmt = stmt.where(
            Consumo.id.in_(
                select(ConsumoChassi.consumo_id).where(ConsumoChassi.chassi == normalizar_chassi(chassi))
            )
        )
    return stmt


def _empresas(session: Session, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, EmpresaResumo]:
    procurados = {i for i in ids if i is not None}
    if not procurados:
        return {}
    linhas = session.scalars(select(Empresa).where(Empresa.id.in_(procurados))).all()
    return {e.id: EmpresaResumo.model_validate(e) for e in linhas}


def montar_lancamentos(session: Session, lancamentos: Sequence[UrvLancamento]) -> list[LancamentoSaida]:
    empresas = _empresas(session, (lanc.contraparte_id for lanc in lancamentos))
    return [
        LancamentoSaida(
            id=lanc.id,
            empresa_id=lanc.empresa_id,
            tipo=lanc.tipo,
            quantidade=lanc.quantidade,
            credito_id=lanc.credito_id,
            consumo_id=lanc.consumo_id,
            contraparte_id=lanc.contraparte_id,
            contraparte=empresas.get(lanc.contraparte_id) if lanc.contraparte_id else None,
            criado_em=lanc.criado_em,
        )
        for lanc in lancamentos
    ]


def montar_creditos(session: Session, creditos: Sequence[UrvCredito]) -> list[CreditoSaida]:
    empresas = _empresas(session, [i for c in creditos for i in (c.geradora_id, c.titular_id)])
    saida = []
    for c in creditos:
        cert = c.certificado
        saida.append(
            CreditoSaida(
                id=c.id,
                certificado_id=c.certificado_id,
                certificado=CertificadoResumo(
                    id=cert.id,
                    numero=cert.numero,
                    tipo_veiculo=cert.tipo_veiculo,
                    fator=cert.fator,
                    emitido_em=cert.emitido_em,
                ),
                chassi=cert.veiculo.chassi,
                geradora_id=c.geradora_id,
                geradora=empresas[c.geradora_id],
                titular_id=c.titular_id,
                titular=empresas[c.titular_id],
                quantidade=c.quantidade,
                status=c.status,
                criado_em=c.criado_em,
            )
        )
    return saida


def montar_consumos(session: Session, consumos: Sequence[Consumo]) -> list[ConsumoSaida]:
    mmv_ids = {c.mmv_id for c in consumos}
    codigos: dict[uuid.UUID, str] = {}
    if mmv_ids:
        codigos = dict(session.execute(select(Mmv.id, Mmv.codigo).where(Mmv.id.in_(mmv_ids))).tuples().all())
    return [
        ConsumoSaida(
            id=c.id,
            fabricante_id=c.fabricante_id,
            mmv_id=c.mmv_id,
            mmv_codigo=codigos.get(c.mmv_id),
            periodo=c.periodo,
            qv=c.qv,
            rm=c.rm,
            pm=c.pm,
            pb=c.pb,
            urv_debito=c.urv_debito,
            saldo_apos=c.saldo_apos,
            regularizar_ate=c.regularizar_ate,
            prazo_reporte=c.prazo_reporte,
            registrado_em=c.registrado_em,
            fora_do_prazo=fora_do_prazo(c),
            chassis=sorted(ch.chassi for ch in c.chassis),
        )
        for c in consumos
    ]
