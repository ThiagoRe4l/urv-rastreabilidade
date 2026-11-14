"""Apoio dos testes de conformidade (dono: qa-conformidade).

Tudo aqui fala com a API pelo contrato (`docs/03-contrato-api.md`). Nada depende da
implementação dos módulos de fluxo e de URV.

`Api` é um invólucro do cliente de teste: antes de cada chamada, confere se a rota existe no
OpenAPI da aplicação. Se não existe, o teste é marcado como `xfail` com o motivo
"rota ainda não existe: MÉTODO /caminho". Quando a rota passa a existir, o `xfail` some
sozinho e o teste passa a valer: não há marcação a remover na integração.
"""

import random
import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from scripts.seed import EMAIL_ADMIN, EMAIL_AUDITOR, EMAIL_DESMONTADORA, EMAIL_FABRICANTE

ADMIN = EMAIL_ADMIN
AUDITOR = EMAIL_AUDITOR
OPERADOR = EMAIL_DESMONTADORA  # DESMONTADORA do seed (Desmonte Paraná S.A.)
FISCAL = EMAIL_FABRICANTE  # FABRICANTE do seed (Montadora Exemplo S.A.)

PREFIXO = "/api/v1"
_METODOS = {"get", "post", "put", "patch", "delete"}
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# Art. 3º §2º da portaria.
FATORES = {
    "LICENCIADO_RODAGEM": Decimal("1.00"),
    "SINISTRADO_PEQUENA_MEDIA": Decimal("0.94"),
    "SUCATA_APROVEITAVEL": Decimal("0.85"),
    "SINISTRADO_GRANDE": Decimal("0.79"),
    "SUCATA_MOTOR_INSERVIVEL": Decimal("0.68"),
    "SUCATA_INSERVIVEL": Decimal("0.38"),
}

# PNG 1x1 e PDF mínimos: os uploads aceitam só imagem e PDF.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)
PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
)


def pdf_unico() -> bytes:
    """PDF mínimo com conteúdo único: a evidência de classificação não se repete entre veículos (A7)."""
    return PDF + f"%{uuid.uuid4().hex}\n".encode()


PESAGENS_PADRAO = (
    ("FERROSO", "RECICLAGEM", "800.000"),
    ("NAO_FERROSO", "RECICLAGEM", "100.000"),
    ("NAO_METALICO", "REJEITO", "100.000"),
)  # 900 aproveitados / 1.000 de entrada = 90,00 % (art. 18 §5º)


class Api:
    """Cliente HTTP do contrato. `api.post("/veiculos", OPERADOR, json={...})`."""

    def __init__(self, client: TestClient, auth: Callable[[str], dict[str, str]]) -> None:
        self.client = client
        self._auth = auth
        self._rotas: list[tuple[str, re.Pattern[str]]] = []
        for caminho, operacoes in client.app.openapi()["paths"].items():
            partes = re.split(r"\{[^}]+\}", caminho)
            padrao = re.compile("[^/]+".join(re.escape(p) for p in partes))
            self._rotas += [(m.upper(), padrao) for m in operacoes if m in _METODOS]

    def existe(self, metodo: str, caminho: str) -> bool:
        alvo = PREFIXO + caminho.split("?")[0]
        return any(m == metodo and p.fullmatch(alvo) for m, p in self._rotas)

    def exigir(self, metodo: str, caminho: str) -> None:
        if not self.existe(metodo, caminho):
            pytest.xfail(f"rota ainda não existe: {metodo} {_UUID.sub('{id}', caminho.split('?')[0])}")

    def chamar(self, metodo: str, caminho: str, quem: str | None = None, **kw: Any) -> Response:
        self.exigir(metodo, caminho)
        headers = dict(kw.pop("headers", None) or {})
        if quem is not None:
            headers.update(self._auth(quem))
        return self.client.request(metodo, PREFIXO + caminho, headers=headers, **kw)

    def get(self, caminho: str, quem: str | None = None, **kw: Any) -> Response:
        return self.chamar("GET", caminho, quem, **kw)

    def post(self, caminho: str, quem: str | None = None, **kw: Any) -> Response:
        return self.chamar("POST", caminho, quem, **kw)

    def put(self, caminho: str, quem: str | None = None, **kw: Any) -> Response:
        return self.chamar("PUT", caminho, quem, **kw)

    def patch(self, caminho: str, quem: str | None = None, **kw: Any) -> Response:
        return self.chamar("PATCH", caminho, quem, **kw)


