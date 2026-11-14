"""Regressão dos dez testes adversariais da revisão independente (docs/revisao-independente.md, anexo A).

No relatório, cada teste passava quando o problema existia. Aqui cada um afirma o comportamento
corrigido, com o achado e o artigo de origem. Duas exceções documentadas:

- `a`: a correspondência nível → RM depende do texto dos itens 17 e 18 do Anexo III do Decreto
  12.435/2025, que ainda não está em `docs/` (lacuna L-01). O que dá para afirmar sem o decreto
  (o RM vem de `config_parametro`) é testado; a afirmação do decreto fica pendente (skip).
- `j`: reescrever a trilha recalculando os hashes só é detectável com ancoragem externa
  (lacuna L-14). O teste afirma a detecção e fica como `xfail` estrito até lá.
"""

import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.relogio import agora
from app.models import ChaveParametro, ConfigParametro, EventoAuditoria
from app.modules.auditoria.service import calcular_hash
from app.modules.portabilidade.service import hash_documento
from app.modules.urv.calculo import calcular_debito
from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FISCAL,
    OPERADOR,
    anexar,
    chassis,
    consumir,
    criar_mmv,
    dados_veiculo,
    dec,
    emitir_certificado,
    emitir_dmr,
    erro,
    gerar_credito,
    novo_chassi,
    ok,
    pdf_unico,
    processar_veiculo,
    receber_veiculo,
    saldo,
    transferir,
)

# A1, lacuna L-01: preencher com {1: RM, 2: RM} quando o texto dos itens 17 e 18 do Anexo III do
# Decreto 12.435/2025 for juntado a docs/ e transcrito em docs/01-requisitos.md.
RM_DO_DECRETO: dict[int, int] | None = None


def _fab_id(api) -> str:
    return ok(api.get("/auth/me", FISCAL))["empresa"]["id"]


def _divergencias(api) -> list[dict]:
    r = ok(api.get("/auditoria/reconciliar", AUDITOR))
    assert r["conciliado"] is (not r["divergencias"])
    return r["divergencias"]


# --- a. A1, RF-18, art. 3º §3º -----------------------------------------------------------------


def test_a_rm_vem_de_config_parametro(api, db_session) -> None:
    """O RM por nível é parâmetro com vigência, não constante no código."""
    mmv = criar_mmv(api, nivel=1)
    vigente = mmv["rm"]
    assert vigente in (5, 10)
    outro = 15 - vigente  # o outro valor admitido pelo art. 3º §3º
    db_session.add(
        ConfigParametro(chave=ChaveParametro.RM_NIVEL_1, valor=str(outro), vigente_desde=date.today())
    )
    db_session.flush()
    assert ok(api.get("/mmvs", FISCAL))["itens"][0]["rm"] in (5, 10)
    consumo = ok(consumir(api, FISCAL, mmv["id"], chassis(100)))
    assert consumo["rm"] == outro
    assert dec(consumo["urv_debito"]) == calcular_debito(100, outro, Decimal("150000"), Decimal("150000"))


@pytest.mark.skipif(
    RM_DO_DECRETO is None,
    reason="A1 pendente: o Decreto 12.435/2025 não está em docs/; o download do Planalto falhou (L-01)",
)
def test_a_rm_conforme_o_decreto(api) -> None:
    """O RM de cada nível é o que os itens 17 e 18 do Anexo III do Decreto 12.435/2025 dizem."""
    assert RM_DO_DECRETO is not None
    for nivel, rm in RM_DO_DECRETO.items():
        assert criar_mmv(api, nivel=nivel)["rm"] == rm


# --- b. A3, RF-18, art. 3º §§3º e 4º ------------------------------------------------------------


def test_b_fracionar_o_consumo_nao_reduz_o_debito(api) -> None:
    pm = "157400.00"
    lote = ok(consumir(api, FISCAL, criar_mmv(api, nivel=1)["id"], chassis(10), preco_medio=pm))
    mmv = criar_mmv(api, nivel=1)
    total = sum(
        (dec(ok(consumir(api, FISCAL, mmv["id"], [c], preco_medio=pm))["urv_debito"]) for c in chassis(10)),
        Decimal(0),
    )
    # Dez consumos de um chassi debitam o mesmo que um de dez: o Qv é o acumulado no período.
    assert total == dec(lote["urv_debito"]) == dec("1.05")
    # Mesmo MMV, mesmo período, Pm diferente: rejeitado.
    erro(
        consumir(api, FISCAL, mmv["id"], chassis(5), preco_medio="300000.00"), 422, "PM_DIVERGENTE_NO_PERIODO"
    )


