"""Exportação e importação para portabilidade. RF-25, RNF-04, RNF-05, arts. 22, 28 e 29."""

import copy
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import (
    Anexo,
    AnexoTipo,
    Certificado,
    Consumo,
    ConsumoChassi,
    DestinoPesagem,
    Dmr,
    Etapa,
    EtapaTipo,
    EventoAuditoria,
    Fracao,
    LancamentoTipo,
    Laudo,
    Mmv,
    Peca,
    PecaClassificacao,
    Pesagem,
    TipoVeiculo,
    UrvCredito,
    UrvCreditoStatus,
    UrvLancamento,
    Veiculo,
)
from app.modules.auditoria.service import verificar_cadeia
from app.modules.portabilidade.service import hash_documento
from app.modules.urv.schemas import ConsumoCriar
from app.modules.urv.service import registrar_consumo, saldo_empresa, transferir_credito
from scripts.seed import (
    CNPJ_DESMONTE,
    CNPJ_MONTADORA,
    EMAIL_ADMIN,
    EMAIL_AUDITOR,
    EMAIL_DESMONTADORA,
    EMAIL_FABRICANTE,
)
from tests.unit.urv.apoio import HOJE, creditar, vins

EXPORTAR = "/api/v1/portabilidade/exportar"
IMPORTAR = "/api/v1/portabilidade/importar"

CHASSI_A = "9BWZZZ377VT004251"
CHASSI_B = "9BWZZZ377VT004252"


def _total(db_session, modelo) -> int:
    return db_session.scalar(select(func.count()).select_from(modelo))


def _importar(client, auth, documento: dict, email: str = EMAIL_ADMIN):
    return client.post(IMPORTAR, json=documento, headers=auth(email))


def _com_hash(documento: dict) -> dict:
    documento["hash_conteudo"] = hash_documento(documento)
    return documento


def _rejeicoes(resposta) -> dict[str, str]:
    return {r["chave"]: r["motivo"] for r in resposta.json()["rejeitados"]}


@pytest.fixture
def dossie(db_session, dados_demo, operador):
    """Na desmontadora: veículo A completo com crédito transferido e veículo B com crédito disponível."""
    credito_a = creditar(
        db_session,
        dados_demo.desmonte_id,
        CHASSI_A,
        tipo=TipoVeiculo.SINISTRADO_GRANDE,
        fator=Decimal("0.79"),
    )
    veiculo_id = credito_a.certificado.veiculo_id
    db_session.add_all(
        [
            Etapa(veiculo_id=veiculo_id, tipo=EtapaTipo.RECEPCAO, iniciada_em=HOJE, concluida_em=HOJE),
            Etapa(
                veiculo_id=veiculo_id, tipo=EtapaTipo.DESTRUICAO, iniciada_em=HOJE, observacoes="Triturado"
            ),
            Anexo(
                veiculo_id=veiculo_id,
                etapa_tipo=EtapaTipo.RECEPCAO,
                tipo=AnexoTipo.FOTO,
                caminho="/data/uploads/foto.jpg",
                sha256="f" * 64,
                nome_original="foto.jpg",
                content_type="image/jpeg",
                tamanho_bytes=1234,
                enviado_por=operador.id,
            ),
            Peca(
                veiculo_id=veiculo_id,
                nome="Porta dianteira",
                classificacao=PecaClassificacao.REUTILIZAVEL,
                codigo_rastreio="RASTREIO-0001",
            ),
            Pesagem(
                veiculo_id=veiculo_id,
                fracao=Fracao.FERROSO,
                destino=DestinoPesagem.RECICLAGEM,
                peso_kg=Decimal("812.500"),
            ),
            Dmr(
                veiculo_id=veiculo_id,
                numero="DMR-1",
                mtr_numero="MTR-SIM-1",
                destinatario_nome="Siderúrgica Açolar",
                destinatario_cnpj="11222333000181",
                tipo_material="Sucata ferrosa",
                peso_kg=Decimal("812.500"),
                emitida_em=HOJE,
            ),
            Laudo(
                veiculo_id=veiculo_id,
                responsavel_nome="Eng. Responsável",
                responsavel_registro="CREA-PR 1",
                assinado_em=HOJE,
                hash_conteudo="b" * 64,
                assinatura="assinatura-simulada",
            ),
        ]
    )
    db_session.flush()
    transferir_credito(db_session, operador, credito_a.id, dados_demo.montadora_id, agora=HOJE)
    credito_b = creditar(db_session, dados_demo.desmonte_id, CHASSI_B)
    db_session.add(
        Laudo(
            veiculo_id=credito_b.certificado.veiculo_id,
            responsavel_nome="Eng. Responsável",
            responsavel_registro="CREA-PR 1",
            assinado_em=HOJE,
            hash_conteudo="c" * 64,
        )
    )
    db_session.flush()
    return credito_a


