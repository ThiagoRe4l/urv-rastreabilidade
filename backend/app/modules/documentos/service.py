"""Laudo de Reciclagem e Certificado de Reciclagem Veicular. RF-14 e RF-15.

Services não fazem commit; a rota faz (ver app/core/db.py).
"""

import hashlib
import json
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.configuracao import fator_vigente
from app.core.deps import filtrar_por_empresa, garantir_acesso_empresa
from app.core.erros import ErroNegocio, NaoEncontrado
from app.core.integracoes import AssinadorDigital
from app.models import (
    AnexoTipo,
    Certificado,
    Empresa,
    EstadoVeiculo,
    EtapaTipo,
    Laudo,
    Peca,
    PecaClassificacao,
    UrvCredito,
    Usuario,
    Veiculo,
)
from app.modules.auditoria.service import json_canonico, normalizar, registrar_evento
from app.modules.documentos.schemas import (
    AssinaturaSaida,
    CertificadoDetalhe,
    CertificadoSaida,
    CreditoResumo,
    LaudoCriar,
    LaudoSaida,
)
from app.modules.empresas.service import credenciamento_vigente
from app.modules.residuos import service as residuos
from app.modules.urv import service as urv_service
from app.modules.veiculos import service as veiculos
from app.modules.veiculos.schemas import VeiculoSaida

# Textos das pendências (docs/02-arquitetura.md, "Pré-condições do certificado"). O número
# entre parênteses é o da pré-condição.
P_CREDENCIAMENTO = "Empresa sem credenciamento ativo e dentro da validade (1)"
P_RECEPCAO = "Etapa RECEPCAO não concluída (2)"
P_DOCUMENTO_ENTRADA = "Falta anexo DOCUMENTO_ENTRADA (2)"
P_CERTIDAO_BAIXA = "Falta anexo CERTIDAO_BAIXA (2)"
P_FOTO_RECEPCAO = "Falta foto da etapa RECEPCAO (2)"
P_DESCONTAMINACAO = "Etapa DESCONTAMINACAO não concluída (3)"
P_FOTO_DESCONTAMINACAO = "Falta foto da etapa DESCONTAMINACAO (3)"
P_DESMONTAGEM = (
    "Etapa DESMONTAGEM não concluída e veículo não marcado como sem viabilidade de desmontagem (4)"
)
P_FOTO_DESMONTAGEM = "Falta foto da etapa DESMONTAGEM (4)"
P_PECA_SEM_RASTREIO = "Há peça reutilizável sem código de rastreio (5)"
P_PECA_NAO_DESCARACTERIZADA = "Há peça não reutilizável sem descaracterização (5)"
P_DESTRUICAO = "Etapa DESTRUICAO não concluída (6)"
P_PESAGEM = "Falta ao menos uma pesagem (6)"
P_FOTO_DESTRUICAO = "Falta foto da etapa DESTRUICAO, a separação dos materiais (6)"
P_LAUDO = "Falta o Laudo de Reciclagem assinado (7)"
P_CERTIFICADO_ANTERIOR = "O chassi já tem certificado emitido (8)"


def _hash(conteudo: dict[str, Any]) -> tuple[bytes, str]:
    dados = json_canonico(normalizar(conteudo)).encode("utf-8")
    return dados, hashlib.sha256(dados).hexdigest()


def _etapas_concluidas(veiculo: Veiculo) -> set[EtapaTipo]:
    return {e.tipo for e in veiculo.etapas if e.concluida_em is not None}


def obter_laudo(session: Session, veiculo_id: uuid.UUID) -> Laudo | None:
    return session.scalar(select(Laudo).where(Laudo.veiculo_id == veiculo_id))


def obter_certificado_do_veiculo(session: Session, veiculo_id: uuid.UUID) -> Certificado | None:
    return session.scalar(select(Certificado).where(Certificado.veiculo_id == veiculo_id))


# --- Laudo -------------------------------------------------------------------------------------