# --- c. A2, RF-12, art. 18 §5º ------------------------------------------------------------------


def test_c_meta_sobre_o_peso_do_veiculo(api, client) -> None:
    client.app.dependency_overrides[agora] = lambda: datetime(2027, 1, 15, 15, 0, tzinfo=UTC)
    try:
        v = processar_veiculo(
            api, OPERADOR, peso_entrada_kg="1200.000", pesagens=[("FERROSO", "RECICLAGEM", "10.000")]
        )
        cert = ok(emitir_certificado(api, OPERADOR, v["id"]))
    finally:
        client.app.dependency_overrides.pop(agora, None)
    # 10 kg aproveitados de um veículo de 1.200 kg: 0,83 %, abaixo da meta de 80 % de 2027.
    assert dec(cert["percentual_aproveitado"]) == dec("0.83")
    assert dec(cert["meta_ano"]) == dec("80")
    assert cert["atende_meta"] is False
    # E as frações não pesam mais que o veículo.
    outro = receber_veiculo(api, peso_entrada_kg="100.000")
    corpo = {"fracao": "FERROSO", "destino": "RECICLAGEM", "peso_kg": "100.001"}
    erro(api.post(f"/veiculos/{outro['id']}/pesagens", OPERADOR, json=corpo), 422, "PESO_ACIMA_DA_ENTRADA")


# --- d. A7, RF-07, RF-21, RNF-07, art. 18 II; art. 21 III ---------------------------------------


def test_d_renavam_certidao_e_evidencia_nao_se_repetem_entre_chassis(api) -> None:
    primeiro = receber_veiculo(api, tipo="LICENCIADO_RODAGEM")
    erro(
        api.post("/veiculos", OPERADOR, json=dados_veiculo(renavam=primeiro["renavam"])),
        409,
        "RENAVAM_DUPLICADO",
    )
    erro(
        api.post(
            "/veiculos", OPERADOR, json=dados_veiculo(certidao_baixa_numero=primeiro["certidao_baixa_numero"])
        ),
        409,
        "CERTIDAO_BAIXA_DUPLICADA",
    )
    evidencia = pdf_unico()
    ok(anexar(api, OPERADOR, primeiro["id"], "EVIDENCIA_CLASSIFICACAO", "RECEPCAO", conteudo=evidencia))
    segundo = receber_veiculo(api, tipo="LICENCIADO_RODAGEM")
    r = anexar(api, OPERADOR, segundo["id"], "EVIDENCIA_CLASSIFICACAO", "RECEPCAO", conteudo=evidencia)
    erro(r, 409, "EVIDENCIA_REUTILIZADA")
    # Sem evidência própria, o segundo continua sucata inservível (RF-07, art. 2º §5º).
    assert ok(api.get(f"/veiculos/{segundo['id']}", OPERADOR))["tipo"] == "SUCATA_INSERVIVEL"


# --- e. A7, RF-06, RF-21, arts. 28 e 29 ---------------------------------------------------------


def test_e_chassi_do_veiculo_em_fim_de_vida_e_vin(api) -> None:
    base = novo_chassi()
    receber_veiculo(api, chassi=base)
    for invalido in (base + "0", "ABC123", "9BW" + "I" * 14, base[:16]):
        erro(api.post("/veiculos", OPERADOR, json=dados_veiculo(chassi=invalido)), 422)


# --- f. A4, RF-22, RNF-01, art. 20 V; art. 24 I -------------------------------------------------