@pytest.fixture
def consumo(db_session, dossie, fiscal, mmv) -> Consumo:
    dados = ConsumoCriar(mmv_id=mmv.id, periodo="2026-10", preco_medio=Decimal("150000"), chassis=vins(5))
    return registrar_consumo(db_session, fiscal, dados, agora=HOJE)


def _exportar(client, auth, email: str = EMAIL_DESMONTADORA) -> dict:
    r = client.get(EXPORTAR, headers=auth(email))
    assert r.status_code == 200, r.text
    return r.json()


def _trocar(chassi: str, marca: str = "X") -> str:
    """Outro chassi, derivado do original (troca o primeiro caractere)."""
    return marca + chassi[1:]


def _outra_plataforma(documento: dict, sufixo: str = "X") -> dict:
    """O mesmo histórico como se viesse de outra plataforma: chassis, números e códigos diferentes."""
    doc = copy.deepcopy(documento)
    doc["origem"] = {"plataforma": "Outra Plataforma", "versao": "9"}

    def trocar(chassi: str) -> str:
        return _trocar(chassi, sufixo)

    for v in doc["veiculos"]:
        v["chassi"] = trocar(v["chassi"])
        for p in v["pecas"]:
            if p["codigo_rastreio"]:
                p["codigo_rastreio"] += sufixo
    for c in doc["certificados"]:
        c["chassi"], c["numero"] = trocar(c["chassi"]), c["numero"] + sufixo
    for c in doc["creditos"]:
        c["chassi"], c["certificado_numero"] = trocar(c["chassi"]), c["certificado_numero"] + sufixo
    for lanc in doc["lancamentos"]:
        if lanc["certificado_numero"]:
            lanc["certificado_numero"] += sufixo
    return _com_hash(doc)


# --- Exportação --------------------------------------------------------------------------------


def test_exportacao_da_geradora(client, auth, relogio, db_session, dados_demo, dossie) -> None:
    r = client.get(EXPORTAR, headers=auth(EMAIL_DESMONTADORA))
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"] == (
        f'attachment; filename="urv-portabilidade-{CNPJ_DESMONTE}-2026-11-13.json"'
    )
    doc = r.json()
    assert doc["versao_formato"] == "1.0"
    assert doc["origem"]["plataforma"] == "URV Rastreabilidade"
    assert doc["empresa"]["cnpj"] == CNPJ_DESMONTE
    assert doc["empresa"]["credenciamento_status"] == "ATIVO"
    assert {"veiculos", "certificados", "creditos", "lancamentos"} <= set(doc)
    assert doc["hash_conteudo"] == hash_documento(doc)

    # Cadastro de usuários (art. 22 I), sem credenciais.
    assert doc["usuarios"] == [
        {"nome": "Operador da Desmontagem", "email": EMAIL_DESMONTADORA, "papel": "DESMONTADORA"}
    ]
    assert "senha" not in r.text
    assert doc["vinculos"] == [
        {"geradora_cnpj": CNPJ_DESMONTE, "fabricante_cnpj": CNPJ_MONTADORA, "ativo": True}
    ]

    veiculos = {v["chassi"]: v for v in doc["veiculos"]}
    assert set(veiculos) == {CHASSI_A, CHASSI_B}
    a = veiculos[CHASSI_A]
    assert sorted(e["tipo"] for e in a["etapas"]) == ["DESTRUICAO", "RECEPCAO"]
    assert a["anexos"][0]["sha256"] == "f" * 64  # só metadados; o arquivo não trafega
    assert "caminho" not in a["anexos"][0]
    assert a["pecas"][0]["codigo_rastreio"] == "RASTREIO-0001"
    assert a["pesagens"][0]["peso_kg"] == "812.500"
    assert a["dmrs"][0]["destinatario_nome"] == "Siderúrgica Açolar"
    assert a["laudo"]["hash_conteudo"] == "b" * 64
    assert veiculos[CHASSI_B]["laudo"]["hash_conteudo"] == "c" * 64
    assert veiculos[CHASSI_B]["etapas"] == veiculos[CHASSI_B]["pecas"] == []

    certificados = {c["chassi"]: c for c in doc["certificados"]}
    assert certificados[CHASSI_A]["fator"] == "0.79"
    assert certificados[CHASSI_A]["emitente_cnpj"] == CNPJ_DESMONTE

    creditos = {c["chassi"]: c for c in doc["creditos"]}
    assert creditos[CHASSI_A]["status"] == "TRANSFERIDO"
    assert creditos[CHASSI_A]["titular_cnpj"] == CNPJ_MONTADORA
    assert creditos[CHASSI_A]["transferido_em"] is not None
    assert creditos[CHASSI_B]["status"] == "DISPONIVEL"
    assert creditos[CHASSI_B]["titular_cnpj"] == CNPJ_DESMONTE
    assert creditos[CHASSI_B]["transferido_em"] is None

    assert sorted((lanc["tipo"], lanc["quantidade"]) for lanc in doc["lancamentos"]) == [
        ("CREDITO", "0.79"),
        ("CREDITO", "1.00"),
        ("TRANSFERENCIA_SAIDA", "-0.79"),
    ]
    saida = next(lanc for lanc in doc["lancamentos"] if lanc["tipo"] == "TRANSFERENCIA_SAIDA")
    assert saida["contraparte_cnpj"] == CNPJ_MONTADORA
    assert saida["certificado_numero"] == f"CRV-{CHASSI_A}"
    assert doc["saldo"] == "1.00"
    assert doc["saldo"] == str(saldo_empresa(db_session, dados_demo.desmonte_id))
    assert doc["mmvs"] == doc["consumos"] == []


