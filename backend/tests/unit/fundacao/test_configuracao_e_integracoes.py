"""Fatores, parâmetros, integrações falsas, utilitários e o esqueleto da aplicação."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.cnpj import cnpj_valido, formatar_cnpj, normalizar_cnpj
from app.core.configuracao import fator_vigente, fim_saldo_negativo, preco_base_vigente
from app.core.decimais import quantizar, quantizar_peso
from app.core.erros import ErroNegocio
from app.core.integracoes import (
    AssinadorDigitalFalso,
    ConsultaRenavamFalsa,
    EmissorMTRFalso,
    ValidadorNotaFiscalFalso,
)
from app.main import ROUTERS, criar_app
from app.models import ConfigFator, EventoAuditoria, TipoVeiculo, Usuario
from app.modules.urv.service import gerar_credito
from scripts.seed import EMAIL_DESMONTADORA, semear

# --- Configuração ------------------------------------------------------------------------------


def test_rota_fatores(client, auth) -> None:
    r = client.get("/api/v1/configuracao/fatores", headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["preco_base"] == "150000.00"  # Decimal trafega como string
    assert corpo["total"] == 6
    assert {i["tipo"]: i["fator"] for i in corpo["itens"]} == {
        "LICENCIADO_RODAGEM": "1.00",
        "SINISTRADO_PEQUENA_MEDIA": "0.94",
        "SUCATA_APROVEITAVEL": "0.85",
        "SINISTRADO_GRANDE": "0.79",
        "SUCATA_MOTOR_INSERVIVEL": "0.68",
        "SUCATA_INSERVIVEL": "0.38",
    }


def test_rota_fatores_exige_login(client) -> None:
    assert client.get("/api/v1/configuracao/fatores").status_code == 401


def test_fator_respeita_vigencia(db_session, dados_demo) -> None:
    hoje = date.today()
    assert fator_vigente(db_session, TipoVeiculo.SINISTRADO_GRANDE, hoje) == Decimal("0.79")
    # Revisão futura (art. 3º §6º): vale a partir da nova data, sem apagar a anterior.
    db_session.add(
        ConfigFator(
            tipo_veiculo=TipoVeiculo.SINISTRADO_GRANDE, fator=Decimal("0.80"), vigente_desde=date(2030, 1, 1)
        )
    )
    db_session.flush()
    assert fator_vigente(db_session, TipoVeiculo.SINISTRADO_GRANDE, date(2029, 12, 31)) == Decimal("0.79")
    assert fator_vigente(db_session, TipoVeiculo.SINISTRADO_GRANDE, date(2030, 1, 1)) == Decimal("0.80")
    with pytest.raises(ErroNegocio) as e:
        fator_vigente(db_session, TipoVeiculo.SINISTRADO_GRANDE, date(2020, 1, 1))
    assert e.value.codigo == "FATOR_NAO_CONFIGURADO"


def test_parametros(db_session, dados_demo) -> None:
    assert preco_base_vigente(db_session, date(2027, 6, 1)) == Decimal("150000.00")
    assert fim_saldo_negativo(db_session, date(2027, 6, 1)) == date(2027, 12, 31)


# --- Seed ---------------------------------------------------------------------------------------


def test_seed_idempotente(db_session) -> None:
    primeiro = semear(db_session)
    usuarios = db_session.scalar(select(func.count()).select_from(Usuario))
    eventos = db_session.scalar(select(func.count()).select_from(EventoAuditoria))
    segundo = semear(db_session)
    assert primeiro == segundo
    assert db_session.scalar(select(func.count()).select_from(Usuario)) == usuarios == 4
    assert db_session.scalar(select(func.count()).select_from(EventoAuditoria)) == eventos


# --- Integrações falsas -------------------------------------------------------------------------


def test_consulta_renavam_falsa() -> None:
    c = ConsultaRenavamFalsa()
    ok = c.consultar("12345678901", "9BWZZZ377VT004251")
    assert ok.encontrado and ok.baixado and ok.licenciamento_regular
    assert not c.consultar("00012345678", "X").encontrado
    assert not c.consultar("123", "X").encontrado
    atrasado = c.consultar("12345678909", "X")
    assert atrasado.encontrado and not atrasado.licenciamento_regular


def test_validador_nota_fiscal_falso() -> None:
    v = ValidadorNotaFiscalFalso()
    assert v.validar("NF-123", "12345678000195").valida
    assert not v.validar("INVALIDA-1", "12345678000195").valida
    assert not v.validar("", "12345678000195").valida
    assert not v.validar("NF-123", "12345678000100").valida


def test_emissor_mtr_falso() -> None:
    e = EmissorMTRFalso()
    a = e.emitir(gerador_cnpj="1", destinatario_cnpj="2", tipo_material="FERROSO", peso_kg=Decimal("10.000"))
    b = e.emitir(gerador_cnpj="1", destinatario_cnpj="2", tipo_material="FERROSO", peso_kg=Decimal("10.000"))
    assert a.numero.startswith("MTR-SIM-")
    assert a.numero != b.numero


def test_assinador_falso_detecta_alteracao() -> None:
    s = AssinadorDigitalFalso()
    assinatura = s.assinar(b"laudo do chassi X", "Eng. Fulana - CREA 123")
    assert s.verificar(b"laudo do chassi X", assinatura)
    assert not s.verificar(b"laudo do chassi Y", assinatura)


# --- Utilitários --------------------------------------------------------------------------------


def test_quantizar_round_half_up() -> None:
    # Anexo I, item 5: 0,935 → 0,94 e 0,785 → 0,79 (ROUND_HALF_EVEN daria 0,94 e 0,78).
    assert quantizar(Decimal("0.935")) == Decimal("0.94")
    assert quantizar(Decimal("0.785")) == Decimal("0.79")
    assert quantizar(Decimal("0.125")) == Decimal("0.13")
    assert quantizar_peso("1.2345") == Decimal("1.235")
    with pytest.raises(TypeError):
        quantizar(0.1)  # type: ignore[arg-type]


def test_cnpj() -> None:
    assert cnpj_valido("12.345.678/0001-95")
    assert not cnpj_valido("12.345.678/0001-96")
    assert not cnpj_valido("11111111111111")
    assert normalizar_cnpj("12.345.678/0001-95") == "12345678000195"
    assert formatar_cnpj("12345678000195") == "12.345.678/0001-95"


# --- Esqueleto ----------------------------------------------------------------------------------


def test_todos_os_modulos_tem_router_registrado() -> None:
    modulos = {r.tags[0] for r in ROUTERS}
    assert modulos == {
        "auth",
        "empresas",
        "auditoria",
        "configuracao",
        "veiculos",
        "pecas",
        "residuos",
        "documentos",
        "mmv",
        "urv",
        "relatorios",
        "portabilidade",
    }


def test_openapi_e_docs(client) -> None:
    assert client.get("/docs").status_code == 200
    esquema = client.get("/openapi.json").json()
    assert "/api/v1/auth/login" in esquema["paths"]
    assert client.get("/saude").json() == {"status": "ok"}
    assert criar_app().title == "URV Rastreabilidade"


def test_gerar_credito_e_stub(db_session) -> None:
    with pytest.raises(NotImplementedError):
        gerar_credito(db_session, None)  # type: ignore[arg-type]
