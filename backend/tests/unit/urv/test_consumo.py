"""Consumo de URV: débito, saldo, prazos e unicidade de chassi. RF-18 a RF-21."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.erros import ErroNegocio
from app.models import (
    ChaveParametro,
    ConfigParametro,
    Consumo,
    ConsumoChassi,
    EventoAuditoria,
    LancamentoTipo,
    MmvStatus,
    TipoEmpresa,
    UrvLancamento,
)
from app.modules.auditoria.service import verificar_cadeia
from app.modules.urv.schemas import ConsumoCriar
from app.modules.urv.service import registrar_consumo, saldo_empresa, transferir_credito
from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA, EMAIL_FABRICANTE
from tests.unit.urv.apoio import (
    CNPJ_IMPORTADORA,
    HOJE,
    creditar,
    criar_empresa_com_usuario,
    criar_mmv,
    vin,
    vins,
)

URV = "/api/v1/urv"

EM_2027 = datetime(2027, 6, 15, 15, 0, tzinfo=UTC)
EM_2028 = datetime(2028, 2, 10, 15, 0, tzinfo=UTC)


def _dar_saldo(db_session, dados_demo, operador, quantidade: int, prefixo: str = "FIMDEVIDA") -> None:
    """Gera `quantidade` créditos de 1.00 na desmontadora e transfere todos ao fabricante do seed."""
    for n in range(quantidade):
        credito = creditar(db_session, dados_demo.desmonte_id, f"{prefixo}{n:04d}")
        transferir_credito(db_session, operador, credito.id, dados_demo.montadora_id, agora=HOJE)


def _consumir(client, auth, mmv, chassis, *, periodo="2026-11", preco="150000.00", email=EMAIL_FABRICANTE):
    corpo = {"mmv_id": str(mmv.id), "periodo": periodo, "preco_medio": preco, "chassis": chassis}
    return client.post(f"{URV}/consumos", json=corpo, headers=auth(email))


def _total(db_session, modelo) -> int:
    return db_session.scalar(select(func.count()).select_from(modelo))


# --- Simulação ---------------------------------------------------------------------------------


def test_simulacao_devolve_debito_saldo_e_memoria_de_calculo(
    client, auth, relogio, db_session, dados_demo, operador, mmv
) -> None:
    _dar_saldo(db_session, dados_demo, operador, 2)
    r = client.post(
        f"{URV}/consumos/simular",
        json={"mmv_id": str(mmv.id), "quantidade": 1000, "preco_medio": "180000.00"},
        headers=auth(EMAIL_FABRICANTE),
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "urv_debito": "120.00",
        "saldo_atual": "2.00",
        "saldo_apos": "-118.00",
        "saldo_suficiente": False,
        "permitido": True,  # até 31/12/2027 o saldo negativo é aceito
        "regularizar_ate": "2027-02-28",
        "prazo_saldo_negativo": "2027-12-31",
        "memoria_calculo": {
            "formula": "urv_debito = (qv / rm) * max(1, pm / pb)",
            "qv": 1000,
            "nivel": 1,
            "rm": 10,
            "pm": "180000.00",
            "pb": "150000.00",
            "razao_preco": "1.2000",
            "multiplicador": "1.2000",
        },
    }
    # Simular não grava nada.
    assert _total(db_session, Consumo) == 0
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("2.00")


def test_simulacao_com_preco_abaixo_do_base_e_nivel_2(client, auth, relogio, db_session, dados_demo) -> None:
    nivel_2 = criar_mmv(db_session, dados_demo.montadora_id, codigo="SUV-2.0", nivel=2)
    r = client.post(
        f"{URV}/consumos/simular",
        json={"mmv_id": str(nivel_2.id), "quantidade": 1000, "preco_medio": 90000},
        headers=auth(EMAIL_FABRICANTE),
    )
    corpo = r.json()
    assert corpo["urv_debito"] == "200.00"  # 1000 / 5, multiplicador 1
    assert corpo["memoria_calculo"]["rm"] == 5
    assert corpo["memoria_calculo"]["razao_preco"] == "0.6000"
    assert corpo["memoria_calculo"]["multiplicador"] == "1.0000"


def test_simulacao_em_2028_avisa_que_o_registro_seria_rejeitado(client, auth, relogio, mmv) -> None:
    relogio(EM_2028)
    r = client.post(
        f"{URV}/consumos/simular",
        json={"mmv_id": str(mmv.id), "quantidade": 7, "preco_medio": "150000"},
        headers=auth(EMAIL_FABRICANTE),
    )
    corpo = r.json()
    assert (corpo["urv_debito"], corpo["saldo_suficiente"], corpo["permitido"]) == ("0.70", False, False)
    assert corpo["regularizar_ate"] is None


# --- Registro (RF-18) --------------------------------------------------------------------------


def test_consumo_com_saldo_baixa_o_livro(
    client, auth, relogio, db_session, dados_demo, operador, mmv
) -> None:
    _dar_saldo(db_session, dados_demo, operador, 2)
    chassis = vins(7)

    r = _consumir(client, auth, mmv, chassis, preco="180000.00")
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["qv"] == 7
    assert c["rm"] == 10
    assert c["pm"] == "180000.00"
    assert c["pb"] == "150000.00"  # de config_parametro, vigente na data
    assert c["urv_debito"] == "0.84"  # (7 / 10) * 1.2
    assert c["saldo_apos"] == "1.16"
    assert c["regularizar_ate"] is None  # havia saldo
    assert c["prazo_reporte"] == "2026-12-14"  # RF-20: décimo dia útil de dezembro
    assert c["fora_do_prazo"] is False
    assert c["chassis"] == chassis
    assert c["mmv_codigo"] == mmv.codigo

    consumo = db_session.scalar(select(Consumo))
    assert consumo.registrado_em == HOJE
    (debito,) = db_session.scalars(select(UrvLancamento).where(UrvLancamento.tipo == LancamentoTipo.DEBITO))
    assert (debito.empresa_id, debito.quantidade, debito.consumo_id) == (
        dados_demo.montadora_id,
        Decimal("-0.84"),
        consumo.id,
    )
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("1.16")
    assert client.get(f"{URV}/saldo", headers=auth(EMAIL_FABRICANTE)).json() == {
        "empresa_id": str(dados_demo.montadora_id),
        "saldo": "1.16",
        "regularizar_ate": None,
    }

    evento = db_session.scalar(select(EventoAuditoria).where(EventoAuditoria.tipo == "URV_CONSUMIDA"))
    assert evento.entidade_id == consumo.id
    assert evento.payload["urv_debito"] == "0.84"
    assert evento.payload["saldo_antes"] == "2.00"
    assert evento.payload["chassis"] == chassis
    assert verificar_cadeia(db_session).integra


def test_chassis_sao_normalizados(client, auth, relogio, mmv) -> None:
    r = _consumir(client, auth, mmv, [" 9bw00000000000001 ", "9BW-00000000000002"])
    assert r.status_code == 201, r.text
    assert r.json()["chassis"] == [vin(1), vin(2)]


# --- Saldo (RF-19, art. 8º III e §1º) ----------------------------------------------------------


def test_consumo_sem_saldo_e_aceito_em_2027_com_prazo_de_regularizacao(
    client, auth, relogio, db_session, dados_demo, mmv
) -> None:
    relogio(EM_2027)
    r = _consumir(client, auth, mmv, vins(7), periodo="2027-05")
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["urv_debito"] == "0.70"
    assert c["saldo_apos"] == "-0.70"
    assert c["regularizar_ate"] == "2027-09-30"  # último dia do terceiro mês seguinte a junho
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("-0.70")
    assert client.get(f"{URV}/saldo", headers=auth(EMAIL_FABRICANTE)).json() == {
        "empresa_id": str(dados_demo.montadora_id),
        "saldo": "-0.70",
        "regularizar_ate": "2027-09-30",
    }


def test_consumo_sem_saldo_e_rejeitado_em_2028(client, auth, relogio, db_session, dados_demo, mmv) -> None:
    relogio(EM_2028)
    r = _consumir(client, auth, mmv, vins(7), periodo="2028-01")
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == "SALDO_INSUFICIENTE"
    # Nada foi gravado: nem consumo, nem chassi, nem lançamento.
    assert _total(db_session, Consumo) == 0
    assert _total(db_session, ConsumoChassi) == 0
    assert _total(db_session, UrvLancamento) == 0
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("0.00")


def test_mesmo_consumo_muda_de_resultado_na_virada_de_2027_para_2028(db_session, fiscal, mmv) -> None:
    """A mesma chamada ao service, só com a data trocada. O limite é meia-noite de Brasília."""

    def dados(inicio: int) -> ConsumoCriar:
        return ConsumoCriar(
            mmv_id=mmv.id, periodo="2027-12", preco_medio=Decimal("150000"), chassis=vins(7, inicio)
        )

    ultimo_minuto = datetime(2028, 1, 1, 2, 59, tzinfo=UTC)  # 23h59 de 31/12/2027 em Brasília
    aceito = registrar_consumo(db_session, fiscal, dados(1), agora=ultimo_minuto)
    assert aceito.saldo_apos == Decimal("-0.70")
    assert aceito.regularizar_ate == date(2028, 3, 31)

    primeiro_minuto = datetime(2028, 1, 1, 3, 0, tzinfo=UTC)  # 0h de 1º/1/2028 em Brasília
    with pytest.raises(ErroNegocio) as erro:
        registrar_consumo(db_session, fiscal, dados(100), agora=primeiro_minuto)
    assert (erro.value.status_code, erro.value.codigo) == (409, "SALDO_INSUFICIENTE")


def test_em_2028_consumo_com_saldo_e_aceito_e_o_excedente_nao(
    client, auth, relogio, db_session, dados_demo, operador, mmv
) -> None:
    _dar_saldo(db_session, dados_demo, operador, 1)
    relogio(EM_2028)

    r = _consumir(client, auth, mmv, vins(7), periodo="2028-01")  # 0.70 de 1.00
    assert r.status_code == 201, r.text
    assert (r.json()["saldo_apos"], r.json()["regularizar_ate"]) == ("0.30", None)

    r = _consumir(client, auth, mmv, vins(4, inicio=100), periodo="2028-01")  # 0.40 de 0.30
    assert (r.status_code, r.json()["codigo"]) == (409, "SALDO_INSUFICIENTE")

    r = _consumir(client, auth, mmv, vins(3, inicio=200), periodo="2028-01")  # 0.30 de 0.30: zera
    assert r.status_code == 201, r.text
    assert r.json()["saldo_apos"] == "0.00"
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("0.00")


def test_data_limite_do_saldo_negativo_vem_de_config_parametro(
    client, auth, relogio, db_session, dados_demo, mmv
) -> None:
    db_session.add(
        ConfigParametro(
            chave=ChaveParametro.FIM_SALDO_NEGATIVO, valor="2028-06-30", vigente_desde=date(2028, 1, 1)
        )
    )
    db_session.flush()
    relogio(EM_2028)
    r = _consumir(client, auth, mmv, vins(7), periodo="2028-01")
    assert r.status_code == 201, r.text
    assert r.json()["regularizar_ate"] == "2028-05-31"

    relogio(datetime(2028, 7, 1, 15, 0, tzinfo=UTC))
    r = _consumir(client, auth, mmv, vins(7, inicio=100), periodo="2028-06")
    assert (r.status_code, r.json()["codigo"]) == (409, "SALDO_INSUFICIENTE")


def test_preco_base_vem_de_config_parametro(client, auth, relogio, db_session, mmv) -> None:
    db_session.add(
        ConfigParametro(chave=ChaveParametro.PRECO_BASE, valor="200000.00", vigente_desde=date(2027, 1, 1))
    )
    db_session.flush()
    relogio(EM_2027)
    r = _consumir(client, auth, mmv, vins(10), periodo="2027-05", preco="300000.00")
    assert (r.json()["pb"], r.json()["urv_debito"]) == ("200000.00", "1.50")


def test_prazo_de_regularizacao_e_o_do_consumo_que_abriu_o_saldo_devedor(
    client, auth, relogio, db_session, dados_demo, operador, mmv
) -> None:
    def saldo() -> dict:
        return client.get(f"{URV}/saldo", headers=auth(EMAIL_FABRICANTE)).json()

    relogio(datetime(2027, 3, 10, 15, 0, tzinfo=UTC))
    assert _consumir(client, auth, mmv, vins(5), periodo="2027-02").json()["regularizar_ate"] == "2027-06-30"
    relogio(datetime(2027, 4, 10, 15, 0, tzinfo=UTC))
    assert _consumir(client, auth, mmv, vins(5, 100), periodo="2027-03").json()["regularizar_ate"] == (
        "2027-07-31"
    )
    # O saldo está negativo desde março: vale o prazo mais antigo.
    assert (saldo()["saldo"], saldo()["regularizar_ate"]) == ("-1.00", "2027-06-30")

    _dar_saldo(db_session, dados_demo, operador, 2)  # regulariza e sobra 1.00
    assert (saldo()["saldo"], saldo()["regularizar_ate"]) == ("1.00", None)

    relogio(datetime(2027, 8, 10, 15, 0, tzinfo=UTC))
    r = _consumir(client, auth, mmv, vins(15, 200), periodo="2027-07")  # 1.50 de 1.00
    assert (r.json()["saldo_apos"], r.json()["regularizar_ate"]) == ("-0.50", "2027-11-30")
    assert (saldo()["saldo"], saldo()["regularizar_ate"]) == ("-0.50", "2027-11-30")  # novo saldo devedor


# --- Unicidade de chassi (RF-21) ---------------------------------------------------------------


def test_chassi_de_veiculo_novo_consome_uma_unica_vez(
    client, auth, relogio, db_session, dados_demo, mmv
) -> None:
    assert _consumir(client, auth, mmv, vins(3)).status_code == 201

    r = _consumir(client, auth, mmv, [vin(50), vin(2), vin(51)])
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == "CHASSI_JA_CONSUMIDO"
    assert vin(2) in r.json()["detail"]
    assert _total(db_session, Consumo) == 1
    assert _total(db_session, ConsumoChassi) == 3  # os chassis novos do pedido rejeitado não entraram

    # Vale entre fabricantes: o chassi é único na plataforma.
    outro = criar_empresa_com_usuario(
        db_session,
        cnpj=CNPJ_IMPORTADORA,
        razao_social="Importadora Z",
        tipo=TipoEmpresa.FABRICANTE,
        email="fiscal@importadora.local",
    )
    mmv_outro = criar_mmv(db_session, outro.empresa_id)
    r = _consumir(client, auth, mmv_outro, [vin(1)], email="fiscal@importadora.local")
    assert (r.status_code, r.json()["codigo"]) == (409, "CHASSI_JA_CONSUMIDO")


def test_chassi_repetido_na_mesma_lista(client, auth, relogio, db_session, mmv) -> None:
    r = _consumir(client, auth, mmv, [vin(1), vin(2), vin(1)])
    assert (r.status_code, r.json()["codigo"]) == (422, "CHASSI_REPETIDO_NA_LISTA")
    assert _total(db_session, Consumo) == 0


@pytest.mark.parametrize(
    "corpo",
    [
        {"chassis": []},
        {"chassis": ["CURTO"]},
        {"chassis": ["9BWIOQ00000000001"]},  # I, O e Q não existem em VIN
        {"periodo": "2026-13"},
        {"periodo": "11/2026"},
        {"preco_medio": "0"},
        {"preco_medio": "-1"},
        {"preco_medio": "150000.001"},
    ],
)
def test_entrada_invalida(client, auth, relogio, mmv, corpo) -> None:
    dados = {"mmv_id": str(mmv.id), "periodo": "2026-11", "preco_medio": "150000", "chassis": [vin(1)]}
    r = client.post(f"{URV}/consumos", json={**dados, **corpo}, headers=auth(EMAIL_FABRICANTE))
    assert (r.status_code, r.json()["codigo"]) == (422, "ENTRADA_INVALIDA"), r.text


# --- MMV (RF-04) -------------------------------------------------------------------------------


def test_mmv_ainda_sem_efeitos(client, auth, relogio, db_session, dados_demo) -> None:
    comercializado = criar_mmv(
        db_session, dados_demo.montadora_id, codigo="SEDAN", ja_comercializado=True, efeitos=date(2027, 1, 1)
    )
    r = _consumir(client, auth, comercializado, vins(2))
    assert (r.status_code, r.json()["codigo"]) == (422, "MMV_SEM_EFEITOS")
    assert "2027-01-01" in r.json()["detail"]

    relogio(datetime(2027, 1, 4, 15, 0, tzinfo=UTC))
    assert _consumir(client, auth, comercializado, vins(2), periodo="2027-01").status_code == 201


def test_mmv_retirado_nao_consome(client, auth, relogio, db_session, mmv) -> None:
    mmv.status = MmvStatus.RETIRADO
    db_session.flush()
    r = _consumir(client, auth, mmv, vins(2))
    assert (r.status_code, r.json()["codigo"]) == (422, "MMV_SEM_EFEITOS")


def test_mmv_de_outro_fabricante_ou_inexistente(client, auth, relogio, db_session, dados_demo, mmv) -> None:
    criar_empresa_com_usuario(
        db_session,
        cnpj=CNPJ_IMPORTADORA,
        razao_social="Importadora Z",
        tipo=TipoEmpresa.FABRICANTE,
        email="fiscal@importadora.local",
    )
    r = _consumir(client, auth, mmv, vins(2), email="fiscal@importadora.local")
    assert r.status_code == 404
    r = client.post(
        f"{URV}/consumos/simular",
        json={"mmv_id": "00000000-0000-0000-0000-000000000000", "quantidade": 1, "preco_medio": "1"},
        headers=auth(EMAIL_FABRICANTE),
    )
    assert r.status_code == 404


# --- Prazo de reporte (RF-20) ------------------------------------------------------------------


def test_registro_depois_do_decimo_dia_util_e_aceito_e_marcado(client, auth, relogio, mmv) -> None:
    # HOJE é 13/11/2026, o décimo dia útil de novembro: ainda no prazo para outubro.
    no_prazo = _consumir(client, auth, mmv, vins(2), periodo="2026-10").json()
    assert (no_prazo["prazo_reporte"], no_prazo["fora_do_prazo"]) == ("2026-11-13", False)

    relogio(datetime(2026, 11, 14, 15, 0, tzinfo=UTC))
    atrasado = _consumir(client, auth, mmv, vins(2, 100), periodo="2026-10")
    assert atrasado.status_code == 201  # aceito, só marcado
    assert atrasado.json()["fora_do_prazo"] is True

    r = client.get(f"{URV}/consumos", headers=auth(EMAIL_FABRICANTE))
    assert [c["fora_do_prazo"] for c in r.json()["itens"]] == [True, False]  # mais recente primeiro


# --- Consultas e papéis ------------------------------------------------------------------------


def test_listagem_de_consumos_por_papel(client, auth, relogio, db_session, dados_demo, mmv) -> None:
    outro = criar_empresa_com_usuario(
        db_session,
        cnpj=CNPJ_IMPORTADORA,
        razao_social="Importadora Z",
        tipo=TipoEmpresa.FABRICANTE,
        email="fiscal@importadora.local",
    )
    mmv_outro = criar_mmv(db_session, outro.empresa_id, codigo="OUTRO")
    _consumir(client, auth, mmv, vins(2))
    _consumir(client, auth, mmv_outro, vins(3, 100), email="fiscal@importadora.local")

    r = client.get(f"{URV}/consumos", headers=auth(EMAIL_FABRICANTE))
    assert r.status_code == 200
    assert [(c["qv"], c["mmv_codigo"]) for c in r.json()["itens"]] == [(2, mmv.codigo)]

    for email in (EMAIL_AUDITOR, EMAIL_ADMIN):
        assert client.get(f"{URV}/consumos", headers=auth(email)).json()["total"] == 2
        r = client.get(f"{URV}/consumos", params={"empresa_id": str(outro.empresa_id)}, headers=auth(email))
        assert [c["qv"] for c in r.json()["itens"]] == [3]

    assert client.get(f"{URV}/consumos", headers=auth(EMAIL_DESMONTADORA)).status_code == 403


def test_busca_de_consumo_pelo_chassi(client, auth, relogio, db_session, dados_demo, mmv) -> None:
    """PM-WEB-06, RF-23: o auditor acha o consumo em que um chassi novo foi usado."""
    outro = criar_empresa_com_usuario(
        db_session,
        cnpj=CNPJ_IMPORTADORA,
        razao_social="Importadora Z",
        tipo=TipoEmpresa.FABRICANTE,
        email="fiscal@importadora.local",
    )
    mmv_outro = criar_mmv(db_session, outro.empresa_id, codigo="OUTRO")
    _consumir(client, auth, mmv, vins(2))
    _consumir(client, auth, mmv_outro, vins(3, 100), email="fiscal@importadora.local")

    def buscar(chassi: str, email: str = EMAIL_AUDITOR) -> list:
        r = client.get(f"{URV}/consumos", params={"chassi": chassi}, headers=auth(email))
        assert r.status_code == 200, r.text
        assert r.json()["total"] == len(r.json()["itens"])
        return r.json()["itens"]

    achados = buscar(vin(101))
    assert [c["qv"] for c in achados] == [3]
    assert vin(101) in achados[0]["chassis"] and len(achados[0]["chassis"]) == 3
    assert [c["qv"] for c in buscar(f" {vin(1).lower()} ")] == [2]  # normalizado como no registro
    assert buscar(vin(999)) == []
    assert buscar(vin(1)[:10]) == []  # busca exata, não por trecho
    # O fabricante continua vendo só os próprios consumos, mesmo buscando o chassi de outro.
    assert buscar(vin(101), EMAIL_FABRICANTE) == []


@pytest.mark.parametrize(
    ("email", "codigo"),
    [
        (EMAIL_DESMONTADORA, "PAPEL_NAO_PERMITIDO"),
        (EMAIL_ADMIN, "PAPEL_NAO_PERMITIDO"),
        (EMAIL_AUDITOR, "AUDITOR_SOMENTE_LEITURA"),
    ],
)
def test_so_fabricante_consome_e_simula(client, auth, relogio, mmv, email, codigo) -> None:
    r = _consumir(client, auth, mmv, vins(2), email=email)
    assert (r.status_code, r.json()["codigo"]) == (403, codigo)
    r = client.post(
        f"{URV}/consumos/simular",
        json={"mmv_id": str(mmv.id), "quantidade": 1, "preco_medio": "1"},
        headers=auth(email),
    )
    assert (r.status_code, r.json()["codigo"]) == (403, codigo)