def test_exportacao_do_fabricante(client, auth, relogio, mmv, consumo) -> None:
    doc = _exportar(client, auth, EMAIL_FABRICANTE)
    assert doc["empresa"]["cnpj"] == CNPJ_MONTADORA
    assert doc["veiculos"] == []  # o dossiê do veículo é da geradora
    assert [(c["chassi"], c["status"], c["geradora_cnpj"]) for c in doc["creditos"]] == [
        (CHASSI_A, "TRANSFERIDO", CNPJ_DESMONTE)
    ]
    assert [c["numero"] for c in doc["certificados"]] == [f"CRV-{CHASSI_A}"]  # origem do crédito recebido
    assert [m["codigo"] for m in doc["mmvs"]] == [mmv.codigo]
    (c,) = doc["consumos"]
    assert c["referencia"] == str(consumo.id)
    assert (c["mmv_codigo"], c["qv"], c["urv_debito"], c["saldo_apos"]) == (mmv.codigo, 5, "0.50", "0.29")
    assert c["chassis"] == vins(5)
    assert sorted((lanc["tipo"], lanc["quantidade"]) for lanc in doc["lancamentos"]) == [
        ("DEBITO", "-0.50"),
        ("TRANSFERENCIA_ENTRADA", "0.79"),
    ]
    debito = next(lanc for lanc in doc["lancamentos"] if lanc["tipo"] == "DEBITO")
    assert debito["consumo_referencia"] == str(consumo.id)
    assert doc["saldo"] == "0.29"
    assert doc["hash_conteudo"] == hash_documento(doc)


def test_exportacao_por_papel(client, auth, relogio, dados_demo, dossie) -> None:
    for email in (EMAIL_AUDITOR, EMAIL_ADMIN):
        r = client.get(EXPORTAR, headers=auth(email))
        assert (r.status_code, r.json()["codigo"]) == (422, "EMPRESA_OBRIGATORIA")
        r = client.get(EXPORTAR, params={"empresa_id": str(dados_demo.desmonte_id)}, headers=auth(email))
        assert r.json()["empresa"]["cnpj"] == CNPJ_DESMONTE
    r = client.get(
        EXPORTAR, params={"empresa_id": "00000000-0000-0000-0000-000000000000"}, headers=auth(EMAIL_ADMIN)
    )
    assert r.status_code == 404
    # RNF-05: a empresa exporta o próprio histórico, e só o próprio.
    r = client.get(
        EXPORTAR, params={"empresa_id": str(dados_demo.desmonte_id)}, headers=auth(EMAIL_FABRICANTE)
    )
    assert r.status_code == 404
    assert client.get(EXPORTAR).status_code == 401


