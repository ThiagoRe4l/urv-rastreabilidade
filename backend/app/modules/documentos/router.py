"""Rotas de laudo e certificado (seção "Fluxo do veículo" de docs/03-contrato-api.md).

Dono: backend-fluxo (agente 01). O router já está registrado em app/main.py.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.erros import Erro, NaoEncontrado
from app.core.integracoes import AssinadorDigital, obter_assinador_digital
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.core.relogio import agora
from app.models import Usuario
from app.modules.documentos import service
from app.modules.documentos.schemas import CertificadoDetalhe, CertificadoSaida, LaudoCriar, LaudoSaida
from app.modules.veiculos import service as veiculos
from app.modules.veiculos.papeis import escreve_fluxo, le_dossie

router = APIRouter(tags=["documentos"])

_erros = {404: {"model": Erro}, 409: {"model": Erro}, 422: {"model": Erro}}


@router.post(
    "/veiculos/{veiculo_id}/laudo",
    response_model=LaudoSaida,
    status_code=status.HTTP_201_CREATED,
    responses=_erros,
)
def emitir_laudo(
    veiculo_id: uuid.UUID,
    dados: LaudoCriar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
    assinador: AssinadorDigital = Depends(obter_assinador_digital),
) -> LaudoSaida:
    laudo = service.emitir_laudo(session, usuario, veiculo_id, dados, assinador)  # RF-14
    session.commit()
    return service.laudo_para_saida(laudo)


@router.get("/veiculos/{veiculo_id}/laudo", response_model=LaudoSaida, responses=_erros)
def ler_laudo(
    veiculo_id: uuid.UUID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_dossie),
) -> LaudoSaida:
    """Laudo do veículo, antes ou depois do certificado. 404 se ainda não foi assinado (PM-WEB-03)."""
    veiculo = veiculos.obter_veiculo(session, usuario, veiculo_id)  # 404 se for de outra empresa
    laudo = service.obter_laudo(session, veiculo.id)
    if laudo is None:
        raise NaoEncontrado("Laudo")
    return service.laudo_para_saida(laudo)  # RF-14, RF-23


@router.post(
    "/veiculos/{veiculo_id}/certificado",
    response_model=CertificadoSaida,
    status_code=status.HTTP_201_CREATED,
    responses=_erros,
)
def emitir_certificado(
    veiculo_id: uuid.UUID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
    momento: datetime = Depends(agora),
) -> CertificadoSaida:
    certificado, _ = service.emitir_certificado(session, usuario, veiculo_id, agora=momento)  # RF-15, RF-16
    session.commit()
    return service.certificados_para_saida(session, [certificado])[0]


@router.get("/certificados", response_model=Pagina[CertificadoSaida])
def listar_certificados(
    empresa_id: uuid.UUID | None = Query(None),
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_dossie),
) -> Pagina[CertificadoSaida]:
    itens, total = paginar(session, service.consulta_certificados(usuario, empresa_id), pag)
    return Pagina[CertificadoSaida](itens=service.certificados_para_saida(session, itens), total=total)


@router.get("/certificados/{certificado_id}", response_model=CertificadoDetalhe, responses=_erros)
def detalhar_certificado(
    certificado_id: uuid.UUID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_dossie),
) -> CertificadoDetalhe:
    certificado = service.obter_certificado(session, usuario, certificado_id)
    return service.certificado_detalhe(session, certificado)
