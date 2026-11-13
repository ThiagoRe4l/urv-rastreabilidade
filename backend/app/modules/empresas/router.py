"""Rotas de empresas e vínculos (seção "Fundação" de docs/03-contrato-api.md)."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import obter_sessao
from app.core.deps import exige_papel, usuario_atual
from app.core.erros import Erro
from app.core.paginacao import Pagina, Paginacao, paginacao, paginar
from app.models import Papel, TipoEmpresa, Usuario
from app.modules.empresas import service
from app.modules.empresas.schemas import (
    CredenciamentoAtualizar,
    EmpresaAtualizar,
    EmpresaCriar,
    EmpresaSaida,
    VinculoAtualizar,
    VinculoCriar,
    VinculoSaida,
)

router = APIRouter(tags=["empresas"])

_admin = exige_papel(Papel.ADMIN)
_erros = {404: {"model": Erro}, 409: {"model": Erro}, 422: {"model": Erro}}


@router.post("/empresas", response_model=EmpresaSaida, status_code=status.HTTP_201_CREATED, responses=_erros)
def criar_empresa(
    dados: EmpresaCriar, session: Session = Depends(obter_sessao), usuario: Usuario = Depends(_admin)
) -> EmpresaSaida:
    empresa = service.criar_empresa(session, usuario, dados)  # RF-01
    session.commit()
    return EmpresaSaida.model_validate(empresa)


@router.get("/empresas", response_model=Pagina[EmpresaSaida])
def listar_empresas(
    tipo: TipoEmpresa | None = Query(None),
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
) -> Pagina[EmpresaSaida]:
    itens, total = paginar(session, service.consulta_empresas(session, usuario, tipo), pag)
    return Pagina[EmpresaSaida](itens=[EmpresaSaida.model_validate(e) for e in itens], total=total)


@router.patch("/empresas/{empresa_id}", response_model=EmpresaSaida, responses=_erros)
def atualizar_empresa(
    empresa_id: uuid.UUID,
    dados: EmpresaAtualizar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_admin),
) -> EmpresaSaida:
    empresa = service.atualizar_registro_compromissos(  # art. 8º II
        session, usuario, empresa_id, dados.registro_compromissos
    )
    session.commit()
    return EmpresaSaida.model_validate(empresa)


@router.patch("/empresas/{empresa_id}/credenciamento", response_model=EmpresaSaida, responses=_erros)
def alterar_credenciamento(
    empresa_id: uuid.UUID,
    dados: CredenciamentoAtualizar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_admin),
) -> EmpresaSaida:
    empresa = service.alterar_credenciamento(session, usuario, empresa_id, dados)  # RF-01, art. 16
    session.commit()
    return EmpresaSaida.model_validate(empresa)


@router.post("/vinculos", response_model=VinculoSaida, status_code=status.HTTP_201_CREATED, responses=_erros)
def criar_vinculo(
    dados: VinculoCriar, session: Session = Depends(obter_sessao), usuario: Usuario = Depends(_admin)
) -> VinculoSaida:
    vinculo = service.criar_vinculo(session, usuario, dados.geradora_id, dados.fabricante_id)  # RF-02
    session.commit()
    return VinculoSaida.model_validate(vinculo)


@router.get("/vinculos", response_model=Pagina[VinculoSaida])
def listar_vinculos(
    pag: Paginacao = Depends(paginacao),
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
) -> Pagina[VinculoSaida]:
    itens, total = paginar(session, service.consulta_vinculos(usuario), pag)
    return Pagina[VinculoSaida](itens=[VinculoSaida.model_validate(v) for v in itens], total=total)


@router.patch("/vinculos/{vinculo_id}", response_model=VinculoSaida, responses=_erros)
def alterar_vinculo(
    vinculo_id: uuid.UUID,
    dados: VinculoAtualizar,
    session: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(_admin),
) -> VinculoSaida:
    vinculo = service.alterar_vinculo(session, usuario, vinculo_id, dados.ativo)  # RF-02
    session.commit()
    return VinculoSaida.model_validate(vinculo)
