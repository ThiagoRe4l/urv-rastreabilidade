"""Concorrência no livro de URV, com commits reais em um banco próprio. RF-17, RF-19 e RF-21.

Cada thread usa a sua sessão e a sua transação, como duas requisições simultâneas.
"""

import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.core.erros import ErroNegocio
from app.models import (
    Consumo,
    ConsumoChassi,
    LancamentoTipo,
    TipoEmpresa,
    UrvCredito,
    UrvCreditoStatus,
    UrvLancamento,
    Usuario,
)
from app.modules.auditoria.service import verificar_cadeia
from app.modules.empresas.service import criar_vinculo
from app.modules.urv.schemas import ConsumoCriar
from app.modules.urv.service import registrar_consumo, saldo_empresa, transferir_credito
from scripts.seed import DadosDemo, semear
from tests.banco import apagar_banco, recriar_banco, url_banco_teste
from tests.unit.urv.apoio import CNPJ_IMPORTADORA, creditar, criar_empresa_com_usuario, criar_mmv, vins

EM_2027 = datetime(2027, 6, 15, 15, 0, tzinfo=UTC)
EM_2028 = datetime(2028, 2, 10, 15, 0, tzinfo=UTC)
ESPERA = 30  # segundos; um deadlock ou bloqueio preso faz o teste falhar em vez de travar


@pytest.fixture(scope="module")
def banco() -> Iterator[tuple[Engine, DadosDemo]]:
    url = url_banco_teste("_urv_concorrencia")
    recriar_banco(url)
    eng = create_engine(url, pool_size=8)
    try:
        with Session(eng) as s:
            dados = semear(s)
            s.commit()
        yield eng, dados
    finally:
        eng.dispose()
        apagar_banco(url)


def _em_paralelo(operacoes: list[Callable[[Session], None]], eng: Engine) -> list[str]:
    """Roda cada operação na sua transação, todas largando juntas. Devolve "ok" ou o código do erro."""
    resultados: list[str] = []
    inesperados: list[BaseException] = []
    barreira = threading.Barrier(len(operacoes))

    def rodar(operacao: Callable[[Session], None]) -> None:
        try:
            with Session(eng) as s:
                barreira.wait(timeout=ESPERA)
                operacao(s)
                s.commit()
            resultados.append("ok")
        except ErroNegocio as erro:
            resultados.append(erro.codigo)
        except BaseException as exc:  # noqa: BLE001
            inesperados.append(exc)

    threads = [threading.Thread(target=rodar, args=(op,)) for op in operacoes]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=ESPERA)
    assert not any(t.is_alive() for t in threads), "operações presas em bloqueio"
    assert not inesperados, inesperados
    return sorted(resultados)


def _credito_transferivel(eng: Engine, dados: DadosDemo, chassi: str) -> uuid.UUID:
    with Session(eng) as s:
        credito = creditar(s, dados.desmonte_id, chassi)
        s.commit()
        return credito.id


def test_duas_transferencias_do_mesmo_credito_so_uma_passa(banco) -> None:
    """RF-17, art. 8º §3º: a linha do crédito é travada (SELECT ... FOR UPDATE)."""
    eng, dados = banco
    credito_id = _credito_transferivel(eng, dados, "CONCORRENTE-0001")

    def transferir(s: Session) -> None:
        transferir_credito(s, s.get(Usuario, dados.operador_id), credito_id, dados.montadora_id)

    assert _em_paralelo([transferir, transferir], eng) == ["CREDITO_JA_TRANSFERIDO", "ok"]

    with Session(eng) as s:
        credito = s.get(UrvCredito, credito_id)
        assert credito.status == UrvCreditoStatus.TRANSFERIDO
        assert credito.titular_id == dados.montadora_id
        por_tipo = dict(
            s.execute(
                select(UrvLancamento.tipo, func.count())
                .where(UrvLancamento.credito_id == credito_id)
                .group_by(UrvLancamento.tipo)
            )
            .tuples()
            .all()
        )
        assert por_tipo == {
            LancamentoTipo.CREDITO: 1,
            LancamentoTipo.TRANSFERENCIA_SAIDA: 1,
            LancamentoTipo.TRANSFERENCIA_ENTRADA: 1,
        }
        assert verificar_cadeia(s).integra


def test_oito_transferencias_do_mesmo_credito_so_uma_passa(banco) -> None:
    eng, dados = banco
    credito_id = _credito_transferivel(eng, dados, "CONCORRENTE-0002")
    with Session(eng) as s:
        antes = saldo_empresa(s, dados.montadora_id)

    def transferir(s: Session) -> None:
        transferir_credito(s, s.get(Usuario, dados.operador_id), credito_id, dados.montadora_id)

    assert _em_paralelo([transferir] * 8, eng) == ["CREDITO_JA_TRANSFERIDO"] * 7 + ["ok"]

    with Session(eng) as s:
        assert saldo_empresa(s, dados.montadora_id) == antes + Decimal("1.00")  # entrou uma vez só
        assert verificar_cadeia(s).integra


