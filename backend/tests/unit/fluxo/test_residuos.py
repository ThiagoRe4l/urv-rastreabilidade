"""Pesagens, percentual aproveitado, meta do ano e DMR. RF-11 a RF-13."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.integracoes import Mtr, obter_emissor_mtr
from app.models import DestinoPesagem
from app.modules.residuos.service import atende_meta, meta_do_ano, percentual_aproveitado
from scripts.seed import CNPJ_DESMONTE
from tests.unit.fluxo.apoio import CNPJ_DESTINATARIO, VEICULOS, criar_veiculo, eventos, pesagem


def _pesagens(*itens: tuple[str, str]) -> list:
    return [SimpleNamespace(destino=DestinoPesagem(d), peso_kg=Decimal(p)) for d, p in itens]


def _dmr(**mudancas) -> dict:
    return {
        "numero": "DMR-0001",
        "destinatario_nome": "Recicla Metais Ltda.",
        "destinatario_cnpj": "11.444.777/0001-61",
        "tipo_material": "Sucata ferrosa",
        "peso_kg": "700.000",
        **mudancas,
    }


# --- Percentual aproveitado e meta (RF-12) ------------------------------------------------------


@pytest.mark.parametrize(
    ("itens", "esperado"),
    [
        ((), None),
        ((("RECICLAGEM", "700"), ("REJEITO", "300")), Decimal("70.00")),
        ((("REJEITO", "10"),), Decimal("0.00")),
        (
            (("REAPROVEITAMENTO", "1"), ("RECICLAGEM", "1"), ("RECUPERACAO_ENERGETICA", "1")),
            Decimal("100.00"),
        ),
        # 2/3 = 66,666... → 66,67; 1/3 = 33,333... → 33,33
        ((("RECICLAGEM", "2"), ("REJEITO", "1")), Decimal("66.67")),
        ((("RECICLAGEM", "1"), ("REJEITO", "2")), Decimal("33.33")),
        # 1/8 = 12,5% exato; 1/16 = 6,25%; 79,995 arredonda para cima (ROUND_HALF_UP)
        ((("RECICLAGEM", "0.125"), ("REJEITO", "0.875")), Decimal("12.50")),
        ((("RECICLAGEM", "79.995"), ("REJEITO", "20.005")), Decimal("80.00")),
        ((("RECICLAGEM", "79.994"), ("REJEITO", "20.006")), Decimal("79.99")),
    ],
)
def test_percentual_aproveitado(itens, esperado) -> None:
    resultado = percentual_aproveitado(_pesagens(*itens))
    assert resultado == esperado
    if esperado is not None:
        assert resultado.as_tuple().exponent == -2  # sempre duas casas


@pytest.mark.parametrize(
    ("ano", "meta"),
    [
        (2026, None),
        (2027, "80.00"),
        (2028, "80.00"),
        (2029, "85.00"),
        (2030, "85.00"),
        (2031, "90.00"),
        (2032, "90.00"),
        (2033, "95.00"),
        (2040, "95.00"),
    ],
)
def test_meta_do_ano(ano, meta) -> None:
    assert meta_do_ano(ano) == (Decimal(meta) if meta else None)


def test_atende_meta() -> None:
    assert atende_meta(Decimal("80.00"), Decimal("80.00")) is True
    assert atende_meta(Decimal("79.99"), Decimal("80.00")) is False
    assert atende_meta(Decimal("79.99"), None) is None  # 2026: só registro
    assert atende_meta(None, Decimal("80.00")) is None


# --- Pesagens (RF-11) ---------------------------------------------------------------------------


def test_pesagens_por_fracao_e_resumo(client, h, db_session) -> None:
    v = criar_veiculo(client, h)
    url = f"{VEICULOS}/{v['id']}/pesagens"
    assert client.get(url, headers=h).json() == {
        "itens": [],
        "total": 0,
        "peso_total_kg": "0.000",
        "percentual_aproveitado": None,
        "meta_ano": str(meta) if (meta := meta_do_ano(date.today().year)) else None,
        "atende_meta": None,
    }

    r = pesagem(client, h, v["id"], "FERROSO", "RECICLAGEM", "612.5")
    assert r.status_code == 201, r.text
    assert r.json()["peso_kg"] == "612.500"
    pesagem(client, h, v["id"], "FLUIDOS", "RECUPERACAO_ENERGETICA", 37.5)  # número também é aceito
    pesagem(client, h, v["id"], "NAO_METALICO", "REJEITO", "350")

    resumo = client.get(url, headers=h).json()
    assert resumo["total"] == 3
    # Sem ordem: no teste tudo roda numa transação só, e `criado_em` (now()) sai igual.
    assert {p["fracao"] for p in resumo["itens"]} == {"FERROSO", "FLUIDOS", "NAO_METALICO"}
    assert resumo["peso_total_kg"] == "1000.000"
    assert resumo["percentual_aproveitado"] == "65.00"
    assert client.get(f"{VEICULOS}/{v['id']}", headers=h).json()["percentual_aproveitado"] == "65.00"
    assert eventos(db_session, "PESAGEM_REGISTRADA", r.json()["id"])[0].payload["peso_kg"] == "612.500"


@pytest.mark.parametrize("peso", ["0", "-1", "1.2345", "abc"])
def test_pesagem_invalida(client, h, peso) -> None:
    v = criar_veiculo(client, h)
    assert pesagem(client, h, v["id"], peso_kg=peso).status_code == 422
    assert pesagem(client, h, v["id"], fracao="MADEIRA").status_code == 422


# --- DMR (RF-13) --------------------------------------------------------------------------------


def test_dmr_recebe_mtr_do_emissor(client, h, db_session) -> None:
    pedidos: list[dict] = []

    class EmissorDeTeste:
        def emitir(self, **dados) -> Mtr:
            pedidos.append(dados)
            return Mtr(numero="MTR-TESTE-42", emitido_em=datetime(2026, 11, 12, 15, 0, tzinfo=UTC))

    client.app.dependency_overrides[obter_emissor_mtr] = lambda: EmissorDeTeste()
    v = criar_veiculo(client, h)
    r = client.post(f"{VEICULOS}/{v['id']}/dmrs", json=_dmr(), headers=h)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["mtr_numero"] == "MTR-TESTE-42"
    assert d["destinatario_cnpj"] == CNPJ_DESTINATARIO  # gravado só com dígitos
    assert d["emitida_em"].startswith("2026-11-12T15:00:00")
    assert pedidos == [
        {
            "gerador_cnpj": CNPJ_DESMONTE,
            "destinatario_cnpj": CNPJ_DESTINATARIO,
            "tipo_material": "Sucata ferrosa",
            "peso_kg": Decimal("700.000"),
        }
    ]
    assert eventos(db_session, "DMR_EMITIDA", d["id"])[0].payload["mtr_numero"] == "MTR-TESTE-42"

    lista = client.get(f"{VEICULOS}/{v['id']}/dmrs", headers=h).json()
    assert lista["total"] == 1
    assert lista["itens"][0]["id"] == d["id"]


def test_dmr_com_emissor_simulado_padrao(client, h) -> None:
    v = criar_veiculo(client, h)
    r = client.post(f"{VEICULOS}/{v['id']}/dmrs", json=_dmr(), headers=h)
    assert r.json()["mtr_numero"].startswith("MTR-SIM-")


def test_dmr_duplicada_e_invalida(client, h) -> None:
    v = criar_veiculo(client, h)
    url = f"{VEICULOS}/{v['id']}/dmrs"
    assert client.post(url, json=_dmr(), headers=h).status_code == 201
    r = client.post(url, json=_dmr(tipo_material="Alumínio"), headers=h)
    assert r.status_code == 409
    assert r.json()["codigo"] == "DMR_DUPLICADA"

    assert (
        client.post(url, json=_dmr(numero="DMR-2", destinatario_cnpj="11444777000160"), headers=h).status_code
        == 422
    )
    assert client.post(url, json=_dmr(numero="DMR-2", peso_kg="0"), headers=h).status_code == 422
    assert client.get(url, headers=h).json()["total"] == 1
