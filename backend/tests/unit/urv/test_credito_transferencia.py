"""Geração e transferência de crédito, saldo e extrato. RF-16, RF-17, RF-19 e RF-21."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.erros import ErroNegocio
from app.models import (
    Empresa,
    EventoAuditoria,
    LancamentoTipo,
    TipoEmpresa,
    TipoVeiculo,
    UrvCredito,
    UrvCreditoStatus,
    UrvLancamento,
)
from app.modules.auditoria.service import verificar_cadeia
from app.modules.urv.service import gerar_credito, saldo_empresa, transferir_credito
from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA, EMAIL_FABRICANTE
from tests.unit.urv.apoio import (
    CNPJ_IMPORTADORA,
    CNPJ_RECICLA,
    HOJE,
    creditar,
    criar_certificado,
    criar_empresa_com_usuario,
)

URV = "/api/v1/urv"
CHASSI = "9BWZZZ377VT004251"


def _lancamentos(db_session, **filtros) -> list[UrvLancamento]:
    return list(db_session.scalars(select(UrvLancamento).filter_by(**filtros)))


def _transferir(client, auth, credito_id, fabricante_id, email=EMAIL_DESMONTADORA):
    return client.post(
        f"{URV}/creditos/{credito_id}/transferir",
        json={"fabricante_id": str(fabricante_id)},
        headers=auth(email),
    )


# --- gerar_credito (RF-16) ---------------------------------------------------------------------


def test_gerar_credito_cria_credito_lancamento_e_evento(db_session, dados_demo) -> None:
    certificado = criar_certificado(
        db_session,
        dados_demo.desmonte_id,
        CHASSI,
        tipo=TipoVeiculo.SINISTRADO_PEQUENA_MEDIA,
        fator=Decimal("0.94"),
    )
    credito = gerar_credito(db_session, certificado)

    assert credito.quantidade == Decimal("0.94")  # igual ao fator do certificado
    assert credito.certificado_id == certificado.id
    assert credito.geradora_id == credito.titular_id == dados_demo.desmonte_id
    assert credito.status == UrvCreditoStatus.DISPONIVEL

    (lanc,) = _lancamentos(db_session, credito_id=credito.id)
    assert lanc.tipo == LancamentoTipo.CREDITO
    assert lanc.quantidade == Decimal("0.94")
    assert lanc.empresa_id == dados_demo.desmonte_id
    assert lanc.criado_em == HOJE  # a data da emissão do certificado
    assert saldo_empresa(db_session, dados_demo.desmonte_id) == Decimal("0.94")

    evento = db_session.scalar(
        select(EventoAuditoria).where(
            EventoAuditoria.tipo == "CREDITO_GERADO", EventoAuditoria.entidade_id == credito.id
        )
    )
    assert evento.empresa_id == dados_demo.desmonte_id
    assert evento.payload["quantidade"] == "0.94"
    assert evento.payload["certificado_numero"] == certificado.numero
    assert verificar_cadeia(db_session).integra


def test_gerar_credito_registra_o_autor_quando_informado(db_session, dados_demo, operador) -> None:
    credito = gerar_credito(
        db_session, criar_certificado(db_session, dados_demo.desmonte_id, CHASSI), usuario=operador
    )
    evento = db_session.scalar(select(EventoAuditoria).where(EventoAuditoria.entidade_id == credito.id))
    assert evento.usuario_id == operador.id


def test_gerar_credito_rejeita_certificado_que_ja_tem_credito(db_session, dados_demo) -> None:
    certificado = criar_certificado(db_session, dados_demo.desmonte_id, CHASSI)
    gerar_credito(db_session, certificado)
    with pytest.raises(ErroNegocio) as erro:
        gerar_credito(db_session, certificado)  # RF-21
    assert erro.value.status_code == 409
    assert erro.value.codigo == "CERTIFICADO_JA_CREDITADO"
    assert db_session.scalar(select(func.count()).select_from(UrvCredito)) == 1
    assert len(_lancamentos(db_session)) == 1
    assert saldo_empresa(db_session, dados_demo.desmonte_id) == Decimal("1.00")


def test_saldo_e_a_soma_dos_lancamentos(db_session, dados_demo) -> None:
    assert saldo_empresa(db_session, dados_demo.desmonte_id) == Decimal("0.00")
    creditar(db_session, dados_demo.desmonte_id, "CHASSI-A")
    creditar(
        db_session,
        dados_demo.desmonte_id,
        "CHASSI-B",
        tipo=TipoVeiculo.SUCATA_INSERVIVEL,
        fator=Decimal("0.38"),
    )
    saldo = saldo_empresa(db_session, dados_demo.desmonte_id)
    assert saldo == Decimal("1.38")
    assert str(saldo) == "1.38"


# --- Transferência (RF-17) ---------------------------------------------------------------------


def test_transferencia_direta_ao_fabricante_com_vinculo(
    client, auth, relogio, db_session, dados_demo
) -> None:
    credito = creditar(db_session, dados_demo.desmonte_id, CHASSI, fator=Decimal("0.94"))

    r = _transferir(client, auth, credito.id, dados_demo.montadora_id)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["status"] == "TRANSFERIDO"
    assert corpo["quantidade"] == "0.94"
    assert corpo["chassi"] == CHASSI
    assert corpo["geradora"]["razao_social"] == "Desmonte Paraná S.A."
    assert corpo["titular"]["razao_social"] == "Montadora Exemplo S.A."  # art. 8º II: titularidade

    db_session.refresh(credito)
    assert credito.status == UrvCreditoStatus.TRANSFERIDO
    assert credito.titular_id == dados_demo.montadora_id
    assert credito.geradora_id == dados_demo.desmonte_id

    lancs = {lanc.tipo: lanc for lanc in _lancamentos(db_session, credito_id=credito.id)}
    assert set(lancs) == {"CREDITO", "TRANSFERENCIA_SAIDA", "TRANSFERENCIA_ENTRADA"}
    saida, entrada = lancs["TRANSFERENCIA_SAIDA"], lancs["TRANSFERENCIA_ENTRADA"]
    assert (saida.empresa_id, saida.quantidade, saida.contraparte_id) == (
        dados_demo.desmonte_id,
        Decimal("-0.94"),
        dados_demo.montadora_id,
    )
    assert (entrada.empresa_id, entrada.quantidade, entrada.contraparte_id) == (
        dados_demo.montadora_id,
        Decimal("0.94"),
        dados_demo.desmonte_id,
    )
    assert saida.criado_em == entrada.criado_em == HOJE

    assert saldo_empresa(db_session, dados_demo.desmonte_id) == Decimal("0.00")
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("0.94")

    evento = db_session.scalar(select(EventoAuditoria).where(EventoAuditoria.tipo == "CREDITO_TRANSFERIDO"))
    assert evento.entidade_id == credito.id
    assert evento.usuario_id == dados_demo.operador_id
    assert evento.payload["fabricante_id"] == str(dados_demo.montadora_id)
    assert verificar_cadeia(db_session).integra


def test_credito_transferido_nao_e_transferido_de_novo(client, auth, relogio, db_session, dados_demo) -> None:
    credito = creditar(db_session, dados_demo.desmonte_id, CHASSI)
    assert _transferir(client, auth, credito.id, dados_demo.montadora_id).status_code == 200

    r = _transferir(client, auth, credito.id, dados_demo.montadora_id)
    assert r.status_code == 409
    assert r.json()["codigo"] == "CREDITO_JA_TRANSFERIDO"
    assert len(_lancamentos(db_session, credito_id=credito.id)) == 3
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("1.00")


def test_transferencia_exige_vinculo_ativo(client, auth, relogio, db_session, dados_demo) -> None:
    credito = creditar(db_session, dados_demo.desmonte_id, CHASSI)
    outro = criar_empresa_com_usuario(
        db_session,
        cnpj=CNPJ_IMPORTADORA,
        razao_social="Importadora Z",
        tipo=TipoEmpresa.FABRICANTE,
        email="fiscal@importadora.local",
    )
    # Fabricante sem vínculo, empresa que não existe e empresa que não é fabricante.
    for alvo in (outro.empresa_id, "00000000-0000-0000-0000-000000000000", dados_demo.desmonte_id):
        r = _transferir(client, auth, credito.id, alvo)
        assert r.status_code == 422, r.text
        assert r.json()["codigo"] == "SEM_VINCULO"

    # Vínculo desativado pelo admin.
    client.patch(
        f"/api/v1/vinculos/{dados_demo.vinculo_id}", json={"ativo": False}, headers=auth(EMAIL_ADMIN)
    )
    r = _transferir(client, auth, credito.id, dados_demo.montadora_id)
    assert r.status_code == 422
    assert r.json()["codigo"] == "SEM_VINCULO"

    db_session.refresh(credito)
    assert credito.status == UrvCreditoStatus.DISPONIVEL
    assert len(_lancamentos(db_session, credito_id=credito.id)) == 1


def test_fabricante_precisa_de_registro_de_compromissos(
    client, auth, relogio, db_session, dados_demo
) -> None:
    credito = creditar(db_session, dados_demo.desmonte_id, CHASSI)
    db_session.get(Empresa, dados_demo.montadora_id).registro_compromissos = False
    db_session.flush()
    r = _transferir(client, auth, credito.id, dados_demo.montadora_id)
    assert r.status_code == 422
    assert r.json()["codigo"] == "FABRICANTE_SEM_REGISTRO_COMPROMISSOS"  # art. 8º II


def test_so_a_geradora_transfere_o_proprio_credito(client, auth, relogio, db_session, dados_demo) -> None:
    credito = creditar(db_session, dados_demo.desmonte_id, CHASSI)
    criar_empresa_com_usuario(
        db_session,
        cnpj=CNPJ_RECICLA,
        razao_social="Recicla Sul S.A.",
        tipo=TipoEmpresa.RECICLADORA,
        email="operador@recicla.local",
    )
    # Outra geradora não enxerga o crédito.
    r = _transferir(client, auth, credito.id, dados_demo.montadora_id, email="operador@recicla.local")
    assert r.status_code == 404
    # Crédito inexistente.
    r = _transferir(client, auth, "00000000-0000-0000-0000-000000000000", dados_demo.montadora_id)
    assert r.status_code == 404
    # Art. 8º §3º, intermediação vedada: fabricante, admin e auditor não transferem.
    for email, codigo in (
        (EMAIL_FABRICANTE, "PAPEL_NAO_PERMITIDO"),
        (EMAIL_ADMIN, "PAPEL_NAO_PERMITIDO"),
        (EMAIL_AUDITOR, "AUDITOR_SOMENTE_LEITURA"),
    ):
        r = _transferir(client, auth, credito.id, dados_demo.montadora_id, email=email)
        assert (r.status_code, r.json()["codigo"]) == (403, codigo)


def test_fabricante_nao_repassa_credito_recebido(db_session, dados_demo, operador, fiscal) -> None:
    """Mesmo chamando o service direto, quem recebeu não transfere: não é a geradora."""
    credito = creditar(db_session, dados_demo.desmonte_id, CHASSI)
    transferir_credito(db_session, operador, credito.id, dados_demo.montadora_id)
    with pytest.raises(ErroNegocio) as erro:
        transferir_credito(db_session, fiscal, credito.id, dados_demo.montadora_id)
    assert erro.value.status_code == 404


# --- Consultas ---------------------------------------------------------------------------------


def test_saldo_por_papel(client, auth, relogio, db_session, dados_demo) -> None:
    credito = creditar(db_session, dados_demo.desmonte_id, CHASSI, fator=Decimal("0.94"))
    creditar(db_session, dados_demo.desmonte_id, "9BWZZZ377VT004252", fator=Decimal("0.38"))
    _transferir(client, auth, credito.id, dados_demo.montadora_id)

    r = client.get(f"{URV}/saldo", headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 200
    assert r.json() == {"empresa_id": str(dados_demo.desmonte_id), "saldo": "0.38", "regularizar_ate": None}
    assert client.get(f"{URV}/saldo", headers=auth(EMAIL_FABRICANTE)).json()["saldo"] == "0.94"

    # AUDITOR e ADMIN informam a empresa (RF-23).
    for email in (EMAIL_AUDITOR, EMAIL_ADMIN):
        r = client.get(f"{URV}/saldo", headers=auth(email))
        assert (r.status_code, r.json()["codigo"]) == (422, "EMPRESA_OBRIGATORIA")
        r = client.get(
            f"{URV}/saldo", params={"empresa_id": str(dados_demo.montadora_id)}, headers=auth(email)
        )
        assert r.json()["saldo"] == "0.94"
    r = client.get(
        f"{URV}/saldo",
        params={"empresa_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth(EMAIL_AUDITOR),
    )
    assert r.status_code == 404

    # Empresa não consulta o saldo de outra.
    r = client.get(
        f"{URV}/saldo", params={"empresa_id": str(dados_demo.montadora_id)}, headers=auth(EMAIL_DESMONTADORA)
    )
    assert r.status_code == 404
    assert client.get(f"{URV}/saldo").status_code == 401


def test_extrato_por_papel(client, auth, relogio, db_session, dados_demo) -> None:
    credito = creditar(db_session, dados_demo.desmonte_id, CHASSI)
    _transferir(client, auth, credito.id, dados_demo.montadora_id)

    r = client.get(f"{URV}/extrato", headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 200
    itens = r.json()["itens"]
    assert r.json()["total"] == 2
    assert {(i["tipo"], i["quantidade"]) for i in itens} == {
        ("CREDITO", "1.00"),
        ("TRANSFERENCIA_SAIDA", "-1.00"),
    }
    saida = next(i for i in itens if i["tipo"] == "TRANSFERENCIA_SAIDA")
    assert saida["contraparte"]["razao_social"] == "Montadora Exemplo S.A."
    assert saida["credito_id"] == str(credito.id)

    r = client.get(f"{URV}/extrato", headers=auth(EMAIL_FABRICANTE))
    assert [(i["tipo"], i["quantidade"]) for i in r.json()["itens"]] == [("TRANSFERENCIA_ENTRADA", "1.00")]

    r = client.get(f"{URV}/extrato", params={"tipo": "CREDITO"}, headers=auth(EMAIL_DESMONTADORA))
    assert r.json()["total"] == 1

    # AUDITOR lê tudo, ou uma empresa com ?empresa_id=.
    assert client.get(f"{URV}/extrato", headers=auth(EMAIL_AUDITOR)).json()["total"] == 3
    r = client.get(
        f"{URV}/extrato", params={"empresa_id": str(dados_demo.montadora_id)}, headers=auth(EMAIL_AUDITOR)
    )
    assert r.json()["total"] == 1
    r = client.get(
        f"{URV}/extrato", params={"empresa_id": str(dados_demo.desmonte_id)}, headers=auth(EMAIL_FABRICANTE)
    )
    assert r.status_code == 404


def test_creditos_por_papel_e_status(client, auth, relogio, db_session, dados_demo) -> None:
    transferido = creditar(db_session, dados_demo.desmonte_id, CHASSI, fator=Decimal("0.94"))
    disponivel = creditar(db_session, dados_demo.desmonte_id, "9BWZZZ377VT004252")
    _transferir(client, auth, transferido.id, dados_demo.montadora_id)

    r = client.get(f"{URV}/creditos", headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 200
    assert r.json()["total"] == 2  # a geradora vê os que gerou, transferidos ou não
    item = next(i for i in r.json()["itens"] if i["id"] == str(transferido.id))
    assert item["chassi"] == CHASSI
    assert item["certificado"]["numero"] == f"CRV-{CHASSI}"
    assert item["certificado"]["fator"] == "0.94"

    r = client.get(f"{URV}/creditos", params={"status": "DISPONIVEL"}, headers=auth(EMAIL_DESMONTADORA))
    assert [i["id"] for i in r.json()["itens"]] == [str(disponivel.id)]

    r = client.get(f"{URV}/creditos", headers=auth(EMAIL_FABRICANTE))  # o fabricante vê os que recebeu
    assert [i["id"] for i in r.json()["itens"]] == [str(transferido.id)]

    assert client.get(f"{URV}/creditos", headers=auth(EMAIL_AUDITOR)).json()["total"] == 2
    r = client.get(f"{URV}/creditos", params={"status": "INVALIDO"}, headers=auth(EMAIL_AUDITOR))
    assert r.status_code == 422