def test_dois_consumos_simultaneos_nao_gastam_o_mesmo_saldo(banco) -> None:
    """RF-19, art. 8º III: o saldo é lido com a linha da empresa travada."""
    eng, dados = banco
    with Session(eng) as s:
        # Um fabricante só deste teste, com saldo de 1.00.
        fiscal = criar_empresa_com_usuario(
            s,
            cnpj=CNPJ_IMPORTADORA,
            razao_social="Importadora Z",
            tipo=TipoEmpresa.FABRICANTE,
            email="fiscal@importadora.local",
        )
        mmv_id = criar_mmv(s, fiscal.empresa_id).id
        fiscal_id, fabricante_id = fiscal.id, fiscal.empresa_id
        criar_vinculo(s, None, dados.desmonte_id, fabricante_id)
        credito = creditar(s, dados.desmonte_id, "CONCORRENTE-0003")
        transferir_credito(s, s.get(Usuario, dados.operador_id), credito.id, fabricante_id)
        s.commit()

    def consumir(inicio: int) -> Callable[[Session], None]:
        def _consumir(s: Session) -> None:
            dados_consumo = ConsumoCriar(
                mmv_id=mmv_id, periodo="2028-01", preco_medio=Decimal("150000"), chassis=vins(7, inicio)
            )
            registrar_consumo(s, s.get(Usuario, fiscal_id), dados_consumo, agora=EM_2028)

        return _consumir

    # Cada consumo debita 0.70 de um saldo de 1.00, em 2028: só um cabe.
    assert _em_paralelo([consumir(1000), consumir(2000)], eng) == ["SALDO_INSUFICIENTE", "ok"]

    with Session(eng) as s:
        assert saldo_empresa(s, fabricante_id) == Decimal("0.30")
        consumos = s.scalars(select(Consumo).where(Consumo.fabricante_id == fabricante_id)).all()
        assert [(c.urv_debito, c.saldo_apos) for c in consumos] == [(Decimal("0.70"), Decimal("0.30"))]
        assert verificar_cadeia(s).integra


def test_mesmo_chassi_em_dois_consumos_simultaneos_so_um_passa(banco) -> None:
    """RF-21, arts. 28 e 29: fabricantes diferentes não se travam; quem barra é a unicidade do chassi."""
    eng, dados = banco
    with Session(eng) as s:
        outro = s.scalar(select(Usuario).where(Usuario.email == "fiscal@importadora.local"))
        if outro is None:
            outro = criar_empresa_com_usuario(
                s,
                cnpj=CNPJ_IMPORTADORA,
                razao_social="Importadora Z",
                tipo=TipoEmpresa.FABRICANTE,
                email="fiscal@importadora.local",
            )
        mmv_outro = criar_mmv(s, outro.empresa_id, codigo="DISPUTA-B").id
        mmv_seed = criar_mmv(s, dados.montadora_id, codigo="DISPUTA-A").id
        outro_id = outro.id
        s.commit()

    disputado = vins(1, inicio=5000)

    def consumir(usuario_id: uuid.UUID, mmv_id: uuid.UUID, proprios: int) -> Callable[[Session], None]:
        def _consumir(s: Session) -> None:
            dados_consumo = ConsumoCriar(
                mmv_id=mmv_id,
                periodo="2027-05",
                preco_medio=Decimal("150000"),
                chassis=vins(3, proprios) + disputado,
            )
            registrar_consumo(s, s.get(Usuario, usuario_id), dados_consumo, agora=EM_2027)

        return _consumir

    resultado = _em_paralelo(
        [consumir(dados.fiscal_id, mmv_seed, 6000), consumir(outro_id, mmv_outro, 7000)], eng
    )
    assert resultado == ["CHASSI_JA_CONSUMIDO", "ok"]

    with Session(eng) as s:
        donos = s.scalars(
            select(ConsumoChassi.consumo_id).where(ConsumoChassi.chassi.in_(vins(3, 6000) + vins(3, 7000)))
        ).all()
        assert len(set(donos)) == 1 and len(donos) == 3  # os chassis do consumo rejeitado não ficaram
        assert (
            s.scalar(
                select(func.count()).select_from(ConsumoChassi).where(ConsumoChassi.chassi == disputado[0])
            )
            == 1
        )
        assert verificar_cadeia(s).integra