@dataclass(frozen=True)
class EmpresaTeste:
    id: str
    cnpj: str
    email: str  # usuário da empresa, com a senha do seed


# --- Asserções e conversões -----------------------------------------------------------------


def ok(r: Response) -> Any:
    """Exige 200 ou 201 e devolve o corpo."""
    assert r.status_code in (200, 201), f"{r.request.method} {r.request.url}: {r.status_code} {r.text}"
    return r.json()


def erro(r: Response, status: int | Iterable[int], codigo: str | None = None) -> dict[str, Any]:
    """Exige o status (ou um dos status) e, se informado, o `codigo` estável do contrato."""
    aceitos = (status,) if isinstance(status, int) else tuple(status)
    assert r.status_code in aceitos, f"{r.request.method} {r.request.url}: {r.status_code} {r.text}"
    corpo = r.json()
    if codigo is not None:
        assert corpo.get("codigo") == codigo, corpo
    return corpo


def dec(valor: Any) -> Decimal:
    assert valor is not None
    return Decimal(str(valor))


def itens(r: Response) -> list[dict[str, Any]]:
    corpo = ok(r)
    assert set(corpo) >= {"itens", "total"}, corpo
    return corpo["itens"]


def hojes() -> set[str]:
    """Data de hoje, local e em UTC: o servidor pode usar qualquer uma das duas."""
    return {date.today().isoformat(), datetime.now(UTC).date().isoformat()}


# --- Geradores ------------------------------------------------------------------------------


def cnpj_aleatorio() -> str:
    base = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]  # noqa: S311

    def digito(numeros: list[int]) -> int:
        pesos = list(range(len(numeros) - 7, 1, -1)) + list(range(9, 1, -1))
        resto = sum(n * p for n, p in zip(numeros, pesos, strict=True)) % 11
        return 0 if resto < 2 else 11 - resto

    base.append(digito(base))
    base.append(digito(base))
    return "".join(map(str, base))


def novo_chassi() -> str:
    """17 caracteres válidos para VIN (sem I, O, Q)."""
    return "9BW" + uuid.uuid4().hex[:14].upper()


def chassis(n: int) -> list[str]:
    return [novo_chassi() for _ in range(n)]


def periodo_atual() -> str:
    return date.today().strftime("%Y-%m")