def emitir_laudo(
    session: Session, usuario: Usuario, veiculo_id: uuid.UUID, dados: LaudoCriar, assinador: AssinadorDigital
) -> Laudo:
    """RF-14, art. 18 VII; Anexo III 15.b: laudo assinado pelo responsável técnico."""
    veiculo = veiculos.obter_veiculo(session, usuario, veiculo_id, bloquear=True)
    if obter_laudo(session, veiculo.id) is not None:
        raise ErroNegocio(409, "LAUDO_JA_EMITIDO", "Este veículo já tem Laudo de Reciclagem.")

    concluidas = _etapas_concluidas(veiculo)
    pendencias = [
        texto
        for etapa, texto in (
            (EtapaTipo.DESCONTAMINACAO, P_DESCONTAMINACAO),
            (EtapaTipo.DESTRUICAO, P_DESTRUICAO),
        )
        if etapa not in concluidas
    ]
    if pendencias:
        raise ErroNegocio(
            422,
            "PENDENCIAS_LAUDO",
            "O laudo exige as etapas de descontaminação e destruição concluídas.",
            pendencias,
        )

    empresa = session.get(Empresa, veiculo.empresa_id)
    pesagens = residuos.pesagens_do_veiculo(session, veiculo.id)
    pecas = session.scalars(
        select(Peca).where(Peca.veiculo_id == veiculo.id).order_by(Peca.criado_em, Peca.id)
    )
    # O que o responsável técnico atesta: o retrato do veículo no momento da assinatura.
    conteudo, hash_conteudo = _hash(
        {
            "chassi": veiculo.chassi,
            "empresa_cnpj": empresa.cnpj,
            "tipo": veiculo.tipo,
            "sem_viabilidade_desmontagem": veiculo.sem_viabilidade_desmontagem,
            "responsavel_nome": dados.responsavel_nome,
            "responsavel_registro": dados.responsavel_registro,
            "etapas": [
                {"tipo": e.tipo, "iniciada_em": e.iniciada_em, "concluida_em": e.concluida_em}
                for e in sorted(veiculo.etapas, key=lambda e: e.tipo)
            ],
            "pesagens": [{"fracao": p.fracao, "destino": p.destino, "peso_kg": p.peso_kg} for p in pesagens],
            "percentual_aproveitado": residuos.percentual_aproveitado(pesagens),
            "pecas": [
                {
                    "nome": p.nome,
                    "classificacao": p.classificacao,
                    "codigo_rastreio": p.codigo_rastreio,
                    "destino": p.destino,
                    "descaracterizada": p.descaracterizada,
                }
                for p in pecas
            ],
        }
    )
    # Assinatura simulada atrás de AssinadorDigital (lacuna L-07: não é ICP-Brasil).
    assinatura = assinador.assinar(conteudo, f"{dados.responsavel_nome} ({dados.responsavel_registro})")

    laudo = Laudo(
        veiculo_id=veiculo.id,
        responsavel_nome=dados.responsavel_nome,
        responsavel_registro=dados.responsavel_registro,
        assinado_em=assinatura.assinado_em,
        hash_conteudo=hash_conteudo,
        assinatura=json.dumps(
            {
                "algoritmo": assinatura.algoritmo,
                "valor": assinatura.valor,
                "signatario": assinatura.signatario,
                "assinado_em": assinatura.assinado_em.isoformat(),
            }
        ),
    )
    session.add(laudo)
    if veiculo.estado in (EstadoVeiculo.RECEBIDO, EstadoVeiculo.EM_PROCESSO):
        veiculo.estado = EstadoVeiculo.LAUDO_EMITIDO
    session.flush()
    registrar_evento(
        session,
        usuario,
        "LAUDO_ASSINADO",
        "laudo",
        laudo.id,
        {
            "veiculo_id": veiculo.id,
            "chassi": veiculo.chassi,
            "responsavel_nome": laudo.responsavel_nome,
            "responsavel_registro": laudo.responsavel_registro,
            "hash_conteudo": laudo.hash_conteudo,
            "assinatura_algoritmo": assinatura.algoritmo,
        },
    )
    return laudo


def laudo_para_saida(laudo: Laudo) -> LaudoSaida:
    assinatura = None
    if laudo.assinatura:
        bruto = json.loads(laudo.assinatura)
        assinatura = AssinaturaSaida(algoritmo=bruto["algoritmo"], valor=bruto["valor"])
    return LaudoSaida(
        id=laudo.id,
        veiculo_id=laudo.veiculo_id,
        responsavel_nome=laudo.responsavel_nome,
        responsavel_registro=laudo.responsavel_registro,
        assinado_em=laudo.assinado_em,
        hash_conteudo=laudo.hash_conteudo,
        assinatura=assinatura,
    )


# --- Certificado -------------------------------------------------------------------------------


