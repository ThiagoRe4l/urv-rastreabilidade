"""Recepção, classificação, etapas e anexos do veículo em fim de vida. RF-06 a RF-08.

Services não fazem commit; a rota faz (ver app/core/db.py). Toda validação vem antes da
primeira escrita, para um erro de negócio nunca deixar escrita pela metade na sessão.
"""

import hashlib
import uuid
from pathlib import Path, PurePosixPath

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import filtrar_por_empresa, garantir_acesso_empresa
from app.core.erros import ErroNegocio, NaoEncontrado
from app.models import (
    Anexo,
    AnexoTipo,
    Dmr,
    EstadoVeiculo,
    Etapa,
    EtapaTipo,
    TipoVeiculo,
    Usuario,
    Veiculo,
)
from app.modules.auditoria.service import registrar_evento
from app.modules.veiculos.schemas import EtapaEntrada, VeiculoCriar, normalizar_chassi

ESTADOS_COM_CERTIFICADO = (EstadoVeiculo.CERTIFICADO, EstadoVeiculo.ENCERRADO)

# Assinaturas dos tipos de arquivo aceitos (docs/02-arquitetura.md, Segurança): imagem e PDF.
_IMAGENS = {"image/jpeg", "image/png", "image/webp"}


# --- Consultas e apoio para os outros módulos do fluxo -----------------------------------------


def consulta_veiculos(usuario: Usuario, estado: EstadoVeiculo | None, chassi: str | None) -> Select:
    stmt = filtrar_por_empresa(select(Veiculo), Veiculo.empresa_id, usuario)
    if estado is not None:
        stmt = stmt.where(Veiculo.estado == estado)
    if chassi:
        stmt = stmt.where(Veiculo.chassi.contains(normalizar_chassi(chassi), autoescape=True))
    return stmt.order_by(Veiculo.criado_em.desc(), Veiculo.id)


def obter_veiculo(
    session: Session, usuario: Usuario, veiculo_id: uuid.UUID, *, bloquear: bool = False
) -> Veiculo:
    """Veículo visível ao usuário; 404 se for de outra empresa (não revela que existe).

    `bloquear=True` trava a linha até o fim da transação: use em toda escrita, para duas
    requisições simultâneas não emitirem dois laudos ou dois certificados.
    """
    stmt = select(Veiculo).where(Veiculo.id == veiculo_id)
    if bloquear:
        stmt = stmt.with_for_update()
    veiculo = session.scalar(stmt)
    if veiculo is None:
        raise NaoEncontrado("Veículo")
    garantir_acesso_empresa(usuario, veiculo.empresa_id, "Veículo")
    return veiculo


def tem_certificado(veiculo: Veiculo) -> bool:
    return veiculo.estado in ESTADOS_COM_CERTIFICADO


def exigir_sem_certificado(veiculo: Veiculo) -> None:
    """Depois do certificado, o que ele atesta não muda (RF-15, RNF-07)."""
    if tem_certificado(veiculo):
        raise ErroNegocio(
            409,
            "VEICULO_CERTIFICADO",
            "O certificado já foi emitido; este registro não pode mais ser alterado.",
        )


def marcar_em_processo(veiculo: Veiculo) -> None:
    if veiculo.estado == EstadoVeiculo.RECEBIDO:
        veiculo.estado = EstadoVeiculo.EM_PROCESSO


def encerrar_se_destinado(session: Session, usuario: Usuario, veiculo: Veiculo) -> None:
    """CERTIFICADO → ENCERRADO quando a DESTINACAO está concluída e há ao menos uma DMR."""
    if veiculo.estado != EstadoVeiculo.CERTIFICADO:
        return
    session.flush()
    concluida = session.scalar(
        select(Etapa.id).where(
            Etapa.veiculo_id == veiculo.id,
            Etapa.tipo == EtapaTipo.DESTINACAO,
            Etapa.concluida_em.is_not(None),
        )
    )
    dmrs = session.scalar(select(func.count()).select_from(Dmr).where(Dmr.veiculo_id == veiculo.id))
    if concluida and dmrs:
        veiculo.estado = EstadoVeiculo.ENCERRADO
        session.flush()
        registrar_evento(session, usuario, "VEICULO_ENCERRADO", "veiculo", veiculo.id, {"dmrs": dmrs})


# --- Recepção ----------------------------------------------------------------------------------


