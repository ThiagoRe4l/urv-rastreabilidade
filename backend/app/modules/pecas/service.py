"""Peças do veículo: classificação, etiqueta de rastreio e consulta. RF-09 e RF-10.

Services não fazem commit; a rota faz (ver app/core/db.py).
"""

import secrets
import uuid
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.deps import filtrar_por_empresa, garantir_acesso_empresa
from app.core.erros import ErroNegocio, NaoEncontrado
from app.core.relogio import data_operacao
from app.models import Empresa, Peca, PecaClassificacao, PecaCondicao, PecaDestino, Usuario, Veiculo
from app.modules.auditoria.service import registrar_evento
from app.modules.pecas.schemas import Etiqueta, PecaAtualizar, PecaCriar, PecaSaida, RastreioSaida
from app.modules.veiculos import service as veiculos
from app.modules.veiculos.schemas import normalizar_chassi

# Anexo III, itens 6.b e 10: peça não reutilizável vai para reciclagem, descarte,
# recondicionamento ou remanufatura. Nunca para estoque, revenda ou exportação.
DESTINOS_NAO_REUTILIZAVEL = frozenset(
    {
        PecaDestino.RECICLAGEM,
        PecaDestino.DESCARTE,
        PecaDestino.REMANUFATURA,
        PecaDestino.RECONDICIONAMENTO,
    }
)


def _validar_destino(classificacao: PecaClassificacao, destino: PecaDestino | None) -> None:
    if classificacao == PecaClassificacao.NAO_REUTILIZAVEL and destino not in DESTINOS_NAO_REUTILIZAVEL:
        raise ErroNegocio(
            422,
            "DESTINO_INCOMPATIVEL",
            "Peça não reutilizável só pode ir para reciclagem, descarte, remanufatura ou "
            "recondicionamento (Anexo III, itens 6 e 10).",
        )


def _novo_codigo(session: Session) -> str:
    """Código de rastreio único e não sequencial (não dá para enumerar peças na consulta pública)."""
    while True:
        codigo = f"PC-{secrets.token_hex(8).upper()}"
        if not session.scalar(select(Peca.id).where(Peca.codigo_rastreio == codigo)):
            return codigo


# --- Saída -------------------------------------------------------------------------------------


def _etiqueta(peca: Peca, chassi: str, cnpj: str) -> Etiqueta | None:
    """RF-09, Anexo III, item 8: nome da peça, chassi de origem, data e CNPJ da desmontadora."""
    if peca.classificacao != PecaClassificacao.REUTILIZAVEL or peca.codigo_rastreio is None:
        return None
    return Etiqueta(
        nome=peca.nome,
        chassi=chassi,
        data=data_operacao(peca.criado_em),  # Anexo III 8; L-11; PM-URV-06
        cnpj=cnpj,
        codigo=peca.codigo_rastreio,
    )


def para_saida(session: Session, pecas: Sequence[Peca]) -> list[PecaSaida]:
    """Monta a saída com chassi e etiqueta, buscando veículo e empresa numa consulta só."""
    ids = {p.veiculo_id for p in pecas}
    origem: dict[uuid.UUID, tuple[str, str]] = {}
    if ids:
        linhas = session.execute(
            select(Veiculo.id, Veiculo.chassi, Empresa.cnpj)
            .join(Empresa, Empresa.id == Veiculo.empresa_id)
            .where(Veiculo.id.in_(ids))
        )
        origem = {vid: (chassi, cnpj) for vid, chassi, cnpj in linhas}
    saida = []
    for p in pecas:
        chassi, cnpj = origem[p.veiculo_id]
        saida.append(
            PecaSaida(
                id=p.id,
                veiculo_id=p.veiculo_id,
                chassi=chassi,
                nome=p.nome,
                descricao=p.descricao,
                classificacao=p.classificacao,
                codigo_rastreio=p.codigo_rastreio,
                condicao=p.condicao,
                destino=p.destino,
                descaracterizada=p.descaracterizada,
                criado_em=p.criado_em,
                etiqueta=_etiqueta(p, chassi, cnpj),
            )
        )
    return saida


# --- Escrita -----------------------------------------------------------------------------------


