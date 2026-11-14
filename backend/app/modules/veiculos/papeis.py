"""Papéis do fluxo do veículo (docs/03-contrato-api.md).

DESMONTADORA e RECICLADORA escrevem nos próprios veículos; AUDITOR e ADMIN leem tudo.
FABRICANTE não participa do fluxo: vê certificados pelos créditos, no módulo `urv`.
"""

from app.core.deps import exige_papel
from app.models import Papel

escreve_fluxo = exige_papel(Papel.DESMONTADORA, Papel.RECICLADORA)
le_fluxo = exige_papel(Papel.DESMONTADORA, Papel.RECICLADORA, Papel.ADMIN, Papel.AUDITOR)
