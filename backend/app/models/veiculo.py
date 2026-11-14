import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ComId, coluna_enum
from app.models.enums import (
    AnexoTipo,
    DestinoPesagem,
    DocumentoEntradaTipo,
    EstadoVeiculo,
    EtapaTipo,
    Fracao,
    OrigemAquisicao,
    PecaClassificacao,
    PecaCondicao,
    PecaDestino,
    TipoVeiculo,
)


class Veiculo(ComId, Base):
    """Veículo em fim de vida. RF-06, art. 6º I; art. 18 III; Anexo III 14.a."""

    __tablename__ = "veiculo"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    chassi: Mapped[str] = mapped_column(String(30), unique=True)  # RF-21
    placa: Mapped[str | None] = mapped_column(String(10))
    # Únicos: um Renavam e uma certidão de baixa por veículo (art. 18 II; art. 21 III; A7 da revisão).
    renavam: Mapped[str | None] = mapped_column(String(11), unique=True)
    data_entrada: Mapped[date] = mapped_column(Date)
    tipo_declarado: Mapped[TipoVeiculo] = mapped_column(coluna_enum(TipoVeiculo, "tipo_declarado"))
    # Tipo efetivo, usado no fator. SUCATA_INSERVIVEL sem evidência de classificação (art. 2º §5º).
    tipo: Mapped[TipoVeiculo] = mapped_column(coluna_enum(TipoVeiculo, "tipo"))
    origem_aquisicao: Mapped[OrigemAquisicao] = mapped_column(
        coluna_enum(OrigemAquisicao, "origem_aquisicao")
    )
    documento_entrada_tipo: Mapped[DocumentoEntradaTipo] = mapped_column(
        coluna_enum(DocumentoEntradaTipo, "documento_entrada_tipo")
    )
    documento_entrada_numero: Mapped[str] = mapped_column(String(60))
    certidao_baixa_numero: Mapped[str | None] = mapped_column(String(60), unique=True)
    peso_entrada_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    sem_viabilidade_desmontagem: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    estado: Mapped[EstadoVeiculo] = mapped_column(
        coluna_enum(EstadoVeiculo, "estado"),
        default=EstadoVeiculo.RECEBIDO,
        server_default=EstadoVeiculo.RECEBIDO.value,
    )

    etapas: Mapped[list["Etapa"]] = relationship(back_populates="veiculo", order_by="Etapa.iniciada_em")
    anexos: Mapped[list["Anexo"]] = relationship(back_populates="veiculo", order_by="Anexo.criado_em")
    pecas: Mapped[list["Peca"]] = relationship(back_populates="veiculo", order_by="Peca.criado_em")
    pesagens: Mapped[list["Pesagem"]] = relationship(back_populates="veiculo", order_by="Pesagem.criado_em")
    dmrs: Mapped[list["Dmr"]] = relationship(back_populates="veiculo", order_by="Dmr.emitida_em")

    __table_args__ = (
        CheckConstraint("peso_entrada_kg IS NULL OR peso_entrada_kg > 0", name="peso_positivo"),
    )


class Etapa(ComId, Base):
    """RF-08, art. 18 III a IX. Registros independentes, não uma fila rígida (art. 18 IV)."""

    __tablename__ = "etapa"

    veiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("veiculo.id"), index=True)
    tipo: Mapped[EtapaTipo] = mapped_column(coluna_enum(EtapaTipo, "tipo"))
    iniciada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observacoes: Mapped[str | None] = mapped_column(Text)

    veiculo: Mapped[Veiculo] = relationship(back_populates="etapas")

    __table_args__ = (
        UniqueConstraint("veiculo_id", "tipo"),
        CheckConstraint("concluida_em IS NULL OR concluida_em >= iniciada_em", name="conclusao_apos_inicio"),
    )


class Anexo(ComId, Base):
    """Arquivo em volume local; `sha256` gravado (RF-08)."""

    __tablename__ = "anexo"

    veiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("veiculo.id"), index=True)
    etapa_tipo: Mapped[EtapaTipo | None] = mapped_column(coluna_enum(EtapaTipo, "etapa_tipo"))
    tipo: Mapped[AnexoTipo] = mapped_column(coluna_enum(AnexoTipo, "tipo"))
    caminho: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    nome_original: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(100))
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger)
    enviado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))

    veiculo: Mapped[Veiculo] = relationship(back_populates="anexos")

    __table_args__ = (CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),)


class Peca(ComId, Base):
    """RF-09 e RF-10, art. 18 V; Anexo III 6 a 8 e 16."""

    __tablename__ = "peca"

    veiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("veiculo.id"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    classificacao: Mapped[PecaClassificacao] = mapped_column(coluna_enum(PecaClassificacao, "classificacao"))
    codigo_rastreio: Mapped[str | None] = mapped_column(String(64), unique=True)
    condicao: Mapped[PecaCondicao | None] = mapped_column(coluna_enum(PecaCondicao, "condicao"))
    destino: Mapped[PecaDestino | None] = mapped_column(coluna_enum(PecaDestino, "destino"))
    descaracterizada: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    veiculo: Mapped[Veiculo] = relationship(back_populates="pecas")

    __table_args__ = (
        CheckConstraint(
            "classificacao <> 'REUTILIZAVEL' OR codigo_rastreio IS NOT NULL",
            name="reutilizavel_com_rastreio",
        ),
    )


class Pesagem(ComId, Base):
    """RF-11, art. 18 §6º; Anexo III 14.c."""

    __tablename__ = "pesagem"

    veiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("veiculo.id"), index=True)
    fracao: Mapped[Fracao] = mapped_column(coluna_enum(Fracao, "fracao"))
    destino: Mapped[DestinoPesagem] = mapped_column(coluna_enum(DestinoPesagem, "destino"))
    peso_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3))

    veiculo: Mapped[Veiculo] = relationship(back_populates="pesagens")

    __table_args__ = (CheckConstraint("peso_kg > 0", name="peso_positivo"),)


class Dmr(ComId, Base):
    """Declaração de Movimentação de Resíduos. RF-13, art. 6º III d; Anexo III 14.d."""

    __tablename__ = "dmr"

    veiculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("veiculo.id"), index=True)
    numero: Mapped[str] = mapped_column(String(60))
    mtr_numero: Mapped[str] = mapped_column(String(60))
    destinatario_nome: Mapped[str] = mapped_column(String(200))
    destinatario_cnpj: Mapped[str] = mapped_column(String(14))
    tipo_material: Mapped[str] = mapped_column(String(100))
    peso_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    emitida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    veiculo: Mapped[Veiculo] = relationship(back_populates="dmrs")

    __table_args__ = (
        CheckConstraint("peso_kg > 0", name="peso_positivo"),
        CheckConstraint("destinatario_cnpj ~ '^[0-9]{14}$'", name="cnpj_digitos"),
    )
