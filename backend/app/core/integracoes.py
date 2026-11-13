"""Integrações externas atrás de interfaces, com implementação falsa.

Nenhum serviço externo é chamado no MVP. Para trocar por uma implementação real,
crie a classe que satisfaz o Protocol e devolva-a na função `obter_*`.

Nas rotas, receba a integração por dependência, para os testes poderem trocá-la:

    def emitir(..., emissor: EmissorMTR = Depends(obter_emissor_mtr)): ...

    app.dependency_overrides[obter_emissor_mtr] = lambda: MeuEmissorDeTeste()
"""

import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from app.core.cnpj import cnpj_valido
from app.core.config import get_settings

# --- Renavam (art. 2º I; art. 6º I) ----------------------------------------------------------


@dataclass(frozen=True)
class SituacaoRenavam:
    renavam: str
    chassi: str
    encontrado: bool
    baixado: bool  # registro baixado (art. 18 II)
    licenciamento_regular: bool  # IPVA e licenciamento quitados (art. 2º I)
    mensagem: str


class ConsultaRenavam(Protocol):
    def consultar(self, renavam: str, chassi: str) -> SituacaoRenavam: ...


class ConsultaRenavamFalsa:
    """Simulação determinística.

    - Renavam que não tem 11 dígitos, ou começa com "000": não encontrado.
    - Renavam terminado em "9": encontrado, mas sem licenciamento regular.
    - Demais: encontrado, baixado e com licenciamento regular.
    """

    def consultar(self, renavam: str, chassi: str) -> SituacaoRenavam:
        if not re.fullmatch(r"\d{11}", renavam or "") or renavam.startswith("000"):
            return SituacaoRenavam(renavam, chassi, False, False, False, "Renavam não encontrado (simulado).")
        regular = not renavam.endswith("9")
        msg = "Registro baixado (simulado)." if regular else "Licenciamento em atraso (simulado)."
        return SituacaoRenavam(renavam, chassi, True, True, regular, msg)


# --- Nota fiscal de entrada (art. 6º I a) ----------------------------------------------------


@dataclass(frozen=True)
class ResultadoNotaFiscal:
    valida: bool
    motivo: str | None = None


class ValidadorNotaFiscal(Protocol):
    def validar(self, numero: str, cnpj_destinatario: str) -> ResultadoNotaFiscal: ...


class ValidadorNotaFiscalFalso:
    """Válida se o número não for vazio, não começar com "INVALIDA" e o CNPJ for válido."""

    def validar(self, numero: str, cnpj_destinatario: str) -> ResultadoNotaFiscal:
        if not numero or not numero.strip():
            return ResultadoNotaFiscal(False, "Número da nota fiscal ausente.")
        if numero.upper().startswith("INVALIDA"):
            return ResultadoNotaFiscal(False, "Nota fiscal não localizada (simulado).")
        if not cnpj_valido(cnpj_destinatario):
            return ResultadoNotaFiscal(False, "CNPJ do destinatário inválido.")
        return ResultadoNotaFiscal(True)


# --- MTR do SINIR (Anexo II item 30; Anexo III item 13) --------------------------------------


@dataclass(frozen=True)
class Mtr:
    numero: str
    emitido_em: datetime


class EmissorMTR(Protocol):
    def emitir(
        self, *, gerador_cnpj: str, destinatario_cnpj: str, tipo_material: str, peso_kg: Decimal
    ) -> Mtr: ...


class EmissorMTRFalso:
    """Devolve um número de MTR único com prefixo "MTR-SIM-", deixando claro que é simulado."""

    def emitir(
        self, *, gerador_cnpj: str, destinatario_cnpj: str, tipo_material: str, peso_kg: Decimal
    ) -> Mtr:
        agora = datetime.now(UTC)
        return Mtr(numero=f"MTR-SIM-{agora:%Y%m%d}-{uuid.uuid4().hex[:10].upper()}", emitido_em=agora)


# --- Assinatura digital do responsável técnico (art. 18 VII) ---------------------------------


@dataclass(frozen=True)
class Assinatura:
    algoritmo: str
    valor: str
    signatario: str
    assinado_em: datetime


class AssinadorDigital(Protocol):
    def assinar(self, conteudo: bytes, signatario: str) -> Assinatura: ...

    def verificar(self, conteudo: bytes, assinatura: Assinatura) -> bool: ...


class AssinadorDigitalFalso:
    """HMAC-SHA256 com chave do servidor. Prova integridade, não identidade: não é ICP-Brasil."""

    ALGORITMO = "SIMULADA-HMAC-SHA256"

    def _mac(self, conteudo: bytes, signatario: str, assinado_em: datetime) -> str:
        chave = get_settings().assinatura_segredo.encode("utf-8")
        mensagem = (
            signatario.encode("utf-8") + b"|" + assinado_em.isoformat().encode("ascii") + b"|" + conteudo
        )
        return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()

    def assinar(self, conteudo: bytes, signatario: str) -> Assinatura:
        agora = datetime.now(UTC)
        return Assinatura(self.ALGORITMO, self._mac(conteudo, signatario, agora), signatario, agora)

    def verificar(self, conteudo: bytes, assinatura: Assinatura) -> bool:
        if assinatura.algoritmo != self.ALGORITMO:
            return False
        esperado = self._mac(conteudo, assinatura.signatario, assinatura.assinado_em)
        return hmac.compare_digest(esperado, assinatura.valor)


# --- Pontos de troca (dependências FastAPI) --------------------------------------------------

_renavam = ConsultaRenavamFalsa()
_nota_fiscal = ValidadorNotaFiscalFalso()
_mtr = EmissorMTRFalso()
_assinador = AssinadorDigitalFalso()


def obter_consulta_renavam() -> ConsultaRenavam:
    return _renavam


def obter_validador_nota_fiscal() -> ValidadorNotaFiscal:
    return _nota_fiscal


def obter_emissor_mtr() -> EmissorMTR:
    return _mtr


def obter_assinador_digital() -> AssinadorDigital:
    return _assinador
