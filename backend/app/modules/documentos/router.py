"""Rotas de laudo e certificado (seção "Fluxo do veículo" de docs/03-contrato-api.md).

Dono: backend-fluxo (agente 01). O router já está registrado em app/main.py.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.erros import Erro
from app.core.integracoes import AssinadorDigital, obter_assinador_digital
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.models import Usuario
from app.modules.documentos import service
from app.modules.documentos.schemas import CertificadoDetalhe, CertificadoSaida, LaudoCriar, LaudoSaida
from app.modules.veiculos.papeis import escreve_fluxo, le_fluxo

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
) -> CertificadoSaida:
    certificado, _ = service.emitir_certificado(session, usuario, veiculo_id)  # RF-15 e RF-16
    session.commit()
    return service.certificados_para_saida(session, [certificado])[0]


@router.get("/certificados", response_model=Pagina[CertificadoSaida])
def listar_certificados(
    empresa_id: uuid.UUID | None = Query(None),
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_fluxo),
) -> Pagina[CertificadoSaida]:
    itens, total = paginar(session, service.consulta_certificados(usuario, empresa_id), pag)
    return Pagina[CertificadoSaida](itens=service.certificados_para_saida(session, itens), total=total)


@router.get("/certificados/{certificado_id}", response_model=CertificadoDetalhe, responses=_erros)
def detalhar_certificado(
    certificado_id: uuid.UUID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_fluxo),
) -> CertificadoDetalhe:
    certificado = service.obter_certificado(session, usuario, certificado_id)
    return service.certificado_detalhe(session, certificado)
