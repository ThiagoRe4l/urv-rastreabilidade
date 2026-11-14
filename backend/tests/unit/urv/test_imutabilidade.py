"""Defesa em profundidade do livro de URV no banco (migração 0002, PM-URV-05). RF-17, RF-18, RF-21."""

from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Consumo, LancamentoTipo, UrvLancamento
from scripts.seed import EMAIL_FABRICANTE
from tests.unit.urv.apoio import creditar, vins

URV = "/api/v1/urv"


@pytest.fixture
def consumo(client, auth, relogio, mmv, db_session: Session) -> Consumo:
    corpo = {"mmv_id": str(mmv.id), "periodo": "2026-11", "preco_medio": "150000.00", "chassis": vins(2)}
    r = client.post(f"{URV}/consumos", json=corpo, headers=auth(EMAIL_FABRICANTE))
    assert r.status_code == 201, r.text
    return db_session.scalar(select(Consumo))


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE consumo SET urv_debito = 0",
        "UPDATE consumo SET saldo_apos = 1000",
        "DELETE FROM consumo",
        "TRUNCATE consumo CASCADE",
        "UPDATE consumo_chassi SET chassi = 'OUTRO'",
        "DELETE FROM consumo_chassi",
        "TRUNCATE consumo_chassi",
    ],
)
def test_consumo_registrado_nao_se_altera_no_banco(db_session: Session, consumo, sql: str) -> None:
    with pytest.raises(DBAPIError, match="só de inserção"), db_session.begin_nested():
        db_session.execute(text(sql))


@pytest.mark.parametrize("tipo", [LancamentoTipo.CREDITO, LancamentoTipo.TRANSFERENCIA_ENTRADA])
def test_um_lancamento_de_cada_tipo_por_credito(db_session: Session, dados_demo, tipo) -> None:
    """Mesmo que o service falhe, o banco barra o segundo lançamento do mesmo tipo (RF-17)."""
    credito = creditar(db_session, dados_demo.desmonte_id, "9BWZZZ377VT004251")
    if tipo == LancamentoTipo.TRANSFERENCIA_ENTRADA:
        db_session.add(
            UrvLancamento(
                empresa_id=dados_demo.montadora_id,
                tipo=tipo,
                quantidade=credito.quantidade,
                credito_id=credito.id,
            )
        )
        db_session.flush()
    with pytest.raises(IntegrityError, match="uq_urv_lancamento_credito_id_tipo"), db_session.begin_nested():
        db_session.add(
            UrvLancamento(
                empresa_id=dados_demo.montadora_id,
                tipo=tipo,
                quantidade=Decimal("1.00"),
                credito_id=credito.id,
            )
        )
        db_session.flush()


def test_debitos_nao_colidem_no_indice(client, auth, relogio, mmv, db_session: Session) -> None:
    """DEBITO não tem crédito: dois consumos geram dois débitos sem colidir no índice."""
    for inicio in (1, 50):
        corpo = {
            "mmv_id": str(mmv.id),
            "periodo": "2026-11",
            "preco_medio": "150000.00",
            "chassis": vins(2, inicio),
        }
        assert client.post(f"{URV}/consumos", json=corpo, headers=auth(EMAIL_FABRICANTE)).status_code == 201
    debitos = db_session.scalars(select(UrvLancamento).where(UrvLancamento.tipo == LancamentoTipo.DEBITO))
    assert len(debitos.all()) == 2
