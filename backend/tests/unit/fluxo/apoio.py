"""Apoio dos testes do fluxo do veículo: dados de exemplo e passos do fluxo por HTTP."""

import uuid

from sqlalchemy import select

from app.models import EventoAuditoria

API = "/api/v1"
VEICULOS = f"{API}/veiculos"

CHASSI = "9BWZZZ377VT004251"
EMAIL_OUTRA = "operador@outra.local"
CNPJ_OUTRA = "11222333000181"
CNPJ_DESTINATARIO = "11444777000161"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PDF = b"%PDF-1.4\n%%EOF\n"

INICIO = "2026-11-10T08:00:00Z"
FIM = "2026-11-10T17:00:00Z"

# Passos que levam um veículo até o certificado, na ordem em que o fluxo completo os executa.
PASSOS = (
    "etapa_recepcao",
    "documento_entrada",
    "certidao_baixa",
    "foto_recepcao",
    "evidencia_classificacao",
    "etapa_descontaminacao",
    "foto_descontaminacao",
    "etapa_desmontagem",
    "foto_desmontagem",
    "pecas",
    "etapa_destruicao",
    "pesagens",
    "foto_destruicao",
    "laudo",
)


def pdf_unico() -> bytes:
    """PDF com conteúdo único: a evidência de classificação não se repete entre veículos (A7)."""
    return PDF + f"%{uuid.uuid4().hex}\n".encode()


def dados_veiculo(**mudancas) -> dict:
    # Renavam e certidão de baixa são únicos (A7 da revisão): sorteados a cada veículo.
    return {
        "chassi": CHASSI,
        "placa": "ABC1D23",
        "renavam": f"{uuid.uuid4().int % 10**11:011d}",
        "data_entrada": "2026-11-10",
        "tipo": "SINISTRADO_PEQUENA_MEDIA",
        "origem_aquisicao": "LEILAO_SEGURADORA",
        "documento_entrada_tipo": "NF_ENTRADA",
        "documento_entrada_numero": "NF-000123",
        "certidao_baixa_numero": f"CB-{uuid.uuid4().hex[:12].upper()}",
        "peso_entrada_kg": "1180.500",
        "sem_viabilidade_desmontagem": False,
        **mudancas,
    }


def criar_veiculo(client, headers, **mudancas) -> dict:
    r = client.post(VEICULOS, json=dados_veiculo(**mudancas), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def anexar(client, headers, veiculo_id, tipo, etapa_tipo=None, conteudo=PNG, nome="arquivo.png"):
    dados = {"tipo": tipo}
    if etapa_tipo is not None:
        dados["etapa_tipo"] = etapa_tipo
    return client.post(
        f"{VEICULOS}/{veiculo_id}/anexos",
        data=dados,
        files={"arquivo": (nome, conteudo, "application/octet-stream")},
        headers=headers,
    )


def etapa(client, headers, veiculo_id, tipo, inicio=INICIO, fim=FIM, **extra):
    corpo = {"iniciada_em": inicio, **extra}
    if fim is not None:
        corpo["concluida_em"] = fim
    return client.put(f"{VEICULOS}/{veiculo_id}/etapas/{tipo}", json=corpo, headers=headers)


def pesagem(client, headers, veiculo_id, fracao="FERROSO", destino="RECICLAGEM", peso_kg="700.000"):
    return client.post(
        f"{VEICULOS}/{veiculo_id}/pesagens",
        json={"fracao": fracao, "destino": destino, "peso_kg": peso_kg},
        headers=headers,
    )


def peca(client, headers, veiculo_id, **mudancas):
    corpo = {
        "nome": "Porta dianteira esquerda",
        "descricao": "Sem avarias",
        "classificacao": "REUTILIZAVEL",
        "condicao": "USADA",
        "destino": "ESTOQUE",
        **mudancas,
    }
    return client.post(f"{VEICULOS}/{veiculo_id}/pecas", json=corpo, headers=headers)


def laudo(client, headers, veiculo_id):
    return client.post(
        f"{VEICULOS}/{veiculo_id}/laudo",
        json={"responsavel_nome": "Eng. Ana Souza", "responsavel_registro": "CREA-PR 12345"},
        headers=headers,
    )


def certificado(client, headers, veiculo_id):
    return client.post(f"{VEICULOS}/{veiculo_id}/certificado", headers=headers)


def executar_passos(client, headers, veiculo_id, pular: tuple[str, ...] = ()) -> None:
    """Executa os PASSOS por HTTP, menos os de `pular`. Não confere o laudo: ele pode falhar
    de propósito quando uma etapa que ele exige foi pulada."""

    def ok(resposta) -> None:
        assert resposta.status_code in (200, 201), resposta.text

    for passo in PASSOS:
        if passo in pular:
            continue
        match passo:
            case "etapa_recepcao":
                ok(etapa(client, headers, veiculo_id, "RECEPCAO"))
            case "documento_entrada":
                ok(anexar(client, headers, veiculo_id, "DOCUMENTO_ENTRADA", conteudo=PDF, nome="nf.pdf"))
            case "certidao_baixa":
                ok(anexar(client, headers, veiculo_id, "CERTIDAO_BAIXA", conteudo=PDF, nome="baixa.pdf"))
            case "foto_recepcao":
                ok(anexar(client, headers, veiculo_id, "FOTO", "RECEPCAO"))
            case "evidencia_classificacao":
                ok(
                    anexar(
                        client,
                        headers,
                        veiculo_id,
                        "EVIDENCIA_CLASSIFICACAO",
                        conteudo=pdf_unico(),
                        nome="laudo.pdf",
                    )
                )
            case "etapa_descontaminacao":
                ok(etapa(client, headers, veiculo_id, "DESCONTAMINACAO"))
            case "foto_descontaminacao":
                ok(anexar(client, headers, veiculo_id, "FOTO", "DESCONTAMINACAO"))
            case "etapa_desmontagem":
                ok(etapa(client, headers, veiculo_id, "DESMONTAGEM"))
            case "foto_desmontagem":
                ok(anexar(client, headers, veiculo_id, "FOTO", "DESMONTAGEM", conteudo=JPEG, nome="f.jpg"))
            case "pecas":
                ok(peca(client, headers, veiculo_id))
            case "etapa_destruicao":
                ok(etapa(client, headers, veiculo_id, "DESTRUICAO"))
            case "pesagens":
                ok(pesagem(client, headers, veiculo_id, "FERROSO", "RECICLAGEM", "700.000"))
                ok(pesagem(client, headers, veiculo_id, "NAO_METALICO", "REJEITO", "300.000"))
            case "foto_destruicao":
                ok(anexar(client, headers, veiculo_id, "FOTO", "DESTRUICAO"))
            case "laudo":
                laudo(client, headers, veiculo_id)


def eventos(db_session, tipo: str, entidade_id) -> list[EventoAuditoria]:
    return list(
        db_session.scalars(
            select(EventoAuditoria)
            .where(EventoAuditoria.tipo == tipo, EventoAuditoria.entidade_id == uuid.UUID(str(entidade_id)))
            .order_by(EventoAuditoria.sequencia)
        )
    )