def criar_veiculo(session: Session, usuario: Usuario, dados: VeiculoCriar) -> Veiculo:
    """RF-06, art. 6º I; art. 18 III."""
    # RF-21, arts. 28 e 29: um chassi em fim de vida entra uma única vez.
    if session.scalar(select(Veiculo.id).where(Veiculo.chassi == dados.chassi)):
        raise ErroNegocio(409, "CHASSI_DUPLICADO", "Já existe veículo registrado com este chassi.")

    veiculo = Veiculo(
        empresa_id=usuario.empresa_id,
        chassi=dados.chassi,
        placa=dados.placa,
        renavam=dados.renavam,
        data_entrada=dados.data_entrada,
        tipo_declarado=dados.tipo,
        # RF-07, art. 2º §5º; art. 6º I c: na recepção ainda não há evidência de classificação,
        # então o tipo efetivo é sucata inservível até o anexo EVIDENCIA_CLASSIFICACAO chegar.
        tipo=TipoVeiculo.SUCATA_INSERVIVEL,
        origem_aquisicao=dados.origem_aquisicao,
        documento_entrada_tipo=dados.documento_entrada_tipo,
        documento_entrada_numero=dados.documento_entrada_numero,
        certidao_baixa_numero=dados.certidao_baixa_numero,
        peso_entrada_kg=dados.peso_entrada_kg,
        sem_viabilidade_desmontagem=dados.sem_viabilidade_desmontagem,
        estado=EstadoVeiculo.RECEBIDO,
    )
    session.add(veiculo)
    session.flush()
    registrar_evento(
        session,
        usuario,
        "VEICULO_RECEBIDO",
        "veiculo",
        veiculo.id,
        {
            "chassi": veiculo.chassi,
            "placa": veiculo.placa,
            "renavam": veiculo.renavam,
            "data_entrada": veiculo.data_entrada,
            "tipo_declarado": veiculo.tipo_declarado,
            "tipo": veiculo.tipo,
            "origem_aquisicao": veiculo.origem_aquisicao,
            "documento_entrada_tipo": veiculo.documento_entrada_tipo,
            "documento_entrada_numero": veiculo.documento_entrada_numero,
            "certidao_baixa_numero": veiculo.certidao_baixa_numero,
            "peso_entrada_kg": veiculo.peso_entrada_kg,
            "sem_viabilidade_desmontagem": veiculo.sem_viabilidade_desmontagem,
        },
    )
    return veiculo


# --- Etapas ------------------------------------------------------------------------------------


def registrar_etapa(
    session: Session, usuario: Usuario, veiculo_id: uuid.UUID, tipo: EtapaTipo, dados: EtapaEntrada
) -> Etapa:
    """Cria ou atualiza a etapa. RF-08, art. 18 III a IX.

    Sem ordem obrigatória entre etapas: a descontaminação pode ser anterior à recepção
    (art. 18 IV) e a desmontagem é dispensável (Anexo III, item 11).
    """
    veiculo = obter_veiculo(session, usuario, veiculo_id, bloquear=True)
    # A destinação pode ser registrada depois do certificado: é ela que encerra o veículo.
    if tipo != EtapaTipo.DESTINACAO:
        exigir_sem_certificado(veiculo)

    etapa = session.scalar(select(Etapa).where(Etapa.veiculo_id == veiculo.id, Etapa.tipo == tipo))
    nova = etapa is None
    if etapa is None:
        etapa = Etapa(veiculo=veiculo, tipo=tipo)
        session.add(etapa)
    etapa.iniciada_em = dados.iniciada_em
    etapa.concluida_em = dados.concluida_em
    etapa.observacoes = dados.observacoes
    if tipo != EtapaTipo.RECEPCAO:
        marcar_em_processo(veiculo)
    session.flush()
    registrar_evento(
        session,
        usuario,
        "ETAPA_REGISTRADA" if nova else "ETAPA_ATUALIZADA",
        "etapa",
        etapa.id,
        {
            "veiculo_id": veiculo.id,
            "tipo": tipo,
            "iniciada_em": etapa.iniciada_em,
            "concluida_em": etapa.concluida_em,
            "observacoes": etapa.observacoes,
        },
    )
    encerrar_se_destinado(session, usuario, veiculo)
    return etapa


# --- Anexos ------------------------------------------------------------------------------------


def detectar_tipo_arquivo(conteudo: bytes) -> tuple[str, str] | None:
    """(content_type, extensão) pelos primeiros bytes; o tipo declarado pelo cliente não é confiável."""
    if conteudo.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if conteudo.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    return None


def _raiz_uploads() -> Path:
    return Path(get_settings().upload_dir).resolve()