# --- Importação: validação do arquivo ----------------------------------------------------------


def test_reimportar_o_proprio_arquivo_rejeita_chassi_ja_creditado(
    client, auth, relogio, db_session, dados_demo, dossie
) -> None:
    doc = _exportar(client, auth)
    antes = {m: _total(db_session, m) for m in (Veiculo, Certificado, UrvCredito, UrvLancamento)}

    r = _importar(client, auth, doc)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["importados"] == []
    assert corpo["total_rejeitados"] == 2
    assert {(i["tipo"], i["chave"], i["motivo"]) for i in corpo["rejeitados"]} == {
        ("veiculo", CHASSI_A, "CHASSI_JA_CREDITADO"),
        ("veiculo", CHASSI_B, "CHASSI_JA_CREDITADO"),
    }
    assert all(i["detalhe"] for i in corpo["rejeitados"])
    assert corpo["saldo_confere"] is True  # nada mudou: o saldo local segue igual ao do arquivo
    assert {m: _total(db_session, m) for m in antes} == antes  # RF-21: nada duplicado


def test_arquivo_recusado_inteiro(client, auth, relogio, db_session, dossie) -> None:
    doc = _exportar(client, auth)

    adulterado = copy.deepcopy(doc)
    adulterado["saldo"] = "999.00"
    r = _importar(client, auth, adulterado)
    assert (r.status_code, r.json()["codigo"]) == (422, "HASH_INVALIDO")

    versao_nova = _com_hash({**copy.deepcopy(doc), "versao_formato": "2.0"})
    r = _importar(client, auth, versao_nova)
    assert (r.status_code, r.json()["codigo"]) == (422, "VERSAO_FORMATO_NAO_SUPORTADA")

    desconhecida = copy.deepcopy(doc)
    desconhecida["empresa"]["cnpj"] = "11444777000161"
    r = _importar(client, auth, _com_hash(desconhecida))
    assert (r.status_code, r.json()["codigo"]) == (422, "EMPRESA_NAO_CADASTRADA")

    outro_tipo = copy.deepcopy(doc)
    outro_tipo["empresa"]["tipo"] = "RECICLADORA"
    r = _importar(client, auth, _com_hash(outro_tipo))
    assert (r.status_code, r.json()["codigo"]) == (422, "EMPRESA_TIPO_DIVERGENTE")

    malformado = copy.deepcopy(doc)
    malformado["veiculos"][0]["tipo"] = "CARRO_VELHO"
    del malformado["empresa"]["razao_social"]
    r = _importar(client, auth, malformado)
    assert (r.status_code, r.json()["codigo"]) == (422, "ENTRADA_INVALIDA")

    assert db_session.scalar(select(EventoAuditoria).where(EventoAuditoria.tipo.like("%IMPORTAD%"))) is None


def test_arquivo_sem_hash_e_aceito(client, auth, relogio, dossie) -> None:
    doc = _exportar(client, auth)
    doc.pop("hash_conteudo")  # outras plataformas podem não enviar
    assert _importar(client, auth, doc).status_code == 200


@pytest.mark.parametrize(
    ("email", "codigo"),
    [
        (EMAIL_DESMONTADORA, "PAPEL_NAO_PERMITIDO"),
        (EMAIL_FABRICANTE, "PAPEL_NAO_PERMITIDO"),
        (EMAIL_AUDITOR, "AUDITOR_SOMENTE_LEITURA"),
    ],
)
def test_so_admin_importa(client, auth, relogio, dossie, email, codigo) -> None:
    doc = _exportar(client, auth)
    r = _importar(client, auth, doc, email=email)
    assert (r.status_code, r.json()["codigo"]) == (403, codigo)


# --- Importação: geradora ----------------------------------------------------------------------


