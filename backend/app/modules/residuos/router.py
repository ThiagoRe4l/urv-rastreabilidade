"""Rotas de pesagens e DMR (seção "Fluxo do veículo" de docs/03-contrato-api.md).

Dono: backend-fluxo (agente 01). O router já está registrado em app/main.py.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.erros import Erro
from app.core.integracoes import EmissorMTR, obter_emissor_mtr
from app.core.paginacao import Pagina
from app.core.relogio import agora, data_operacao
from app.models import Usuario
from app.modules.residuos import service
from app.modules.residuos.schemas import DmrCriar, DmrSaida, PesagemCriar, PesagemSaida, PesagensSaida
from app.modules.veiculos import service as veiculos
from app.modules.veiculos.papeis import escreve_fluxo, le_dossie, le_fluxo

router = APIRouter(tags=["residuos"])

_erros = {404: {"model": Erro}, 409: {"model": Erro}, 422: {"model": Erro}}


@router.post(
    "/veiculos/{veiculo_id}/pesagens",
    response_model=PesagemSaida,
    status_code=status.HTTP_201_CREATED,
    responses=_erros,
)
def registrar_pesagem(
    veiculo_id: uuid.UUID,
    dados: PesagemCriar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
) -> PesagemSaida:
    pesagem = service.registrar_pesagem(session, usuario, veiculo_id, dados)  # RF-11
    session.commit()
    return PesagemSaida.model_validate(pesagem)


@router.get("/veiculos/{veiculo_id}/pesagens", response_model=PesagensSaida, responses=_erros)
def listar_pesagens(
    veiculo_id: uuid.UUID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_fluxo),
    momento: datetime = Depends(agora),
) -> PesagensSaida:
    veiculo = veiculos.obter_veiculo(session, usuario, veiculo_id)
    pesagens = service.pesagens_do_veiculo(session, veiculo.id)
    percentual = service.percentual_aproveitado(pesagens, veiculo.peso_entrada_kg)  # RF-12, art. 18 §5º
    meta = service.meta_do_ano(data_operacao(momento).year)  # RF-12, art. 18 §7º; PM-URV-06
    return PesagensSaida(
        itens=[PesagemSaida.model_validate(p) for p in pesagens],
        total=len(pesagens),
        peso_total_kg=service.peso_pesado(pesagens),
        peso_entrada_kg=veiculo.peso_entrada_kg,
        peso_nao_contabilizado_kg=service.peso_nao_contabilizado(pesagens, veiculo.peso_entrada_kg),
        percentual_aproveitado=percentual,
        meta_ano=meta,
        atende_meta=service.atende_meta(percentual, meta),
    )


@router.post(
    "/veiculos/{veiculo_id}/dmrs",
    response_model=DmrSaida,
    status_code=status.HTTP_201_CREATED,
    responses=_erros,
)
def emitir_dmr(
    veiculo_id: uuid.UUID,
    dados: DmrCriar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
    emissor: EmissorMTR = Depends(obter_emissor_mtr),
) -> DmrSaida:
    dmr = service.emitir_dmr(session, usuario, veiculo_id, dados, emissor)  # RF-13
    session.commit()
    return DmrSaida.model_validate(dmr)


@router.get("/veiculos/{veiculo_id}/dmrs", response_model=Pagina[DmrSaida], responses=_erros)
def listar_dmrs(
    veiculo_id: uuid.UUID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_dossie),
) -> Pagina[DmrSaida]:
    veiculo = veiculos.obter_veiculo(session, usuario, veiculo_id)
    dmrs = service.dmrs_do_veiculo(session, veiculo.id)
    return Pagina[DmrSaida](itens=[DmrSaida.model_validate(d) for d in dmrs], total=len(dmrs))