def caminho_do_anexo(anexo: Anexo) -> Path:
    """Caminho absoluto do arquivo, garantidamente dentro da pasta de uploads."""
    raiz = _raiz_uploads()
    caminho = (raiz / anexo.caminho).resolve()
    if not caminho.is_relative_to(raiz) or not caminho.is_file():
        raise NaoEncontrado("Arquivo")
    return caminho


def remover_arquivo(anexo: Anexo) -> None:
    """Desfaz a gravação em disco quando a transação do anexo não se confirma."""
    (_raiz_uploads() / anexo.caminho).unlink(missing_ok=True)


def anexar(
    session: Session,
    usuario: Usuario,
    veiculo_id: uuid.UUID,
    *,
    tipo: AnexoTipo,
    etapa_tipo: EtapaTipo | None,
    conteudo: bytes,
    nome_original: str | None,
) -> Anexo:
    """Grava o arquivo no volume local com nome gerado e `sha256`. RF-08, art. 6º III c; art. 18 §1º."""
    veiculo = obter_veiculo(session, usuario, veiculo_id, bloquear=True)

    limite = get_settings().upload_limite_bytes
    if len(conteudo) > limite:
        raise ErroNegocio(413, "ARQUIVO_GRANDE_DEMAIS", f"O arquivo passa do limite de {limite} bytes.")
    if not conteudo:
        raise ErroNegocio(422, "ARQUIVO_VAZIO", "O arquivo enviado está vazio.")
    detectado = detectar_tipo_arquivo(conteudo)
    if detectado is None:
        raise ErroNegocio(415, "TIPO_DE_ARQUIVO_NAO_PERMITIDO", "Envie imagem (JPEG, PNG, WebP) ou PDF.")
    content_type, extensao = detectado
    if tipo == AnexoTipo.FOTO:
        if content_type not in _IMAGENS:
            raise ErroNegocio(415, "TIPO_DE_ARQUIVO_NAO_PERMITIDO", "Foto precisa ser imagem.")
        if etapa_tipo is None:
            raise ErroNegocio(422, "ETAPA_OBRIGATORIA", "Informe etapa_tipo: a foto é de qual etapa?")
    elif etapa_tipo is None:
        etapa_tipo = EtapaTipo.RECEPCAO  # documentos e evidência de classificação são da recepção

    # RF-07: a evidência aplica o tipo declarado. Depois do certificado, o tipo não muda.
    aplica_tipo = tipo == AnexoTipo.EVIDENCIA_CLASSIFICACAO and veiculo.tipo != veiculo.tipo_declarado
    if aplica_tipo and tem_certificado(veiculo):
        raise ErroNegocio(
            409,
            "TIPO_IMUTAVEL_APOS_CERTIFICADO",
            "O certificado já foi emitido com o tipo atual; a classificação não pode mais mudar.",
        )

    relativo = PurePosixPath(str(veiculo.id)) / f"{uuid.uuid4().hex}{extensao}"
    destino = _raiz_uploads() / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)

    anexo = Anexo(
        veiculo=veiculo,
        etapa_tipo=etapa_tipo,
        tipo=tipo,
        caminho=str(relativo),
        sha256=hashlib.sha256(conteudo).hexdigest(),
        nome_original=(Path(nome_original).name[:255] or None) if nome_original else None,
        content_type=content_type,
        tamanho_bytes=len(conteudo),
        enviado_por=usuario.id,
    )
    try:
        session.add(anexo)
        session.flush()
        registrar_evento(
            session,
            usuario,
            "ANEXO_ENVIADO",
            "anexo",
            anexo.id,
            {
                "veiculo_id": veiculo.id,
                "tipo": tipo,
                "etapa_tipo": etapa_tipo,
                "sha256": anexo.sha256,
                "tamanho_bytes": anexo.tamanho_bytes,
            },
        )
        if aplica_tipo:
            antes = veiculo.tipo
            veiculo.tipo = veiculo.tipo_declarado
            session.flush()
            registrar_evento(
                session,
                usuario,
                "VEICULO_CLASSIFICADO",
                "veiculo",
                veiculo.id,
                {"tipo": {"antes": antes, "depois": veiculo.tipo}, "evidencia_anexo_id": anexo.id},
            )
    except Exception:
        destino.unlink(missing_ok=True)
        raise
    return anexo


def obter_anexo(session: Session, usuario: Usuario, anexo_id: uuid.UUID) -> Anexo:
    anexo = session.get(Anexo, anexo_id)
    if anexo is None:
        raise NaoEncontrado("Anexo")
    garantir_acesso_empresa(usuario, anexo.veiculo.empresa_id, "Anexo")
    return anexo