def test_importa_dossie_de_outra_plataforma(client, auth, relogio, db_session, dados_demo, dossie) -> None:
    doc = _outra_plataforma(_exportar(client, auth))
    chassi_a, chassi_b = _trocar(CHASSI_A), _trocar(CHASSI_B)

    r = _importar(client, auth, doc)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["rejeitados"] == []
    assert corpo["importados"] == [
        {"tipo": "veiculo", "chave": chassi_a},
        {"tipo": "veiculo", "chave": chassi_b},
    ]
    assert corpo["empresa_id"] == str(dados_demo.desmonte_id)

    veiculo = db_session.scalar(select(Veiculo).where(Veiculo.chassi == chassi_a))
    assert veiculo.empresa_id == dados_demo.desmonte_id
    etapas = db_session.scalars(select(Etapa).where(Etapa.veiculo_id == veiculo.id)).all()
    assert sorted(e.tipo for e in etapas) == ["DESTRUICAO", "RECEPCAO"]
    assert next(e.observacoes for e in etapas if e.tipo == "DESTRUICAO") == "Triturado"
    assert db_session.scalar(select(Peca.codigo_rastreio).where(Peca.veiculo_id == veiculo.id)) == (
        "RASTREIO-0001X"
    )
    assert db_session.scalar(select(Pesagem.peso_kg).where(Pesagem.veiculo_id == veiculo.id)) == Decimal(
        "812.500"
    )
    assert db_session.scalar(select(Dmr.numero).where(Dmr.veiculo_id == veiculo.id)) == "DMR-1"
    assert db_session.scalar(select(Laudo.assinatura).where(Laudo.veiculo_id == veiculo.id)) == (
        "assinatura-simulada"
    )
    # Os arquivos de evidência não trafegam: o anexo fica registrado só no evento.
    assert (
        db_session.scalar(select(func.count()).select_from(Anexo).where(Anexo.veiculo_id == veiculo.id)) == 0
    )

    certificado = db_session.scalar(select(Certificado).where(Certificado.veiculo_id == veiculo.id))
    assert (certificado.numero, certificado.fator) == (f"CRV-{CHASSI_A}X", Decimal("0.79"))
    assert certificado.emitido_em == HOJE
    credito = db_session.scalar(select(UrvCredito).where(UrvCredito.certificado_id == certificado.id))
    assert credito.status == UrvCreditoStatus.TRANSFERIDO
    assert (credito.geradora_id, credito.titular_id) == (dados_demo.desmonte_id, dados_demo.montadora_id)
    lancs = db_session.scalars(select(UrvLancamento).where(UrvLancamento.credito_id == credito.id)).all()
    # Só o lado da geradora: a entrada do fabricante vem do arquivo dele (art. 28).
    assert sorted((lanc.tipo, lanc.quantidade, lanc.empresa_id) for lanc in lancs) == [
        (LancamentoTipo.CREDITO, Decimal("0.79"), dados_demo.desmonte_id),
        (LancamentoTipo.TRANSFERENCIA_SAIDA, Decimal("-0.79"), dados_demo.desmonte_id),
    ]

    # O saldo local é o que já havia (1.00) mais o importado (1.00); o do arquivo era 1.00.
    assert (corpo["saldo_arquivo"], corpo["saldo_local"], corpo["saldo_confere"]) == ("1.00", "2.00", False)
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("0.79")  # não mudou

    eventos = db_session.scalars(
        select(EventoAuditoria)
        .where(EventoAuditoria.tipo.like("%IMPORTAD%"))
        .order_by(EventoAuditoria.sequencia)
    ).all()
    assert [e.tipo for e in eventos] == [
        "VEICULO_IMPORTADO",
        "CERTIFICADO_IMPORTADO",
        "CREDITO_IMPORTADO",
        "VEICULO_IMPORTADO",
        "CERTIFICADO_IMPORTADO",
        "CREDITO_IMPORTADO",
        "PORTABILIDADE_IMPORTADA",
    ]
    assert all(e.empresa_id == dados_demo.desmonte_id for e in eventos)
    assert all(e.usuario_id == dados_demo.admin_id for e in eventos)
    assert eventos[0].payload["origem"] == "Outra Plataforma"
    assert eventos[0].payload["anexos_nao_importados"] == ["f" * 64]
    assert eventos[-1].payload["importados"] == {"veiculo": 2}
    assert eventos[-1].payload["hash_conteudo"] == doc["hash_conteudo"]
    assert verificar_cadeia(db_session).integra

    # Importar de novo: tudo rejeitado, nada duplicado.
    r = _importar(client, auth, doc)
    assert _rejeicoes(r) == {chassi_a: "CHASSI_JA_CREDITADO", chassi_b: "CHASSI_JA_CREDITADO"}
    assert _total(db_session, Veiculo) == 4


