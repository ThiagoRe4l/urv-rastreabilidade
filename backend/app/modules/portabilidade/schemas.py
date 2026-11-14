"""Formato de troca entre plataformas, versão 1.0. RF-25, RNF-04, art. 22.

JSON próprio e versionado (premissa de docs/01-requisitos.md). Regras do formato:

- As entidades se ligam por chaves naturais (CNPJ, chassi, número do certificado, código do
  MMV), nunca por id interno: cada plataforma gera os seus.
- Todo `Decimal` vai como string; datas com hora levam fuso.
- `hash_conteudo` é o SHA-256 do JSON canônico (chaves ordenadas, sem espaços, UTF-8) do
  documento sem o próprio campo. Serve para detectar corrupção, não substitui assinatura.
- Arquivos de evidência não trafegam: `anexos` leva só metadados e o `sha256` de cada um.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, Field

from app.models import (
    AnexoTipo,
    CredenciamentoStatus,
    DestinoPesagem,
    DocumentoEntradaTipo,
    EstadoVeiculo,
    EtapaTipo,
    Fracao,
    LancamentoTipo,
    MmvStatus,
    OrigemAquisicao,
    Papel,
    PecaClassificacao,
    PecaCondicao,
    PecaDestino,
    TipoEmpresa,
    TipoVeiculo,
    UrvCreditoStatus,
)

VERSAO_FORMATO = "1.0"
PLATAFORMA = "URV Rastreabilidade"

_CNPJ = r"^[0-9]{14}$"
_HASH = r"^[0-9a-f]{64}$"
_PERIODO = r"^[0-9]{4}-(0[1-9]|1[0-2])$"

Cnpj = Field(pattern=_CNPJ, description="Só dígitos")
Chassi = Field(min_length=1, max_length=30)
NumeroCertificado = Field(min_length=1, max_length=40)


class OrigemPortavel(BaseModel):
    plataforma: str = Field(max_length=100)
    versao: str | None = Field(None, max_length=40)


class EmpresaPortavel(BaseModel):
    cnpj: str = Cnpj
    razao_social: str = Field(max_length=200)
    tipo: TipoEmpresa
    credenciamento_status: CredenciamentoStatus | None = None
    credenciamento_validade: date | None = None
    registro_compromissos: bool = False


class UsuarioPortavel(BaseModel):
    """Cadastro de usuários (art. 22 I). Sem senha: cada plataforma cria as próprias credenciais."""

    nome: str
    email: str
    papel: Papel


class VinculoPortavel(BaseModel):
    geradora_cnpj: str = Cnpj
    fabricante_cnpj: str = Cnpj
    ativo: bool


class EtapaPortavel(BaseModel):
    tipo: EtapaTipo
    iniciada_em: AwareDatetime
    concluida_em: AwareDatetime | None = None
    observacoes: str | None = None


class AnexoPortavel(BaseModel):
    tipo: AnexoTipo
    etapa_tipo: EtapaTipo | None = None
    sha256: str = Field(pattern=_HASH)
    nome_original: str | None = None
    content_type: str | None = None
    tamanho_bytes: int | None = None
    enviado_em: AwareDatetime


class PecaPortavel(BaseModel):
    nome: str = Field(max_length=200)
    descricao: str | None = None
    classificacao: PecaClassificacao
    codigo_rastreio: str | None = Field(None, max_length=64)
    condicao: PecaCondicao | None = None
    destino: PecaDestino | None = None
    descaracterizada: bool = False
    item_seguranca: bool = False
    registrada_em: AwareDatetime


class PesagemPortavel(BaseModel):
    fracao: Fracao
    destino: DestinoPesagem
    peso_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    registrada_em: AwareDatetime


class DmrPortavel(BaseModel):
    numero: str = Field(max_length=60)
    mtr_numero: str = Field(max_length=60)
    destinatario_nome: str = Field(max_length=200)
    destinatario_cnpj: str = Cnpj
    tipo_material: str = Field(max_length=100)
    peso_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    emitida_em: AwareDatetime


class LaudoPortavel(BaseModel):
    responsavel_nome: str = Field(max_length=200)
    responsavel_registro: str = Field(max_length=60)
    assinado_em: AwareDatetime
    hash_conteudo: str = Field(pattern=_HASH)
    assinatura: str | None = None


class VeiculoPortavel(BaseModel):
    chassi: str = Chassi
    placa: str | None = Field(None, max_length=10)
    renavam: str | None = Field(None, max_length=11)
    data_entrada: date
    tipo_declarado: TipoVeiculo
    tipo: TipoVeiculo
    origem_aquisicao: OrigemAquisicao
    documento_entrada_tipo: DocumentoEntradaTipo
    documento_entrada_numero: str = Field(max_length=60)
    certidao_baixa_numero: str | None = Field(None, max_length=60)
    peso_entrada_kg: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=3)
    sem_viabilidade_desmontagem: bool = False
    estado: EstadoVeiculo
    registrado_em: AwareDatetime
    etapas: list[EtapaPortavel] = []
    anexos: list[AnexoPortavel] = []
    pecas: list[PecaPortavel] = []
    pesagens: list[PesagemPortavel] = []
    dmrs: list[DmrPortavel] = []
    laudo: LaudoPortavel | None = None


class CertificadoPortavel(BaseModel):
    numero: str = NumeroCertificado
    chassi: str = Chassi
    emitente_cnpj: str = Cnpj
    tipo_veiculo: TipoVeiculo
    fator: Decimal = Field(gt=0, le=1, max_digits=5, decimal_places=2)
    percentual_aproveitado: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    meta_ano: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    atende_meta: bool | None = None
    emitido_em: AwareDatetime
    hash_conteudo: str = Field(pattern=_HASH)


class CreditoPortavel(BaseModel):
    certificado_numero: str = NumeroCertificado
    chassi: str = Chassi
    quantidade: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    status: UrvCreditoStatus
    geradora_cnpj: str = Cnpj
    titular_cnpj: str = Cnpj
    gerado_em: AwareDatetime
    transferido_em: AwareDatetime | None = None


class LancamentoPortavel(BaseModel):
    """Extrato da empresa. Na importação serve só à conferência; os lançamentos são refeitos."""

    tipo: LancamentoTipo
    quantidade: Decimal = Field(max_digits=14, decimal_places=2, description="Com sinal")
    certificado_numero: str | None = None
    consumo_referencia: str | None = None
    contraparte_cnpj: str | None = None
    registrado_em: AwareDatetime


class MmvPortavel(BaseModel):
    codigo: str = Field(min_length=1, max_length=60)
    ncm: str = Field(pattern=r"^[0-9]{8}$")
    nivel: int = Field(ge=1, le=2)
    percentual_reciclabilidade: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    ja_comercializado: bool
    efeitos_a_partir_de: date
    status: MmvStatus = MmvStatus.ATIVO
    cadastrado_em: AwareDatetime


class ConsumoPortavel(BaseModel):
    referencia: str = Field(max_length=64, description="Identificador do consumo na plataforma de origem")
    mmv_codigo: str = Field(min_length=1, max_length=60)
    periodo: str = Field(pattern=_PERIODO)
    qv: int = Field(gt=0)
    rm: int
    pm: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    pb: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    urv_debito: Decimal = Field(
        ge=0, max_digits=14, decimal_places=2, description="Deste consumo, no acumulado do MMV no período"
    )
    saldo_apos: Decimal = Field(max_digits=14, decimal_places=2)
    regularizar_ate: date | None = None
    prazo_reporte: date
    registrado_em: AwareDatetime
    chassis: list[str] = Field(min_length=1)


class ArquivoPortabilidade(BaseModel):
    """Todo o histórico de uma empresa. RF-25, RNF-05, art. 22 I e II."""

    versao_formato: str = Field(
        description=f'Versão do formato; esta plataforma lê e escreve "{VERSAO_FORMATO}"'
    )
    gerado_em: AwareDatetime
    origem: OrigemPortavel
    empresa: EmpresaPortavel
    usuarios: list[UsuarioPortavel] = []
    vinculos: list[VinculoPortavel] = []
    veiculos: list[VeiculoPortavel] = []
    certificados: list[CertificadoPortavel] = []
    creditos: list[CreditoPortavel] = []
    lancamentos: list[LancamentoPortavel] = []
    mmvs: list[MmvPortavel] = []
    consumos: list[ConsumoPortavel] = []
    saldo: Decimal = Field(max_digits=14, decimal_places=2, description="Saldo de URV na origem")
    hash_conteudo: str | None = Field(
        None, pattern=_HASH, description="Obrigatório na importação (422 HASH_AUSENTE)"
    )


class ItemImportado(BaseModel):
    tipo: str = Field(description="veiculo, mmv, credito_recebido ou consumo")
    chave: str = Field(description="Chassi, código do MMV, número do certificado ou referência do consumo")


class ItemRejeitado(ItemImportado):
    motivo: str = Field(description="Código estável, por exemplo CHASSI_JA_CREDITADO")
    detalhe: str


class ResultadoImportacao(BaseModel):
    versao_formato: str
    empresa_id: uuid.UUID
    importados: list[ItemImportado]
    rejeitados: list[ItemRejeitado]
    total_importados: int
    total_rejeitados: int
    saldo_arquivo: Decimal
    saldo_local: Decimal
    saldo_confere: bool = Field(
        description="O saldo local depois da importação bate com o do arquivo (art. 28)"
    )
