"""Relatório ao MDIC: contagens e volumes por ano. RF-24, art. 27 I e II."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models import (
    DestinoPesagem,
    DocumentoEntradaTipo,
    Fracao,
    OrigemAquisicao,
    Pesagem,
    TipoVeiculo,
    Veiculo,
)
from app.modules.urv.schemas import ConsumoCriar
from app.modules.urv.service import registrar_consumo, transferir_credito
from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA, EMAIL_FABRICANTE
from tests.unit.urv.apoio import HOJE, creditar, vins

RELATORIO = "/api/v1/relatorios/mdic"

EM_2027 = datetime(2027, 3, 10, 15, 0, tzinfo=UTC)


@pytest.fixture
def cenario(db_session, dados_demo, operador, fiscal, mmv) -> None:
    """2026: três veículos, dois certificados, um crédito transferido, um consumo e três pesagens.
    2027: um certificado, uma transferência e um consumo."""
    desmonte = dados_demo.desmonte_id
    a = creditar(db_session, desmonte, "CHASSI-A", tipo=TipoVeiculo.SINISTRADO_GRANDE, fator=Decimal("0.79"))
    creditar(db_session, desmonte, "CHASSI-B", tipo=TipoVeiculo.SUCATA_INSERVIVEL, fator=Decimal("0.38"))
    db_session.add(
        Veiculo(  # recebido em 2026, ainda sem certificado
            empresa_id=desmonte,
            chassi="CHASSI-C",
            data_entrada=date(2026, 12, 31),
            tipo_declarado=TipoVeiculo.SUCATA_INSERVIVEL,
            tipo=TipoVeiculo.SUCATA_INSERVIVEL,
            origem_aquisicao=OrigemAquisicao.LEILAO_SEGURADORA,
            documento_entrada_tipo=DocumentoEntradaTipo.AUTO_ARREMATACAO,
            documento_entrada_numero="AA-9",
        )
    )
    transferir_credito(db_session, operador, a.id, dados_demo.montadora_id, agora=HOJE)
    registrar_consumo(
        db_session,
        fiscal,
        ConsumoCriar(mmv_id=mmv.id, periodo="2026-10", preco_medio=Decimal("180000"), chassis=vins(5)),
        agora=HOJE,
    )
    veiculo_a = a.certificado.veiculo_id
    for fracao, destino, peso, quando in (
        (Fracao.FERROSO, DestinoPesagem.RECICLAGEM, "700.500", HOJE),
        (Fracao.FERROSO, DestinoPesagem.RECICLAGEM, "100.250", HOJE),
        (Fracao.FLUIDOS, DestinoPesagem.REJEITO, "12.125", HOJE),
        (Fracao.PNEUS, DestinoPesagem.RECUPERACAO_ENERGETICA, "40.000", EM_2027),
    ):
        db_session.add(
            Pesagem(
                veiculo_id=veiculo_a, fracao=fracao, destino=destino, peso_kg=Decimal(peso), criado_em=quando
            )
        )

    # 23h de 31/12/2026 em Brasília já é 2027 em UTC: conta em 2026.
    virada = datetime(2027, 1, 1, 2, 0, tzinfo=UTC)
    creditar(db_session, desmonte, "CHASSI-D", emitido_em=virada)

    c = creditar(db_session, desmonte, "CHASSI-E", emitido_em=EM_2027)
    transferir_credito(db_session, operador, c.id, dados_demo.montadora_id, agora=EM_2027)
    registrar_consumo(
        db_session,
        fiscal,
        ConsumoCriar(mmv_id=mmv.id, periodo="2027-02", preco_medio=Decimal("150000"), chassis=vins(3, 100)),
        agora=EM_2027,
    )
    db_session.flush()


def test_relatorio_de_2026(client, auth, cenario) -> None:
    r = client.get(RELATORIO, params={"ano": 2026}, headers=auth(EMAIL_AUDITOR))
    assert r.status_code == 200, r.text
    assert r.json() == {
        "ano": 2026,
        "registros": 5,  # veículos com entrada em 2026 (os de apoio entram em 10/11/2026)
        "certificados_emitidos": 3,  # A, B e o emitido às 23h de 31/12 em Brasília
        "urv_gerada": "2.17",  # 0.79 + 0.38 + 1.00
        "urv_transferida": "0.79",
        "urv_consumida": "0.60",  # (5 / 10) * 1.2
        "materiais": [
            {"fracao": "FERROSO", "destino": "RECICLAGEM", "peso_kg": "800.750"},
            {"fracao": "FLUIDOS", "destino": "REJEITO", "peso_kg": "12.125"},
        ],
        "peso_total_kg": "812.875",
    }


def test_relatorio_de_2027(client, auth, cenario) -> None:
    r = client.get(RELATORIO, params={"ano": 2027}, headers=auth(EMAIL_ADMIN))
    assert r.json() == {
        "ano": 2027,
        "registros": 0,
        "certificados_emitidos": 1,
        "urv_gerada": "1.00",
        "urv_transferida": "1.00",
        "urv_consumida": "0.30",
        "materiais": [{"fracao": "PNEUS", "destino": "RECUPERACAO_ENERGETICA", "peso_kg": "40.000"}],
        "peso_total_kg": "40.000",
    }


def test_ano_sem_movimento_e_ano_padrao(client, auth, relogio, cenario) -> None:
    r = client.get(RELATORIO, params={"ano": 2030}, headers=auth(EMAIL_AUDITOR))
    assert r.json() == {
        "ano": 2030,
        "registros": 0,
        "certificados_emitidos": 0,
        "urv_gerada": "0.00",
        "urv_transferida": "0.00",
        "urv_consumida": "0.00",
        "materiais": [],
        "peso_total_kg": "0.000",
    }
    assert client.get(RELATORIO, headers=auth(EMAIL_AUDITOR)).json()["ano"] == 2026  # o ano corrente
    relogio(EM_2027)
    assert client.get(RELATORIO, headers=auth(EMAIL_AUDITOR)).json()["ano"] == 2027


def test_relatorio_so_para_auditor_e_admin(client, auth) -> None:
    for email in (EMAIL_DESMONTADORA, EMAIL_FABRICANTE):
        r = client.get(RELATORIO, headers=auth(email))
        assert (r.status_code, r.json()["codigo"]) == (403, "PAPEL_NAO_PERMITIDO")
    assert client.get(RELATORIO).status_code == 401
    assert client.get(RELATORIO, params={"ano": 1999}, headers=auth(EMAIL_AUDITOR)).status_code == 422