def test_itens_rejeitados_nao_impedem_os_demais(
    client, auth, relogio, db_session, dados_demo, dossie
) -> None:
    doc = _outra_plataforma(_exportar(client, auth))
    chassi_a, chassi_b = _trocar(CHASSI_A), _trocar(CHASSI_B)
    for c in doc["certificados"]:
        if c["chassi"] == chassi_a:
            c["fator"] = "0.94"  # não é o fator de SINISTRADO_GRANDE
    r = _importar(client, auth, _com_hash(doc))
    assert r.status_code == 200, r.text
    assert _rejeicoes(r) == {chassi_a: "FATOR_DIVERGENTE"}
    assert r.json()["importados"] == [{"tipo": "veiculo", "chave": chassi_b}]
    assert db_session.scalar(select(Veiculo.id).where(Veiculo.chassi == chassi_a)) is None
    assert db_session.scalar(select(Veiculo.id).where(Veiculo.chassi == chassi_b)) is not None
    assert db_session.scalar(select(Peca.id).where(Peca.codigo_rastreio == "RASTREIO-0001X")) is None
    assert verificar_cadeia(db_session).integra


def _dossie_minimo(doc: dict, sufixo: str, **mudancas) -> dict:
    """Arquivo só com o veículo A de `doc`, como se viesse de outra plataforma, com um defeito."""
    novo = _outra_plataforma(doc, sufixo)
    chassi = _trocar(CHASSI_A, sufixo)
    novo["veiculos"] = [v for v in novo["veiculos"] if v["chassi"] == chassi]
    novo["certificados"] = [c for c in novo["certificados"] if c["chassi"] == chassi]
    novo["creditos"] = [c for c in novo["creditos"] if c["chassi"] == chassi]
    for secao, campos in mudancas.items():
        if campos is None:
            novo[secao] = []
        else:
            novo[secao][0].update(campos)
    return _com_hash(novo)


@pytest.mark.parametrize(
    ("mudancas", "motivo"),
    [
        ({"certificados": None}, "VEICULO_SEM_CERTIFICADO"),
        ({"creditos": None}, "CERTIFICADO_SEM_CREDITO"),
        ({"veiculos": {"laudo": None}}, "VEICULO_SEM_LAUDO"),
        ({"veiculos": {"estado": "EM_PROCESSO"}}, "ESTADO_DIVERGENTE"),
        ({"veiculos": {"tipo": "SUCATA_INSERVIVEL"}}, "TIPO_DIVERGENTE"),
        ({"certificados": {"emitente_cnpj": CNPJ_MONTADORA}}, "GERADORA_DIVERGENTE"),
        ({"certificados": {"emitido_em": "2020-01-01T12:00:00Z"}}, "FATOR_NAO_CONFIGURADO"),
        ({"creditos": {"quantidade": "0.50"}}, "QUANTIDADE_DIVERGENTE"),
        ({"creditos": {"titular_cnpj": "11444777000161"}}, "TITULAR_NAO_CADASTRADO"),
        ({"creditos": {"status": "DISPONIVEL"}}, "TITULAR_DIVERGENTE"),
    ],
)
def test_motivos_de_rejeicao_do_veiculo(client, auth, relogio, db_session, dossie, mudancas, motivo) -> None:
    doc = _dossie_minimo(_exportar(client, auth), "Y", **mudancas)
    r = _importar(client, auth, doc)
    assert r.status_code == 200, r.text
    assert r.json()["importados"] == []
    assert motivo in _rejeicoes(r).values(), r.json()
    assert _total(db_session, Veiculo) == 2


def test_numero_de_certificado_e_rastreio_ja_usados(client, auth, relogio, dossie) -> None:
    original = _exportar(client, auth)

    doc = _dossie_minimo(original, "Y", certificados={"numero": f"CRV-{CHASSI_A}"})
    doc["creditos"][0]["certificado_numero"] = f"CRV-{CHASSI_A}"
    assert "CERTIFICADO_DUPLICADO" in _rejeicoes(_importar(client, auth, _com_hash(doc))).values()

    doc = _dossie_minimo(original, "Y")
    doc["veiculos"][0]["pecas"][0]["codigo_rastreio"] = "RASTREIO-0001"
    assert "CODIGO_RASTREIO_DUPLICADO" in _rejeicoes(_importar(client, auth, _com_hash(doc))).values()