def decimo_dia_util_do_mes_seguinte(periodo: str) -> date:
    """RF-20, art. 7º parágrafo único. Dia útil: segunda a sexta, sem feriados (premissa)."""
    ano, mes = map(int, periodo.split("-"))
    dia = date(ano + mes // 12, mes % 12 + 1, 1)
    uteis = 0
    while True:
        if dia.weekday() < 5:
            uteis += 1
            if uteis == 10:
                return dia
        dia += timedelta(days=1)


def ultimo_dia_do_terceiro_mes_seguinte(registro: date) -> date:
    """RF-19, art. 8º §1º."""
    indice = registro.year * 12 + (registro.month - 1) + 4  # primeiro dia do quarto mês seguinte
    return date(indice // 12, indice % 12 + 1, 1) - timedelta(days=1)


# --- Fluxo do veículo -----------------------------------------------------------------------


def dados_veiculo(**alteracoes: Any) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "chassi": novo_chassi(),
        "placa": "QAT" + f"{random.randint(0, 9)}A{random.randint(10, 99)}",  # noqa: S311
        "renavam": f"{uuid.uuid4().int % 10**11:011d}",  # único por veículo (A7)
        "data_entrada": date.today().isoformat(),
        "tipo": "SUCATA_INSERVIVEL",
        "origem_aquisicao": "COMPRA_DIRETA",
        "documento_entrada_tipo": "NF_ENTRADA",
        "documento_entrada_numero": "NF-1001",
        "certidao_baixa_numero": f"CB-{uuid.uuid4().hex[:12].upper()}",  # única por veículo (A7)
        "peso_entrada_kg": "1000.000",  # PESAGENS_PADRAO pesa o veículo inteiro
        "sem_viabilidade_desmontagem": False,
    }
    corpo.update(alteracoes)
    return corpo


def receber_veiculo(api: Api, quem: str = OPERADOR, **alteracoes: Any) -> dict[str, Any]:
    return ok(api.post("/veiculos", quem, json=dados_veiculo(**alteracoes)))


def anexar(
    api: Api,
    quem: str,
    veiculo_id: str,
    tipo: str,
    etapa_tipo: str,
    *,
    conteudo: bytes | None = None,
    nome: str | None = None,
    mime: str | None = None,
) -> Response:
    foto = tipo == "FOTO"
    padrao = PNG if foto else (pdf_unico() if tipo == "EVIDENCIA_CLASSIFICACAO" else PDF)
    arquivo = (
        nome or ("foto.png" if foto else "documento.pdf"),
        conteudo if conteudo is not None else padrao,
        mime or ("image/png" if foto else "application/pdf"),
    )
    return api.post(
        f"/veiculos/{veiculo_id}/anexos",
        quem,
        files={"arquivo": arquivo},
        data={"tipo": tipo, "etapa_tipo": etapa_tipo},
    )


def registrar_etapa(api: Api, quem: str, veiculo_id: str, tipo: str, *, concluir: bool = True) -> Response:
    agora = datetime.now(UTC).replace(microsecond=0)
    corpo = {"iniciada_em": (agora - timedelta(hours=1)).isoformat(), "observacoes": f"Etapa {tipo}"}
    if concluir:
        corpo["concluida_em"] = agora.isoformat()
    return api.put(f"/veiculos/{veiculo_id}/etapas/{tipo}", quem, json=corpo)


def criar_peca(api: Api, quem: str, veiculo_id: str, **alteracoes: Any) -> dict[str, Any]:
    corpo = {
        "nome": "Porta dianteira esquerda",
        "descricao": "Porta completa, sem avarias",
        "classificacao": "REUTILIZAVEL",
        "condicao": "USADA",
        "destino": "ESTOQUE",
    }
    corpo.update(alteracoes)
    return ok(api.post(f"/veiculos/{veiculo_id}/pecas", quem, json=corpo))


def pesar(api: Api, quem: str, veiculo_id: str, fracao: str, destino: str, peso_kg: str) -> Response:
    corpo = {"fracao": fracao, "destino": destino, "peso_kg": peso_kg}
    return api.post(f"/veiculos/{veiculo_id}/pesagens", quem, json=corpo)


def emitir_dmr(api: Api, quem: str, veiculo_id: str, **alteracoes: Any) -> Response:
    corpo = {
        "numero": f"DMR-{uuid.uuid4().hex[:8].upper()}",
        "destinatario_nome": "Siderúrgica Exemplo Ltda.",
        "destinatario_cnpj": cnpj_aleatorio(),
        "tipo_material": "Sucata ferrosa",
        "peso_kg": "800.000",
    }
    corpo.update(alteracoes)
    return api.post(f"/veiculos/{veiculo_id}/dmrs", quem, json=corpo)


def assinar_laudo(api: Api, quem: str, veiculo_id: str) -> Response:
    corpo = {"responsavel_nome": "Eng. Marina Duarte", "responsavel_registro": "CREA-PR 123456"}
    return api.post(f"/veiculos/{veiculo_id}/laudo", quem, json=corpo)


# Cada chave é uma evidência ou etapa que `processar_veiculo` pode deixar de fora.
EVIDENCIAS = (
    "documento_entrada",
    "certidao_baixa",
    "foto_recepcao",
    "etapa_recepcao",
    "etapa_descontaminacao",
    "foto_descontaminacao",
    "etapa_desmontagem",
    "foto_desmontagem",
    "peca_descaracterizada",
    "etapa_destruicao",
    "pesagem",
    "foto_destruicao",
    "laudo",
)


def processar_veiculo(
    api: Api,
    quem: str = OPERADOR,
    *,
    omitir: Iterable[str] = (),
    pesagens: Iterable[tuple[str, str, str]] = PESAGENS_PADRAO,
    **alteracoes: Any,
) -> dict[str, Any]:
    """Leva um veículo até o ponto de emitir o certificado (art. 18 III a VII).

    `omitir` deixa de fora itens de `EVIDENCIAS`. `evidencia_classificacao` também pode ser
    omitida: aí o veículo fica como sucata inservível (RF-07).
    """
    fora = set(omitir)
    assert fora <= set(EVIDENCIAS) | {"evidencia_classificacao"}, fora
    v = receber_veiculo(api, quem, **alteracoes)
    vid = v["id"]

    if "documento_entrada" not in fora:
        ok(anexar(api, quem, vid, "DOCUMENTO_ENTRADA", "RECEPCAO"))
    if "certidao_baixa" not in fora:
        ok(anexar(api, quem, vid, "CERTIDAO_BAIXA", "RECEPCAO"))
    if v["tipo_declarado"] != "SUCATA_INSERVIVEL" and "evidencia_classificacao" not in fora:
        ok(anexar(api, quem, vid, "EVIDENCIA_CLASSIFICACAO", "RECEPCAO"))
    if "foto_recepcao" not in fora:
        ok(anexar(api, quem, vid, "FOTO", "RECEPCAO"))
    if "etapa_recepcao" not in fora:
        ok(registrar_etapa(api, quem, vid, "RECEPCAO"))

    if "etapa_descontaminacao" not in fora:
        ok(registrar_etapa(api, quem, vid, "DESCONTAMINACAO"))
    if "foto_descontaminacao" not in fora:
        ok(anexar(api, quem, vid, "FOTO", "DESCONTAMINACAO"))

    if not v["sem_viabilidade_desmontagem"]:
        if "etapa_desmontagem" not in fora:
            ok(registrar_etapa(api, quem, vid, "DESMONTAGEM"))
        if "foto_desmontagem" not in fora:
            ok(anexar(api, quem, vid, "FOTO", "DESMONTAGEM"))
        criar_peca(api, quem, vid)
        inutil = criar_peca(
            api, quem, vid, nome="Airbag do motorista", classificacao="NAO_REUTILIZAVEL", destino="RECICLAGEM"
        )
        if "peca_descaracterizada" not in fora:
            ok(api.patch(f"/pecas/{inutil['id']}", quem, json={"descaracterizada": True}))

    if "etapa_destruicao" not in fora:
        ok(registrar_etapa(api, quem, vid, "DESTRUICAO"))
    if "pesagem" not in fora:
        for fracao, destino, peso in pesagens:
            ok(pesar(api, quem, vid, fracao, destino, peso))
    if "foto_destruicao" not in fora:
        ok(anexar(api, quem, vid, "FOTO", "DESTRUICAO"))

    if "laudo" not in fora:
        r = assinar_laudo(api, quem, vid)
        if not fora & {"etapa_descontaminacao", "etapa_destruicao"}:
            ok(r)  # com as duas etapas concluídas, o laudo tem de sair
    return ok(api.get(f"/veiculos/{vid}", quem))


def emitir_certificado(api: Api, quem: str, veiculo_id: str) -> Response:
    return api.post(f"/veiculos/{veiculo_id}/certificado", quem)


def gerar_credito(api: Api, quem: str = OPERADOR, **alteracoes: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Processa um veículo e emite o certificado. Devolve (veículo, certificado com `credito`)."""
    v = processar_veiculo(api, quem, **alteracoes)
    cert = ok(emitir_certificado(api, quem, v["id"]))
    assert cert.get("credito"), cert
    return v, cert


def transferir(api: Api, quem: str, credito_id: str, fabricante_id: Any) -> Response:
    return api.post(
        f"/urv/creditos/{credito_id}/transferir", quem, json={"fabricante_id": str(fabricante_id)}
    )


# --- URV ------------------------------------------------------------------------------------


def saldo(api: Api, quem: str) -> Decimal:
    return dec(ok(api.get("/urv/saldo", quem))["saldo"])


def criar_mmv(api: Api, quem: str = FISCAL, **alteracoes: Any) -> dict[str, Any]:
    corpo = {
        "codigo": f"MMV-{uuid.uuid4().hex[:8].upper()}",
        "ncm": "87032310",
        "nivel": 1,
        "percentual_reciclabilidade": "85.00",
        "ja_comercializado": False,
    }
    corpo.update(alteracoes)
    return ok(api.post("/mmvs", quem, json=corpo))


def consumir(
    api: Api,
    quem: str,
    mmv_id: str,
    lista_chassis: list[str],
    *,
    preco_medio: str = "150000.00",
    periodo: str | None = None,
) -> Response:
    corpo = {
        "mmv_id": mmv_id,
        "periodo": periodo or periodo_atual(),
        "preco_medio": preco_medio,
        "chassis": lista_chassis,
    }
    return api.post("/urv/consumos", quem, json=corpo)


# --- Trilha de auditoria --------------------------------------------------------------------

GATILHO_TRILHA = "trg_evento_auditoria_imutavel"


def adulterar(db_session: Session, sequencia: int) -> None:
    """O que `scripts/adulterar.py` faz: desliga o gatilho e altera um evento."""
    db_session.execute(text(f"ALTER TABLE evento_auditoria DISABLE TRIGGER {GATILHO_TRILHA}"))
    db_session.execute(
        text(
            "UPDATE evento_auditoria SET payload = payload || '{\"_adulterado\": true}' WHERE sequencia = :s"
        ),
        {"s": sequencia},
    )
    db_session.execute(text(f"ALTER TABLE evento_auditoria ENABLE TRIGGER {GATILHO_TRILHA}"))
