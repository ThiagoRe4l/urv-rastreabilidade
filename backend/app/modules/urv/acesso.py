"""Qual empresa uma consulta enxerga, conforme o papel. Usado por `urv` e `portabilidade`."""

import uuid

from app.core.deps import garantir_acesso_empresa, le_tudo
from app.core.erros import ErroNegocio
from app.models import Usuario


def empresa_consultada(
    usuario: Usuario, empresa_id: uuid.UUID | None, *, obrigatoria: bool = False
) -> uuid.UUID | None:
    """Empresa alvo da consulta.

    - Usuário de empresa: sempre a própria; pedir outra dá 404, sem revelar que existe.
    - ADMIN e AUDITOR (RF-23, art. 9º; art. 24 V): a de `?empresa_id=`; sem o parâmetro,
      `None` = todas. Com `obrigatoria`, a falta do parâmetro é erro.
    """
    if le_tudo(usuario):
        if empresa_id is None and obrigatoria:
            raise ErroNegocio(422, "EMPRESA_OBRIGATORIA", "Informe a empresa em ?empresa_id=.")
        return empresa_id
    if empresa_id is not None:
        garantir_acesso_empresa(usuario, empresa_id, "Empresa")
    return usuario.empresa_id
