"""Papéis do fluxo do veículo (docs/03-contrato-api.md).

DESMONTADORA e RECICLADORA escrevem nos próprios veículos; AUDITOR e ADMIN leem tudo.
FABRICANTE não participa do fluxo, mas lê o dossiê (certificado, laudo, anexos e DMRs) do veículo
que gerou um crédito de que é titular: guarda e apresenta essa documentação (art. 9º; art. 10;
achado A8 da revisão). `le_dossie` é só para essas rotas de leitura.
"""

from app.core.deps import exige_papel
from app.models import Papel

escreve_fluxo = exige_papel(Papel.DESMONTADORA, Papel.RECICLADORA)
le_fluxo = exige_papel(Papel.DESMONTADORA, Papel.RECICLADORA, Papel.ADMIN, Papel.AUDITOR)
le_dossie = exige_papel(Papel.DESMONTADORA, Papel.RECICLADORA, Papel.ADMIN, Papel.AUDITOR, Papel.FABRICANTE)