def test_f_tabelas_de_negocio_protegidas_e_reconciliadas(api, db_session) -> None:
    _, cert = gerar_credito(api, OPERADOR)  # sucata inservível: 0,38
    cid = cert["credito"]["id"]
    for sql, alvo in (
        ("UPDATE urv_credito SET quantidade = 1.00 WHERE id = :i", cid),
        (
            "UPDATE certificado SET fator = 1.00, tipo_veiculo = 'LICENCIADO_RODAGEM' WHERE id = :i",
            cert["id"],
        ),
    ):
        with pytest.raises(DBAPIError), db_session.begin_nested():
            db_session.execute(text(sql), {"i": alvo})
    antes = saldo(api, FISCAL)
    ok(transferir(api, OPERADOR, cid, _fab_id(api)))
    assert saldo(api, FISCAL) - antes == dec("0.38")

    # O MMV continua editável no banco, mas a reconciliação acusa a diferença com a trilha.
    mmv = criar_mmv(api, nivel=2)
    db_session.execute(text("UPDATE mmv SET nivel = 1 WHERE id = :i"), {"i": mmv["id"]})
    db_session.flush()
    assert ok(api.get("/auditoria/verificar", AUDITOR))["integra"] is True
    acusadas = [d for d in _divergencias(api) if d["entidade_id"] == mmv["id"]]
    assert [(d["verificacao"], d["entidade"]) for d in acusadas] == [("TRILHA", "mmv")]


# --- g. A8, RF-23, art. 9º ----------------------------------------------------------------------


def test_g_fabricante_le_o_dossie_do_credito_que_detem(api, nova_empresa) -> None:
    v, cert = gerar_credito(api, OPERADOR)
    ok(emitir_dmr(api, OPERADOR, v["id"]))
    dossie = (
        f"/certificados/{cert['id']}",
        f"/veiculos/{v['id']}",
        f"/veiculos/{v['id']}/laudo",
        f"/veiculos/{v['id']}/dmrs",
    )
    for rota in dossie:  # antes da transferência o fabricante não é titular
        erro(api.get(rota, FISCAL), 404)
    ok(transferir(api, OPERADOR, cert["credito"]["id"], _fab_id(api)))

    for rota in dossie:
        ok(api.get(rota, FISCAL))
    anexos = ok(api.get(f"/veiculos/{v['id']}", FISCAL))["anexos"]
    assert anexos
    for a in anexos:
        assert api.get(f"/anexos/{a['id']}/arquivo", FISCAL).status_code == 200
    assert len(ok(api.get(f"/veiculos/{v['id']}/dmrs", FISCAL))["itens"]) == 1
    # Outro fabricante continua sem acesso, e o fabricante não escreve no fluxo.
    outro = nova_empresa("FABRICANTE")
    for rota in dossie:
        erro(api.get(rota, outro.email), 404)
    corpo = {"fracao": "FERROSO", "destino": "RECICLAGEM", "peso_kg": "1.000"}
    erro(api.post(f"/veiculos/{v['id']}/pesagens", FISCAL, json=corpo), 403)


# --- h. A5, RF-25, RNF-04, art. 8º I; art. 22 ---------------------------------------------------


def test_h_importacao_exige_hash_e_credenciamento_e_marca_o_importado(api, nova_empresa) -> None:
    g = nova_empresa("DESMONTADORA")
    gerar_credito(api, g.email, tipo="LICENCIADO_RODAGEM")
    arq = ok(api.get("/portabilidade/exportar", g.email))

    chassi = novo_chassi()
    numero = f"CRV-2026-{secrets.token_hex(5).upper()}"
    v = arq["veiculos"][0]
    v.update(
        chassi=chassi,
        renavam=f"9{secrets.randbelow(10**10):010d}",
        certidao_baixa_numero=f"CB-{uuid.uuid4().hex[:10]}",
        anexos=[],
        etapas=[],
        pesagens=[],
        pecas=[],
    )
    arq["certificados"][0].update(chassi=chassi, numero=numero)
    arq["creditos"][0].update(chassi=chassi, certificado_numero=numero)
    arq["lancamentos"] = []

    sem_hash = {**arq, "hash_conteudo": None}
    erro(api.post("/portabilidade/importar", ADMIN, json=sem_hash), 422, "HASH_AUSENTE")
    erro(
        api.post("/portabilidade/importar", ADMIN, json={**arq, "hash_conteudo": "0" * 64}),
        422,
        "HASH_INVALIDO",
    )

    arq["hash_conteudo"] = hash_documento(arq)
    ok(
        api.patch(
            f"/empresas/{g.id}/credenciamento", ADMIN, json={"status": "CANCELADO", "validade": "2028-11-14"}
        )
    )
    antes = saldo(api, g.email)
    erro(api.post("/portabilidade/importar", ADMIN, json=arq), 422, "CREDENCIAMENTO_INATIVO")
    assert saldo(api, g.email) == antes

    # Com credenciamento ativo e hash válido o item entra, marcado como importado. O hash é
    # recalculável por qualquer um: a confiança entre plataformas é a lacuna L-15.
    validade = (date.today() + timedelta(days=365)).isoformat()
    ok(api.patch(f"/empresas/{g.id}/credenciamento", ADMIN, json={"status": "ATIVO", "validade": validade}))
    r = ok(api.post("/portabilidade/importar", ADMIN, json=arq))
    assert {"tipo": "veiculo", "chave": chassi} in r["importados"], r
    importado = next(c for c in ok(api.get("/urv/creditos", g.email))["itens"] if c["chassi"] == chassi)
    assert importado["importado"] is True
    certificado = ok(api.get(f"/certificados/{importado['certificado_id']}", AUDITOR))
    assert certificado["importado"] is True and certificado["credito"]["importado"] is True