def pendencias_certificado(
    session: Session, veiculo: Veiculo, em: date, *, para_emissao: bool = False
) -> list[str]:
    """O que falta para o certificado. RF-15, art. 18 VIII; art. 8º I. Lista vazia = pode emitir.

    Devolve todas as pendências de uma vez. Com certificado já emitido não há nada a fazer:
    a lista é vazia na consulta e traz só a pré-condição 8 na tentativa de emitir de novo.
    """
    # 8. RF-21, arts. 28 e 29: um chassi gera crédito uma única vez.
    if obter_certificado_do_veiculo(session, veiculo.id) is not None:
        return [P_CERTIFICADO_ANTERIOR] if para_emissao else []

    faltas: list[str] = []
    # 1. Arts. 11 e 16; art. 8º I: só empresa credenciada gera URV.
    if not credenciamento_vigente(session.get(Empresa, veiculo.empresa_id), em):
        faltas.append(P_CREDENCIAMENTO)

    concluidas = _etapas_concluidas(veiculo)
    anexos = {a.tipo for a in veiculo.anexos}
    fotos = {a.etapa_tipo for a in veiculo.anexos if a.tipo == AnexoTipo.FOTO}

    # 2. Art. 6º I; art. 18 III; Anexo III 14.a.
    if EtapaTipo.RECEPCAO not in concluidas:
        faltas.append(P_RECEPCAO)
    if AnexoTipo.DOCUMENTO_ENTRADA not in anexos:
        faltas.append(P_DOCUMENTO_ENTRADA)
    if AnexoTipo.CERTIDAO_BAIXA not in anexos:
        faltas.append(P_CERTIDAO_BAIXA)
    if EtapaTipo.RECEPCAO not in fotos:
        faltas.append(P_FOTO_RECEPCAO)

    # 3. Art. 18 IV.
    if EtapaTipo.DESCONTAMINACAO not in concluidas:
        faltas.append(P_DESCONTAMINACAO)
    if EtapaTipo.DESCONTAMINACAO not in fotos:
        faltas.append(P_FOTO_DESCONTAMINACAO)

    # 4. Art. 18 V; Anexo III, item 11: sem viabilidade, o veículo vai direto à trituração.
    if not veiculo.sem_viabilidade_desmontagem:
        if EtapaTipo.DESMONTAGEM not in concluidas:
            faltas.append(P_DESMONTAGEM)
        if EtapaTipo.DESMONTAGEM not in fotos:
            faltas.append(P_FOTO_DESMONTAGEM)

    # 5. Anexo III, itens 6 a 8.
    pecas = session.scalars(select(Peca).where(Peca.veiculo_id == veiculo.id)).all()
    if any(p.classificacao == PecaClassificacao.REUTILIZAVEL and not p.codigo_rastreio for p in pecas):
        faltas.append(P_PECA_SEM_RASTREIO)
    if any(p.classificacao == PecaClassificacao.NAO_REUTILIZAVEL and not p.descaracterizada for p in pecas):
        faltas.append(P_PECA_NAO_DESCARACTERIZADA)

    # 6. Art. 18 VI e §6º; art. 6º III c; Anexo III 15.c.
    if EtapaTipo.DESTRUICAO not in concluidas:
        faltas.append(P_DESTRUICAO)
    if not residuos.pesagens_do_veiculo(session, veiculo.id):
        faltas.append(P_PESAGEM)
    if EtapaTipo.DESTRUICAO not in fotos:
        faltas.append(P_FOTO_DESTRUICAO)

    # 7. Art. 18 VII.
    if obter_laudo(session, veiculo.id) is None:
        faltas.append(P_LAUDO)
    return faltas