def test_chassi_em_processamento_aqui_nao_e_importado(client, auth, relogio, db_session, dossie) -> None:
    doc = _dossie_minimo(_exportar(client, auth), "Y")
    chassi = _trocar(CHASSI_A, "Y")
    veiculo = db_session.scalar(select(Veiculo).where(Veiculo.chassi == CHASSI_B))
    # Um veículo recebido aqui, ainda sem certificado, com o mesmo chassi do arquivo (em minúsculas).
    db_session.add(
        Veiculo(
            empresa_id=veiculo.empresa_id,
            chassi=chassi.lower(),
            data_entrada=veiculo.data_entrada,
            tipo_declarado=veiculo.tipo,
            tipo=veiculo.tipo,
            origem_aquisicao=veiculo.origem_aquisicao,
            documento_entrada_tipo=veiculo.documento_entrada_tipo,
            documento_entrada_numero="NF-2",
        )
    )
    db_session.flush()
    assert _rejeicoes(_importar(client, auth, doc)) == {chassi: "CHASSI_JA_REGISTRADO"}


def test_fabricante_nao_importa_veiculo(client, auth, relogio, dossie) -> None:
    doc = _dossie_minimo(_exportar(client, auth), "Y")
    doc["empresa"] = {"cnpj": CNPJ_MONTADORA, "razao_social": "Montadora Exemplo S.A.", "tipo": "FABRICANTE"}
    r = _importar(client, auth, _com_hash(doc))
    assert "EMPRESA_NAO_GERADORA" in _rejeicoes(r).values()


# --- Importação: fabricante --------------------------------------------------------------------


def _arquivo_do_fabricante(numero_certificado: str, chassis: list[str], **consumo) -> dict:
    """Histórico do fabricante do seed em outra plataforma: um MMV, um crédito recebido e um consumo."""
    quando = datetime(2026, 11, 12, 14, 0, tzinfo=UTC).isoformat()
    return _com_hash(
        {
            "versao_formato": "1.0",
            "gerado_em": quando,
            "origem": {"plataforma": "Outra Plataforma"},
            "empresa": {
                "cnpj": CNPJ_MONTADORA,
                "razao_social": "Montadora Exemplo S.A.",
                "tipo": "FABRICANTE",
            },
            "mmvs": [
                {
                    "codigo": "PICAPE-2.8",
                    "ncm": "87042190",
                    "nivel": 2,
                    "percentual_reciclabilidade": "88.00",
                    "ja_comercializado": False,
                    "efeitos_a_partir_de": "2026-11-10",
                    "cadastrado_em": quando,
                }
            ],
            "creditos": [
                {
                    "certificado_numero": numero_certificado,
                    "chassi": _trocar(CHASSI_A),
                    "quantidade": "0.79",
                    "status": "TRANSFERIDO",
                    "geradora_cnpj": CNPJ_DESMONTE,
                    "titular_cnpj": CNPJ_MONTADORA,
                    "gerado_em": quando,
                    "transferido_em": quando,
                }
            ],
            "consumos": [
                {
                    "referencia": "consumo-origem-1",
                    "mmv_codigo": "PICAPE-2.8",
                    "periodo": "2026-11",
                    "qv": len(chassis),
                    "rm": 5,
                    "pm": "300000.00",
                    "pb": "150000.00",
                    "urv_debito": "0.80",  # (2 / 5) * 2
                    "saldo_apos": "-0.01",
                    "regularizar_ate": "2027-02-28",
                    "prazo_reporte": "2026-12-14",
                    "registrado_em": quando,
                    "chassis": chassis,
                    **consumo,
                }
            ],
            "saldo": "-0.01",
        }
    )