# --- i. A6, RF-18, art. 3º §5º ------------------------------------------------------------------


def test_i_importacao_de_consumo_rejeita_pb_divergente(api, nova_empresa) -> None:
    f = nova_empresa("FABRICANTE")
    mmv = criar_mmv(api, f.email, nivel=1)
    arq = ok(api.get("/portabilidade/exportar", f.email))
    pb = "1500000.00"  # dez vezes o Pb do art. 3º §5º
    arq["mmvs"] = []
    arq["consumos"] = [
        {
            "referencia": "X-1",
            "mmv_codigo": mmv["codigo"],
            "periodo": date.today().strftime("%Y-%m"),
            "qv": 100,
            "rm": mmv["rm"],
            "pm": "1500000.00",
            "pb": pb,
            "urv_debito": str(calcular_debito(100, mmv["rm"], Decimal("1500000.00"), Decimal(pb))),
            "saldo_apos": "-10.00",
            "prazo_reporte": (date.today() + timedelta(days=30)).isoformat(),
            "registrado_em": datetime.now(UTC).isoformat(),
            "chassis": chassis(100),
        }
    ]
    arq["hash_conteudo"] = hash_documento(arq)
    r = ok(api.post("/portabilidade/importar", ADMIN, json=arq))
    assert [(x["tipo"], x["motivo"]) for x in r["rejeitados"]] == [("consumo", "PB_DIVERGENTE")]
    assert saldo(api, f.email) == dec("0.00")


# --- j. A4, lacuna L-14, art. 20 V --------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="L-14: reescrever a cadeia recalculando os hashes exige ancoragem externa para ser detectado",
)
def test_j_reescrever_a_cadeia_recalculando_os_hashes(api, db_session) -> None:
    _, cert = gerar_credito(api, OPERADOR)
    db_session.execute(text("ALTER TABLE evento_auditoria DISABLE TRIGGER trg_evento_auditoria_imutavel"))
    db_session.execute(
        text(
            "UPDATE evento_auditoria SET payload = jsonb_set(payload, '{quantidade}', '\"1.00\"') "
            "WHERE tipo = 'CREDITO_GERADO' AND entidade_id = :i"
        ),
        {"i": cert["credito"]["id"]},
    )
    anterior = None
    for ev in db_session.scalars(select(EventoAuditoria).order_by(EventoAuditoria.sequencia)):
        if anterior is not None:
            ev.hash_anterior = anterior
        ev.hash = calcular_hash(
            ev.hash_anterior, ev.ocorrido_em, ev.usuario_id, ev.empresa_id,
            ev.tipo, ev.entidade, ev.entidade_id, ev.payload,
        )  # fmt: skip
        db_session.flush()
        anterior = ev.hash
    db_session.execute(text("ALTER TABLE evento_auditoria ENABLE TRIGGER trg_evento_auditoria_imutavel"))
    db_session.expire_all()
    # O que deveria acontecer: a adulteração ser detectada. Hoje a cadeia confere consigo mesma.
    assert ok(api.get("/auditoria/verificar", AUDITOR))["integra"] is False