def registrar_peca(session: Session, usuario: Usuario, veiculo_id: uuid.UUID, dados: PecaCriar) -> Peca:
    """RF-09, art. 18 V; Anexo III 6 a 8."""
    veiculo = veiculos.obter_veiculo(session, usuario, veiculo_id, bloquear=True)
    # O certificado atesta a situação de todas as peças; não entram peças depois dele.
    veiculos.exigir_sem_certificado(veiculo)
    _validar_destino(dados.classificacao, dados.destino)

    reutilizavel = dados.classificacao == PecaClassificacao.REUTILIZAVEL
    peca = Peca(
        veiculo=veiculo,
        nome=dados.nome,
        descricao=dados.descricao,
        classificacao=dados.classificacao,
        # Anexo III, item 8: toda peça reutilizável sai etiquetada com código de rastreio.
        codigo_rastreio=_novo_codigo(session) if reutilizavel else None,
        condicao=dados.condicao,
        destino=dados.destino,
        descaracterizada=False,
    )
    session.add(peca)
    veiculos.marcar_em_processo(veiculo)
    session.flush()
    registrar_evento(
        session,
        usuario,
        "PECA_REGISTRADA",
        "peca",
        peca.id,
        {
            "veiculo_id": veiculo.id,
            "nome": peca.nome,
            "classificacao": peca.classificacao,
            "codigo_rastreio": peca.codigo_rastreio,
            "condicao": peca.condicao,
            "destino": peca.destino,
        },
    )
    return peca


def atualizar_peca(session: Session, usuario: Usuario, peca_id: uuid.UUID, dados: PecaAtualizar) -> Peca:
    """Muda o destino ou marca a descaracterização. Vale também depois do certificado
    (a peça em estoque é vendida mais tarde), por isso a trilha guarda antes e depois."""
    peca = session.scalar(select(Peca).where(Peca.id == peca_id).with_for_update())
    if peca is None:
        raise NaoEncontrado("Peça")
    garantir_acesso_empresa(usuario, peca.veiculo.empresa_id, "Peça")

    mudancas: dict[str, dict] = {}
    if dados.destino is not None and dados.destino != peca.destino:
        _validar_destino(peca.classificacao, dados.destino)
        mudancas["destino"] = {"antes": peca.destino, "depois": dados.destino}
    if dados.descaracterizada is not None and dados.descaracterizada != peca.descaracterizada:
        if not dados.descaracterizada:
            raise ErroNegocio(
                422,
                "DESCARACTERIZACAO_IRREVERSIVEL",
                "Uma peça descaracterizada não volta ao estado anterior.",
            )
        mudancas["descaracterizada"] = {"antes": False, "depois": True}
    if not mudancas:
        return peca

    for campo, valores in mudancas.items():
        setattr(peca, campo, valores["depois"])
    session.flush()
    registrar_evento(
        session, usuario, "PECA_ATUALIZADA", "peca", peca.id, {"veiculo_id": peca.veiculo_id, **mudancas}
    )
    return peca


# --- Consulta ----------------------------------------------------------------------------------


def consulta_pecas(
    usuario: Usuario,
    *,
    veiculo_id: uuid.UUID | None = None,
    chassi: str | None,
    nome: str | None,
    condicao: PecaCondicao | None,
    destino: PecaDestino | None,
    classificacao: PecaClassificacao | None,
) -> Select:
    """RF-10, Anexo III 16: por origem (chassi), tipo (nome, classificação), condição e destino."""
    stmt = select(Peca).join(Veiculo, Veiculo.id == Peca.veiculo_id)
    stmt = filtrar_por_empresa(stmt, Veiculo.empresa_id, usuario)
    if veiculo_id is not None:  # PM-WEB-04: peças de um veículo, na página dele
        stmt = stmt.where(Peca.veiculo_id == veiculo_id)
    if chassi:
        stmt = stmt.where(Veiculo.chassi.contains(normalizar_chassi(chassi), autoescape=True))
    if nome and nome.strip():
        stmt = stmt.where(Peca.nome.icontains(nome.strip(), autoescape=True))
    if condicao is not None:
        stmt = stmt.where(Peca.condicao == condicao)
    if destino is not None:
        stmt = stmt.where(Peca.destino == destino)
    if classificacao is not None:
        stmt = stmt.where(Peca.classificacao == classificacao)
    return stmt.order_by(Peca.criado_em.desc(), Peca.id)


def rastrear(session: Session, codigo: str) -> RastreioSaida:
    """Consulta pública pelo código da etiqueta: devolve só a etiqueta e o destino atual."""
    linha = session.execute(
        select(Peca, Veiculo.chassi, Empresa.cnpj)
        .join(Veiculo, Veiculo.id == Peca.veiculo_id)
        .join(Empresa, Empresa.id == Veiculo.empresa_id)
        .where(Peca.codigo_rastreio == codigo.strip().upper())
    ).first()
    if linha is None:
        raise NaoEncontrado("Peça")
    peca, chassi, cnpj = linha
    etiqueta = _etiqueta(peca, chassi, cnpj)
    if etiqueta is None:
        raise NaoEncontrado("Peça")
    return RastreioSaida(**etiqueta.model_dump(), destino=peca.destino)