def emitir_certificado(
    session: Session, usuario: Usuario, veiculo_id: uuid.UUID, *, agora: datetime | None = None
) -> tuple[Certificado, UrvCredito]:
    """RF-15, art. 18 VIII: emite o certificado e gera o crédito de URV na mesma transação."""
    agora = agora or datetime.now(UTC)
    veiculo = veiculos.obter_veiculo(session, usuario, veiculo_id, bloquear=True)
    session.flush()

    faltas = pendencias_certificado(session, veiculo, agora.date(), para_emissao=True)
    if faltas:
        raise ErroNegocio(
            422,
            "PENDENCIAS_CERTIFICADO",
            "O certificado só é emitido com etapas e evidências completas.",
            faltas,
        )

    empresa = session.get(Empresa, veiculo.empresa_id)
    laudo = obter_laudo(session, veiculo.id)
    # RF-12, art. 18 §5º: abaixo da meta é alerta gravado no certificado, não bloqueio.
    percentual = residuos.percentual_aproveitado(residuos.pesagens_do_veiculo(session, veiculo.id))
    meta = residuos.meta_do_ano(agora.year)
    # RF-16, art. 3º §2º: o fator é o do tipo efetivo, vigente na data da emissão.
    fator = fator_vigente(session, veiculo.tipo, agora.date())
    numero = f"CRV-{agora:%Y}-{secrets.token_hex(5).upper()}"
    _, hash_conteudo = _hash(
        {
            "numero": numero,
            "chassi": veiculo.chassi,
            "empresa_cnpj": empresa.cnpj,
            "tipo_veiculo": veiculo.tipo,
            "fator": fator,
            "percentual_aproveitado": percentual,
            "meta_ano": meta,
            "emitido_em": agora,
            "laudo_hash": laudo.hash_conteudo,
        }
    )
    certificado = Certificado(
        veiculo_id=veiculo.id,
        numero=numero,
        empresa_id=veiculo.empresa_id,
        tipo_veiculo=veiculo.tipo,
        fator=fator,
        percentual_aproveitado=percentual,
        meta_ano=meta,
        atende_meta=residuos.atende_meta(percentual, meta),
        emitido_em=agora,
        hash_conteudo=hash_conteudo,
    )
    session.add(certificado)
    veiculo.estado = EstadoVeiculo.CERTIFICADO
    session.flush()
    registrar_evento(
        session,
        usuario,
        "CERTIFICADO_EMITIDO",
        "certificado",
        certificado.id,
        {
            "veiculo_id": veiculo.id,
            "chassi": veiculo.chassi,
            "numero": numero,
            "tipo_veiculo": certificado.tipo_veiculo,
            "fator": fator,
            "percentual_aproveitado": percentual,
            "meta_ano": meta,
            "atende_meta": certificado.atende_meta,
            "hash_conteudo": hash_conteudo,
        },
    )
    # RF-16, art. 18 §3º: o crédito nasce com o certificado. A lógica é do módulo `urv`.
    credito = urv_service.gerar_credito(session, certificado)
    # Se a destinação já estava concluída com DMR, o veículo encerra aqui.
    veiculos.encerrar_se_destinado(session, usuario, veiculo)
    return certificado, credito


def consulta_certificados(usuario: Usuario, empresa_id: uuid.UUID | None) -> Select:
    stmt = filtrar_por_empresa(select(Certificado), Certificado.empresa_id, usuario)
    if empresa_id is not None:
        stmt = stmt.where(Certificado.empresa_id == empresa_id)
    return stmt.order_by(Certificado.emitido_em.desc(), Certificado.id)


def obter_certificado(session: Session, usuario: Usuario, certificado_id: uuid.UUID) -> Certificado:
    certificado = session.get(Certificado, certificado_id)
    if certificado is None:
        raise NaoEncontrado("Certificado")
    garantir_acesso_empresa(usuario, certificado.empresa_id, "Certificado")
    return certificado


def _campos(certificado: Certificado, credito: UrvCredito | None) -> dict[str, Any]:
    return {
        "id": certificado.id,
        "numero": certificado.numero,
        "veiculo_id": certificado.veiculo_id,
        "chassi": certificado.veiculo.chassi,
        "empresa_id": certificado.empresa_id,
        "tipo_veiculo": certificado.tipo_veiculo,
        "fator": certificado.fator,
        "percentual_aproveitado": certificado.percentual_aproveitado,
        "meta_ano": certificado.meta_ano,
        "atende_meta": certificado.atende_meta,
        "emitido_em": certificado.emitido_em,
        "hash_conteudo": certificado.hash_conteudo,
        "credito": CreditoResumo.model_validate(credito) if credito is not None else None,
    }


def certificados_para_saida(session: Session, certificados: Sequence[Certificado]) -> list[CertificadoSaida]:
    creditos: dict[uuid.UUID, UrvCredito] = {}
    if certificados:
        creditos = {
            c.certificado_id: c
            for c in session.scalars(
                select(UrvCredito).where(UrvCredito.certificado_id.in_([c.id for c in certificados]))
            )
        }
    return [CertificadoSaida(**_campos(c, creditos.get(c.id))) for c in certificados]


def certificado_detalhe(session: Session, certificado: Certificado) -> CertificadoDetalhe:
    credito = session.scalar(select(UrvCredito).where(UrvCredito.certificado_id == certificado.id))
    laudo = obter_laudo(session, certificado.veiculo_id)
    return CertificadoDetalhe(
        **_campos(certificado, credito),
        laudo=laudo_para_saida(laudo) if laudo is not None else None,
        veiculo=VeiculoSaida.model_validate(certificado.veiculo),
    )
