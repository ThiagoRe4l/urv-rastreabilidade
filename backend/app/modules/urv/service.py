"""Livro de URV. Dono: backend-urv (agente 02).

`gerar_credito` é o ponto de contato com o fluxo do veículo (docs/02-arquitetura.md):
a fundação fixa a assinatura; o agente 02 implementa; o agente 01 só chama.
"""

from sqlalchemy.orm import Session

from app.models import Certificado, UrvCredito


def gerar_credito(session: Session, certificado: Certificado) -> UrvCredito:
    """Cria o crédito do certificado e o lançamento CREDITO da geradora, sem commit.

    RF-16, art. 3º §§1º e 2º; art. 18 §3º; art. 8º I.

    - `quantidade` = `certificado.fator` (crédito indivisível, um por certificado).
    - `geradora_id` = `titular_id` = `certificado.empresa_id`; status DISPONIVEL.
    - Um `UrvLancamento` tipo CREDITO, quantidade positiva, `credito_id` preenchido.
    - Registra evento de auditoria na mesma transação.
    - Rejeita certificado que já tem crédito.
    """
    raise NotImplementedError("gerar_credito é implementado pelo agente 02 (backend-urv).")
