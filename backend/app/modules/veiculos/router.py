"""Rotas de veículos, etapas e anexos (seção "Fluxo do veículo" de docs/03-contrato-api.md).

Dono: backend-fluxo (agente 01). O router já está registrado em app/main.py.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import obter_sessao
from app.core.erros import Erro
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.core.relogio import agora, data_operacao
from app.models import AnexoTipo, EstadoVeiculo, EtapaTipo, Usuario
from app.modules.documentos import service as documentos
from app.modules.residuos import service as residuos
from app.modules.veiculos import service
from app.modules.veiculos.papeis import escreve_fluxo, le_fluxo
from app.modules.veiculos.schemas import (
    AnexoSaida,
    EtapaEntrada,
    EtapaSaida,
    VeiculoCriar,
    VeiculoDetalhe,
    VeiculoSaida,
)

router = APIRouter(tags=["veiculos"])

_erros = {404: {"model": Erro}, 409: {"model": Erro}, 422: {"model": Erro}}


@router.post("/veiculos", response_model=VeiculoSaida, status_code=status.HTTP_201_CREATED, responses=_erros)
def receber_veiculo(
    dados: VeiculoCriar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
) -> VeiculoSaida:
    veiculo = service.criar_veiculo(session, usuario, dados)  # RF-06 e RF-07
    session.commit()
    return VeiculoSaida.model_validate(veiculo)


@router.get("/veiculos", response_model=Pagina[VeiculoSaida])
def listar_veiculos(
    estado: EstadoVeiculo | None = Query(None),
    chassi: str | None = Query(None, description="Trecho do chassi"),
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_fluxo),
) -> Pagina[VeiculoSaida]:
    itens, total = paginar(session, service.consulta_veiculos(usuario, estado, chassi), pag)
    return Pagina[VeiculoSaida](itens=[VeiculoSaida.model_validate(v) for v in itens], total=total)


@router.get("/veiculos/{veiculo_id}", response_model=VeiculoDetalhe, responses=_erros)
def detalhar_veiculo(
    veiculo_id: uuid.UUID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_fluxo),
    momento: datetime = Depends(agora),
) -> VeiculoDetalhe:
    veiculo = service.obter_veiculo(session, usuario, veiculo_id)
    laudo = documentos.obter_laudo(session, veiculo.id)
    certificado = documentos.obter_certificado_do_veiculo(session, veiculo.id)
    return VeiculoDetalhe(
        **VeiculoSaida.model_validate(veiculo).model_dump(exclude={"rebaixado"}),
        etapas=[EtapaSaida.model_validate(e) for e in sorted(veiculo.etapas, key=lambda e: e.iniciada_em)],
        anexos=[AnexoSaida.model_validate(a) for a in sorted(veiculo.anexos, key=lambda a: a.criado_em)],
        pendencias_certificado=documentos.pendencias_certificado(  # RF-15; PM-URV-06
            session, veiculo, data_operacao(momento)
        ),
        percentual_aproveitado=residuos.percentual_aproveitado(  # RF-12
            residuos.pesagens_do_veiculo(session, veiculo.id)
        ),
        laudo_id=laudo.id if laudo else None,
        certificado_id=certificado.id if certificado else None,
    )


@router.put("/veiculos/{veiculo_id}/etapas/{tipo}", response_model=EtapaSaida, responses=_erros)
def registrar_etapa(
    veiculo_id: uuid.UUID,
    tipo: EtapaTipo,
    dados: EtapaEntrada,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
) -> EtapaSaida:
    etapa = service.registrar_etapa(session, usuario, veiculo_id, tipo, dados)  # RF-08
    session.commit()
    return EtapaSaida.model_validate(etapa)


@router.post(
    "/veiculos/{veiculo_id}/anexos",
    response_model=AnexoSaida,
    status_code=status.HTTP_201_CREATED,
    responses={**_erros, 413: {"model": Erro}, 415: {"model": Erro}},
)
def enviar_anexo(
    veiculo_id: uuid.UUID,
    arquivo: UploadFile = File(..., description="Imagem (JPEG, PNG, WebP) ou PDF, até 10 MB"),
    tipo: AnexoTipo = Form(...),
    etapa_tipo: EtapaTipo | None = Form(
        None, description="Obrigatório para FOTO; padrão RECEPCAO nos demais"
    ),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(escreve_fluxo),
) -> AnexoSaida:
    # Lê um byte além do limite: basta para saber que passou, sem carregar o arquivo inteiro.
    conteudo = arquivo.file.read(get_settings().upload_limite_bytes + 1)
    anexo = service.anexar(  # RF-07 e RF-08
        session,
        usuario,
        veiculo_id,
        tipo=tipo,
        etapa_tipo=etapa_tipo,
        conteudo=conteudo,
        nome_original=arquivo.filename,
    )
    try:
        session.commit()
    except Exception:
        service.remover_arquivo(anexo)
        raise
    return AnexoSaida.model_validate(anexo)


@router.get(
    "/anexos/{anexo_id}/arquivo",
    response_class=FileResponse,
    responses={404: {"model": Erro}},
)
def baixar_anexo(
    anexo_id: uuid.UUID,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(le_fluxo),
) -> FileResponse:
    anexo = service.obter_anexo(session, usuario, anexo_id)
    return FileResponse(
        service.caminho_do_anexo(anexo),
        media_type=anexo.content_type,
        filename=anexo.nome_original or f"anexo-{anexo.id}",
        headers={"X-Content-Type-Options": "nosniff"},
    )