def test_importa_historico_do_fabricante_depois_do_da_geradora(
    client, auth, relogio, db_session, dados_demo, dossie
) -> None:
    numero = f"CRV-{CHASSI_A}X"
    chassis = vins(2, inicio=900)
    doc = _arquivo_do_fabricante(numero, chassis)

    # Sem o arquivo da geradora, o crédito não existe aqui: o consumo entra, o crédito não.
    r = _importar(client, auth, doc)
    assert r.status_code == 200, r.text
    assert _rejeicoes(r) == {numero: "CREDITO_NAO_ENCONTRADO"}
    assert r.json()["importados"] == [
        {"tipo": "mmv", "chave": "PICAPE-2.8"},
        {"tipo": "consumo", "chave": "consumo-origem-1"},
    ]
    # Aqui o fabricante já tinha 0.79 (do crédito nativo): 0.79 - 0.80. Coincide com o arquivo.
    assert (r.json()["saldo_local"], r.json()["saldo_confere"]) == ("-0.01", True)

    consumo = db_session.scalar(select(Consumo))
    assert (consumo.qv, consumo.rm, consumo.urv_debito) == (2, 5, Decimal("0.80"))
    assert consumo.saldo_apos == Decimal("-0.01")  # o saldo deste livro
    assert consumo.regularizar_ate.isoformat() == "2027-02-28"
    assert consumo.registrado_em == datetime(2026, 11, 12, 14, 0, tzinfo=UTC)
    assert sorted(db_session.scalars(select(ConsumoChassi.chassi))) == chassis
    mmv = db_session.scalar(select(Mmv).where(Mmv.codigo == "PICAPE-2.8"))
    assert (mmv.fabricante_id, mmv.nivel) == (dados_demo.montadora_id, 2)

    # A geradora migra: o crédito passa a existir aqui, transferido ao fabricante, sem a entrada.
    assert _importar(client, auth, _outra_plataforma(_exportar(client, auth))).json()["rejeitados"] == []
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("-0.01")

    # Agora o arquivo do fabricante traz a entrada; o resto já está aqui.
    r = _importar(client, auth, doc)
    assert r.json()["importados"] == [{"tipo": "credito_recebido", "chave": numero}]
    assert _rejeicoes(r) == {"PICAPE-2.8": "MMV_JA_CADASTRADO", "consumo-origem-1": "CHASSI_JA_CONSUMIDO"}
    assert saldo_empresa(db_session, dados_demo.montadora_id) == Decimal("0.78")
    entrada = db_session.scalar(
        select(UrvLancamento)
        .join(UrvCredito, UrvCredito.id == UrvLancamento.credito_id)
        .join(Certificado, Certificado.id == UrvCredito.certificado_id)
        .where(Certificado.numero == numero, UrvLancamento.tipo == LancamentoTipo.TRANSFERENCIA_ENTRADA)
    )
    assert (entrada.empresa_id, entrada.contraparte_id) == (dados_demo.montadora_id, dados_demo.desmonte_id)

    # RF-17: a transferência é única também na importação.
    assert _rejeicoes(_importar(client, auth, doc))[numero] == "TRANSFERENCIA_JA_REGISTRADA"
    assert _total(db_session, Consumo) == 1
    assert verificar_cadeia(db_session).integra


@pytest.mark.parametrize(
    ("consumo", "motivo"),
    [
        ({"urv_debito": "0.40"}, "DEBITO_DIVERGENTE"),  # ignorou o multiplicador de preço
        ({"qv": 3}, "QV_DIVERGENTE"),
        ({"rm": 10}, "RM_DIVERGENTE"),  # o MMV é nível 2
        ({"mmv_codigo": "NAO-EXISTE"}, "MMV_NAO_ENCONTRADO"),
    ],
)
def test_motivos_de_rejeicao_do_consumo(client, auth, relogio, db_session, dossie, consumo, motivo) -> None:
    doc = _arquivo_do_fabricante("CRV-INEXISTENTE", vins(2, inicio=900), **consumo)
    r = _importar(client, auth, doc)
    assert r.status_code == 200, r.text
    assert _rejeicoes(r)["consumo-origem-1"] == motivo
    assert _total(db_session, Consumo) == 0
    assert _total(db_session, ConsumoChassi) == 0


def test_consumo_importado_respeita_chassi_ja_consumido_aqui(
    client, auth, relogio, db_session, consumo
) -> None:
    doc = _arquivo_do_fabricante("CRV-INEXISTENTE", [vins(5)[0], "9BW00000000000999"])
    r = _importar(client, auth, doc)
    assert _rejeicoes(r)["consumo-origem-1"] == "CHASSI_JA_CONSUMIDO"  # RF-21 entre plataformas
    assert _total(db_session, Consumo) == 1


def test_geradora_nao_importa_mmv_nem_consumo(client, auth, relogio, dossie) -> None:
    doc = _arquivo_do_fabricante("CRV-X", vins(2, inicio=900))
    doc["empresa"] = {"cnpj": CNPJ_DESMONTE, "razao_social": "Desmonte Paraná S.A.", "tipo": "DESMONTADORA"}
    doc["creditos"] = []
    r = _importar(client, auth, _com_hash(doc))
    assert _rejeicoes(r) == {
        "PICAPE-2.8": "EMPRESA_NAO_FABRICANTE",
        "consumo-origem-1": "EMPRESA_NAO_FABRICANTE",
    }
