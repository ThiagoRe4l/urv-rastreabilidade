"""Exportação e importação para portabilidade entre plataformas. RF-25, RNF-04, RNF-05, art. 22.

Exportação: todo o histórico da empresa em JSON versionado (ver `schemas.py`).

Importação (ADMIN): a empresa do arquivo precisa já estar cadastrada aqui. Cada item é gravado
em um savepoint próprio; o que não passa na validação volta em `rejeitados`, com o motivo, e não
impede os demais. Escopo no MVP:

- Geradora: veículos com laudo, certificado e crédito (o dossiê completo, menos os arquivos).
  Chassi que já tem crédito aqui é rejeitado com CHASSI_JA_CREDITADO (RF-21, arts. 28 e 29).
- Fabricante: MMVs, créditos recebidos (o crédito precisa existir aqui, vindo do arquivo da
  geradora) e consumos, com rejeição de chassi já consumido.

Services não fazem commit; a rota faz.
"""

import hashlib
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.cnpj import normalizar_cnpj
from app.core.configuracao import fator_vigente
from app.core.decimais import quantizar
from app.core.erros import ErroNegocio, NaoEncontrado
from app.models import (
    Certificado,
    Consumo,
    ConsumoChassi,
    Dmr,
    Empresa,
    EstadoVeiculo,
    Etapa,
    LancamentoTipo,
    Laudo,
    Mmv,
    Peca,
    Pesagem,
    TipoEmpresa,
    UrvCredito,
    UrvCreditoStatus,
    UrvLancamento,
    Usuario,
    Veiculo,
    Vinculo,
)
from app.modules.auditoria.service import CHAVE_BLOQUEIO_CADEIA, json_canonico, registrar_evento
from app.modules.portabilidade.schemas import (
    PLATAFORMA,
    VERSAO_FORMATO,
    AnexoPortavel,
    ArquivoPortabilidade,
    CertificadoPortavel,
    ConsumoPortavel,
    CreditoPortavel,
    DmrPortavel,
    EmpresaPortavel,
    EtapaPortavel,
    ItemImportado,
    ItemRejeitado,
    LancamentoPortavel,
    LaudoPortavel,
    MmvPortavel,
    OrigemPortavel,
    PecaPortavel,
    PesagemPortavel,
    ResultadoImportacao,
    UsuarioPortavel,
    VeiculoPortavel,
    VinculoPortavel,
)
from app.modules.urv.calculo import calcular_debito, rm_do_nivel
from app.modules.urv.relogio import data_operacao
from app.modules.urv.schemas import normalizar_chassi
from app.modules.urv.service import saldo_empresa, travar_empresas

TIPOS_GERADORA = (TipoEmpresa.DESMONTADORA, TipoEmpresa.RECICLADORA)
ESTADOS_COM_CERTIFICADO = (EstadoVeiculo.CERTIFICADO, EstadoVeiculo.ENCERRADO)
VERSAO_PLATAFORMA = "0.1.0"


def hash_documento(documento: dict[str, Any]) -> str:
    """SHA-256 do JSON canônico do documento, sem o campo `hash_conteudo`."""
    sem_hash = {k: v for k, v in documento.items() if k != "hash_conteudo"}
    return hashlib.sha256(json_canonico(sem_hash).encode("utf-8")).hexdigest()


# --- Exportação -------------------------------------------------------------------------------


def exportar(session: Session, empresa_id: uuid.UUID, momento: datetime) -> dict[str, Any]:
    """Documento de portabilidade da empresa, pronto para serializar. RF-25, art. 22 I e II."""
    empresa = session.get(Empresa, empresa_id)
    if empresa is None:
        raise NaoEncontrado("Empresa")

    veiculos = session.scalars(
        select(Veiculo)
        .where(Veiculo.empresa_id == empresa_id)
        .options(
            selectinload(Veiculo.etapas),
            selectinload(Veiculo.anexos),
            selectinload(Veiculo.pecas),
            selectinload(Veiculo.pesagens),
            selectinload(Veiculo.dmrs),
        )
        .order_by(Veiculo.criado_em, Veiculo.chassi)
    ).all()
    laudos = {
        laudo.veiculo_id: laudo
        for laudo in session.scalars(select(Laudo).where(Laudo.veiculo_id.in_([v.id for v in veiculos])))
    }
    # Créditos gerados pela empresa ou de que ela é titular (os recebidos, no caso do fabricante).
    creditos = session.scalars(
        select(UrvCredito)
        .where(or_(UrvCredito.geradora_id == empresa_id, UrvCredito.titular_id == empresa_id))
        .options(selectinload(UrvCredito.certificado).selectinload(Certificado.veiculo))
        .order_by(UrvCredito.criado_em, UrvCredito.id)
    ).all()
    certificados = session.scalars(
        select(Certificado)
        .where(
            or_(
                Certificado.empresa_id == empresa_id,
                Certificado.id.in_([c.certificado_id for c in creditos]),
            )
        )
        .options(selectinload(Certificado.veiculo))
        .order_by(Certificado.emitido_em, Certificado.numero)
    ).all()
    lancamentos = session.scalars(
        select(UrvLancamento)
        .where(UrvLancamento.empresa_id == empresa_id)
        .order_by(UrvLancamento.criado_em, UrvLancamento.id)
    ).all()
    mmvs = session.scalars(select(Mmv).where(Mmv.fabricante_id == empresa_id).order_by(Mmv.codigo)).all()
    consumos = session.scalars(
        select(Consumo)
        .where(Consumo.fabricante_id == empresa_id)
        .options(selectinload(Consumo.chassis))
        .order_by(Consumo.registrado_em, Consumo.id)
    ).all()
    usuarios = session.scalars(
        select(Usuario).where(Usuario.empresa_id == empresa_id).order_by(Usuario.email)
    ).all()
    vinculos = session.scalars(
        select(Vinculo)
        .where(or_(Vinculo.geradora_id == empresa_id, Vinculo.fabricante_id == empresa_id))
        .order_by(Vinculo.criado_em, Vinculo.id)
    ).all()

    transferido_em = dict(
        session.execute(
            select(UrvLancamento.credito_id, UrvLancamento.criado_em).where(
                UrvLancamento.tipo == LancamentoTipo.TRANSFERENCIA_SAIDA,
                UrvLancamento.credito_id.in_([c.id for c in creditos]),
            )
        )
        .tuples()
        .all()
    )
    ids_empresas = {empresa_id}
    ids_empresas.update(i for c in creditos for i in (c.geradora_id, c.titular_id))
    ids_empresas.update(c.empresa_id for c in certificados)
    ids_empresas.update(lanc.contraparte_id for lanc in lancamentos if lanc.contraparte_id)
    cnpj = dict(
        session.execute(select(Empresa.id, Empresa.cnpj).where(Empresa.id.in_(ids_empresas))).tuples().all()
    )
    numero_por_credito = {c.id: c.certificado.numero for c in creditos}
    codigo_mmv = {m.id: m.codigo for m in mmvs}

    arquivo = ArquivoPortabilidade(
        versao_formato=VERSAO_FORMATO,
        gerado_em=momento,
        origem=OrigemPortavel(plataforma=PLATAFORMA, versao=VERSAO_PLATAFORMA),
        empresa=EmpresaPortavel(
            cnpj=empresa.cnpj,
            razao_social=empresa.razao_social,
            tipo=empresa.tipo,
            credenciamento_status=empresa.credenciamento_status,
            credenciamento_validade=empresa.credenciamento_validade,
            registro_compromissos=empresa.registro_compromissos,
        ),
        usuarios=[UsuarioPortavel(nome=u.nome, email=u.email, papel=u.papel) for u in usuarios],
        vinculos=[
            VinculoPortavel(geradora_cnpj=v.geradora.cnpj, fabricante_cnpj=v.fabricante.cnpj, ativo=v.ativo)
            for v in vinculos
        ],
        veiculos=[_veiculo_portavel(v, laudos.get(v.id)) for v in veiculos],
        certificados=[
            CertificadoPortavel(
                numero=c.numero,
                chassi=c.veiculo.chassi,
                emitente_cnpj=cnpj[c.empresa_id],
                tipo_veiculo=c.tipo_veiculo,
                fator=c.fator,
                percentual_aproveitado=c.percentual_aproveitado,
                meta_ano=c.meta_ano,
                atende_meta=c.atende_meta,
                emitido_em=c.emitido_em,
                hash_conteudo=c.hash_conteudo,
            )
            for c in certificados
        ],
        creditos=[
            CreditoPortavel(
                certificado_numero=c.certificado.numero,
                chassi=c.certificado.veiculo.chassi,
                quantidade=c.quantidade,
                status=c.status,
                geradora_cnpj=cnpj[c.geradora_id],
                titular_cnpj=cnpj[c.titular_id],
                gerado_em=c.certificado.emitido_em,
                transferido_em=transferido_em.get(c.id),
            )
            for c in creditos
        ],
        lancamentos=[
            LancamentoPortavel(
                tipo=lanc.tipo,
                quantidade=lanc.quantidade,
                certificado_numero=numero_por_credito.get(lanc.credito_id) if lanc.credito_id else None,
                consumo_referencia=str(lanc.consumo_id) if lanc.consumo_id else None,
                contraparte_cnpj=cnpj.get(lanc.contraparte_id) if lanc.contraparte_id else None,
                registrado_em=lanc.criado_em,
            )
            for lanc in lancamentos
        ],
        mmvs=[
            MmvPortavel(
                codigo=m.codigo,
                ncm=m.ncm,
                nivel=m.nivel,
                percentual_reciclabilidade=m.percentual_reciclabilidade,
                ja_comercializado=m.ja_comercializado,
                efeitos_a_partir_de=m.efeitos_a_partir_de,
                status=m.status,
                cadastrado_em=m.criado_em,
            )
            for m in mmvs
        ],
        consumos=[
            ConsumoPortavel(
                referencia=str(c.id),
                mmv_codigo=codigo_mmv[c.mmv_id],
                periodo=c.periodo,
                qv=c.qv,
                rm=c.rm,
                pm=c.pm,
                pb=c.pb,
                urv_debito=c.urv_debito,
                saldo_apos=c.saldo_apos,
                regularizar_ate=c.regularizar_ate,
                prazo_reporte=c.prazo_reporte,
                registrado_em=c.registrado_em,
                chassis=sorted(ch.chassi for ch in c.chassis),
            )
            for c in consumos
        ],
        saldo=saldo_empresa(session, empresa_id),
    )
    documento = arquivo.model_dump(mode="json")
    documento["hash_conteudo"] = hash_documento(documento)
    return documento


def _veiculo_portavel(v: Veiculo, laudo: Laudo | None) -> VeiculoPortavel:
    return VeiculoPortavel(
        chassi=v.chassi,
        placa=v.placa,
        renavam=v.renavam,
        data_entrada=v.data_entrada,
        tipo_declarado=v.tipo_declarado,
        tipo=v.tipo,
        origem_aquisicao=v.origem_aquisicao,
        documento_entrada_tipo=v.documento_entrada_tipo,
        documento_entrada_numero=v.documento_entrada_numero,
        certidao_baixa_numero=v.certidao_baixa_numero,
        peso_entrada_kg=v.peso_entrada_kg,
        sem_viabilidade_desmontagem=v.sem_viabilidade_desmontagem,
        estado=v.estado,
        registrado_em=v.criado_em,
        etapas=[
            EtapaPortavel(
                tipo=e.tipo, iniciada_em=e.iniciada_em, concluida_em=e.concluida_em, observacoes=e.observacoes
            )
            for e in v.etapas
        ],
        anexos=[
            AnexoPortavel(
                tipo=a.tipo,
                etapa_tipo=a.etapa_tipo,
                sha256=a.sha256,
                nome_original=a.nome_original,
                content_type=a.content_type,
                tamanho_bytes=a.tamanho_bytes,
                enviado_em=a.criado_em,
            )
            for a in v.anexos
        ],
        pecas=[
            PecaPortavel(
                nome=p.nome,
                descricao=p.descricao,
                classificacao=p.classificacao,
                codigo_rastreio=p.codigo_rastreio,
                condicao=p.condicao,
                destino=p.destino,
                descaracterizada=p.descaracterizada,
                registrada_em=p.criado_em,
            )
            for p in v.pecas
        ],
        pesagens=[
            PesagemPortavel(fracao=p.fracao, destino=p.destino, peso_kg=p.peso_kg, registrada_em=p.criado_em)
            for p in v.pesagens
        ],
        dmrs=[
            DmrPortavel(
                numero=d.numero,
                mtr_numero=d.mtr_numero,
                destinatario_nome=d.destinatario_nome,
                destinatario_cnpj=d.destinatario_cnpj,
                tipo_material=d.tipo_material,
                peso_kg=d.peso_kg,
                emitida_em=d.emitida_em,
            )
            for d in v.dmrs
        ],
        laudo=None
        if laudo is None
        else LaudoPortavel(
            responsavel_nome=laudo.responsavel_nome,
            responsavel_registro=laudo.responsavel_registro,
            assinado_em=laudo.assinado_em,
            hash_conteudo=laudo.hash_conteudo,
            assinatura=laudo.assinatura,
        ),
    )


# --- Importação -------------------------------------------------------------------------------


class _Rejeicao(Exception):
    """Item recusado na importação: desfaz o savepoint do item e entra em `rejeitados`."""

    def __init__(self, motivo: str, detalhe: str) -> None:
        super().__init__(detalhe)
        self.motivo = motivo
        self.detalhe = detalhe


class _Importacao:
    def __init__(self, session: Session, usuario: Usuario, empresa: Empresa, arquivo: ArquivoPortabilidade):
        self.session = session
        self.usuario = usuario
        self.empresa = empresa
        self.arquivo = arquivo
        self.origem = arquivo.origem.plataforma
        self.importados: list[ItemImportado] = []
        self.rejeitados: list[ItemRejeitado] = []

    # Cada item em um savepoint: a falha de um não desfaz os outros.
    def tentar(self, tipo: str, chave: str, gravar: Callable[[], None]) -> None:
        try:
            with self.session.begin_nested():
                gravar()
        except _Rejeicao as r:
            self.rejeitados.append(ItemRejeitado(tipo=tipo, chave=chave, motivo=r.motivo, detalhe=r.detalhe))
        except (IntegrityError, DataError):
            self.rejeitados.append(
                ItemRejeitado(
                    tipo=tipo,
                    chave=chave,
                    motivo="VIOLACAO_INTEGRIDADE",
                    detalhe="O item viola uma restrição de integridade do banco.",
                )
            )
        else:
            self.importados.append(ItemImportado(tipo=tipo, chave=chave))

    def evento(self, tipo: str, entidade: str, entidade_id: uuid.UUID, payload: dict[str, Any]) -> None:
        registrar_evento(
            self.session,
            self.usuario,
            tipo,
            entidade,
            entidade_id,
            {**payload, "origem": self.origem},
            empresa_id=self.empresa.id,
        )

    def empresa_por_cnpj(self, cnpj: str) -> Empresa | None:
        return self.session.scalar(select(Empresa).where(Empresa.cnpj == normalizar_cnpj(cnpj)))

    # --- Geradora: veículo com laudo, certificado e crédito ---------------------------------

    def veiculo(
        self, v: VeiculoPortavel, cert: CertificadoPortavel | None, cred: CreditoPortavel | None
    ) -> None:
        s, empresa = self.session, self.empresa
        chassi = normalizar_chassi(v.chassi)
        if empresa.tipo not in TIPOS_GERADORA:
            raise _Rejeicao(
                "EMPRESA_NAO_GERADORA", "Só desmontadora ou recicladora registra veículo em fim de vida."
            )

        # RF-21, RNF-04, arts. 28 e 29: um chassi em fim de vida gera crédito uma única vez,
        # em qualquer plataforma.
        existente = s.scalar(select(Veiculo).where(func.upper(Veiculo.chassi) == chassi))
        if existente is not None:
            creditado = s.scalar(select(Certificado.id).where(Certificado.veiculo_id == existente.id))
            if creditado is not None:
                raise _Rejeicao(
                    "CHASSI_JA_CREDITADO", f"O chassi {chassi} já gerou crédito de URV nesta plataforma."
                )
            raise _Rejeicao(
                "CHASSI_JA_REGISTRADO", f"O chassi {chassi} já está em processamento nesta plataforma."
            )

        if cert is None:
            raise _Rejeicao("VEICULO_SEM_CERTIFICADO", "O MVP só importa veículo com certificado emitido.")
        if cred is None:
            raise _Rejeicao("CERTIFICADO_SEM_CREDITO", "O arquivo não traz o crédito do certificado.")
        if v.laudo is None:
            raise _Rejeicao("VEICULO_SEM_LAUDO", "Certificado sem laudo de reciclagem (art. 6º I f).")
        if v.estado not in ESTADOS_COM_CERTIFICADO:
            raise _Rejeicao("ESTADO_DIVERGENTE", f"Veículo com certificado no estado {v.estado}.")
        if s.scalar(select(Certificado.id).where(Certificado.numero == cert.numero)) is not None:
            raise _Rejeicao("CERTIFICADO_DUPLICADO", f"Já existe certificado com o número {cert.numero}.")
        if cert.emitente_cnpj != empresa.cnpj or cred.geradora_cnpj != empresa.cnpj:
            raise _Rejeicao("GERADORA_DIVERGENTE", "O certificado ou o crédito é de outra empresa.")
        if cert.tipo_veiculo != v.tipo:
            raise _Rejeicao("TIPO_DIVERGENTE", "O tipo do certificado difere do tipo efetivo do veículo.")
        try:
            fator = fator_vigente(s, cert.tipo_veiculo, data_operacao(cert.emitido_em))
        except ErroNegocio as exc:
            raise _Rejeicao(exc.codigo, exc.detail) from exc
        if cert.fator != fator:  # art. 3º §2º
            raise _Rejeicao("FATOR_DIVERGENTE", f"Fator {cert.fator} difere do vigente na emissão ({fator}).")
        if cred.quantidade != cert.fator:  # RF-16
            raise _Rejeicao(
                "QUANTIDADE_DIVERGENTE", "A quantidade do crédito difere do fator do certificado."
            )

        titular = empresa
        if cred.status == UrvCreditoStatus.TRANSFERIDO:
            achado = self.empresa_por_cnpj(cred.titular_cnpj)
            if achado is None or achado.tipo != TipoEmpresa.FABRICANTE:
                raise _Rejeicao(
                    "TITULAR_NAO_CADASTRADO",
                    f"O titular {cred.titular_cnpj} não é fabricante cadastrado nesta plataforma.",
                )
            titular = achado
        elif cred.titular_cnpj != empresa.cnpj:
            raise _Rejeicao("TITULAR_DIVERGENTE", "Crédito disponível com titular diferente da geradora.")
        rastreios = [p.codigo_rastreio for p in v.pecas if p.codigo_rastreio]
        if rastreios and s.scalar(select(Peca.id).where(Peca.codigo_rastreio.in_(rastreios)).limit(1)):
            raise _Rejeicao("CODIGO_RASTREIO_DUPLICADO", "Há peça com código de rastreio já usado aqui.")

        veiculo = Veiculo(
            empresa_id=empresa.id,
            chassi=chassi,
            placa=v.placa,
            renavam=v.renavam,
            data_entrada=v.data_entrada,
            tipo_declarado=v.tipo_declarado,
            tipo=v.tipo,
            origem_aquisicao=v.origem_aquisicao,
            documento_entrada_tipo=v.documento_entrada_tipo,
            documento_entrada_numero=v.documento_entrada_numero,
            certidao_baixa_numero=v.certidao_baixa_numero,
            peso_entrada_kg=v.peso_entrada_kg,
            sem_viabilidade_desmontagem=v.sem_viabilidade_desmontagem,
            estado=v.estado,
            criado_em=v.registrado_em,
        )
        s.add(veiculo)
        s.flush()
        s.add_all(
            Etapa(
                veiculo_id=veiculo.id,
                tipo=e.tipo,
                iniciada_em=e.iniciada_em,
                concluida_em=e.concluida_em,
                observacoes=e.observacoes,
            )
            for e in v.etapas
        )
        s.add_all(
            Peca(
                veiculo_id=veiculo.id,
                nome=p.nome,
                descricao=p.descricao,
                classificacao=p.classificacao,
                codigo_rastreio=p.codigo_rastreio,
                condicao=p.condicao,
                destino=p.destino,
                descaracterizada=p.descaracterizada,
                criado_em=p.registrada_em,
            )
            for p in v.pecas
        )
        s.add_all(
            Pesagem(
                veiculo_id=veiculo.id,
                fracao=p.fracao,
                destino=p.destino,
                peso_kg=p.peso_kg,
                criado_em=p.registrada_em,
            )
            for p in v.pesagens
        )
        s.add_all(
            Dmr(
                veiculo_id=veiculo.id,
                numero=d.numero,
                mtr_numero=d.mtr_numero,
                destinatario_nome=d.destinatario_nome,
                destinatario_cnpj=d.destinatario_cnpj,
                tipo_material=d.tipo_material,
                peso_kg=d.peso_kg,
                emitida_em=d.emitida_em,
            )
            for d in v.dmrs
        )
        s.add(
            Laudo(
                veiculo_id=veiculo.id,
                responsavel_nome=v.laudo.responsavel_nome,
                responsavel_registro=v.laudo.responsavel_registro,
                assinado_em=v.laudo.assinado_em,
                hash_conteudo=v.laudo.hash_conteudo,
                assinatura=v.laudo.assinatura,
            )
        )
        certificado = Certificado(
            veiculo_id=veiculo.id,
            numero=cert.numero,
            empresa_id=empresa.id,
            tipo_veiculo=cert.tipo_veiculo,
            fator=cert.fator,
            percentual_aproveitado=cert.percentual_aproveitado,
            meta_ano=cert.meta_ano,
            atende_meta=cert.atende_meta,
            emitido_em=cert.emitido_em,
            hash_conteudo=cert.hash_conteudo,
        )
        s.add(certificado)
        s.flush()
        credito = UrvCredito(
            certificado_id=certificado.id,
            geradora_id=empresa.id,
            titular_id=titular.id,
            quantidade=cred.quantidade,
            status=cred.status,
        )
        s.add(credito)
        s.flush()
        s.add(
            UrvLancamento(
                empresa_id=empresa.id,
                tipo=LancamentoTipo.CREDITO,
                quantidade=cred.quantidade,
                credito_id=credito.id,
                criado_em=cert.emitido_em,
            )
        )
        if cred.status == UrvCreditoStatus.TRANSFERIDO:
            # Só a saída da geradora. A entrada do fabricante vem do arquivo dele, junto com os
            # consumos, para o saldo dele aqui não nascer maior que o da origem (art. 28).
            s.add(
                UrvLancamento(
                    empresa_id=empresa.id,
                    tipo=LancamentoTipo.TRANSFERENCIA_SAIDA,
                    quantidade=-cred.quantidade,
                    credito_id=credito.id,
                    contraparte_id=titular.id,
                    criado_em=cred.transferido_em or cert.emitido_em,
                )
            )
        s.flush()

        self.evento(
            "VEICULO_IMPORTADO",
            "veiculo",
            veiculo.id,
            {
                "chassi": chassi,
                "tipo": v.tipo,
                "estado": v.estado,
                "data_entrada": v.data_entrada,
                "etapas": len(v.etapas),
                "pecas": len(v.pecas),
                "pesagens": len(v.pesagens),
                "dmrs": len(v.dmrs),
                "anexos_nao_importados": [a.sha256 for a in v.anexos],
                "laudo_hash": v.laudo.hash_conteudo,
            },
        )
        self.evento(
            "CERTIFICADO_IMPORTADO",
            "certificado",
            certificado.id,
            {
                "numero": cert.numero,
                "chassi": chassi,
                "tipo_veiculo": cert.tipo_veiculo,
                "fator": cert.fator,
                "emitido_em": cert.emitido_em,
                "hash_conteudo": cert.hash_conteudo,
            },
        )
        self.evento(
            "CREDITO_IMPORTADO",
            "urv_credito",
            credito.id,
            {
                "certificado_id": certificado.id,
                "quantidade": cred.quantidade,
                "status": cred.status,
                "geradora_id": empresa.id,
                "titular_id": titular.id,
            },
        )

    # --- Fabricante: MMVs, créditos recebidos e consumos ------------------------------------

    def _exigir_fabricante(self) -> None:
        if self.empresa.tipo != TipoEmpresa.FABRICANTE:
            raise _Rejeicao("EMPRESA_NAO_FABRICANTE", "Só fabricante ou importador tem MMV e consumo de URV.")

    def _mmv(self, codigo: str) -> Mmv | None:
        return self.session.scalar(
            select(Mmv).where(Mmv.fabricante_id == self.empresa.id, Mmv.codigo == codigo.strip())
        )

    def mmv(self, m: MmvPortavel) -> None:
        self._exigir_fabricante()
        if self._mmv(m.codigo) is not None:
            raise _Rejeicao("MMV_JA_CADASTRADO", f"O MMV {m.codigo} já está cadastrado para a empresa.")
        mmv = Mmv(
            fabricante_id=self.empresa.id,
            codigo=m.codigo.strip(),
            ncm=m.ncm,
            nivel=m.nivel,
            percentual_reciclabilidade=m.percentual_reciclabilidade,
            ja_comercializado=m.ja_comercializado,
            efeitos_a_partir_de=m.efeitos_a_partir_de,
            status=m.status,
            criado_em=m.cadastrado_em,
        )
        self.session.add(mmv)
        self.session.flush()
        self.evento(
            "MMV_IMPORTADO",
            "mmv",
            mmv.id,
            {
                "codigo": mmv.codigo,
                "ncm": mmv.ncm,
                "nivel": mmv.nivel,
                "efeitos_a_partir_de": mmv.efeitos_a_partir_de,
                "status": mmv.status,
            },
        )

    def credito_recebido(self, c: CreditoPortavel) -> None:
        s, empresa = self.session, self.empresa
        self._exigir_fabricante()
        credito = s.scalar(
            select(UrvCredito)
            .join(Certificado, Certificado.id == UrvCredito.certificado_id)
            .where(Certificado.numero == c.certificado_numero)
        )
        if credito is None:
            raise _Rejeicao(
                "CREDITO_NAO_ENCONTRADO",
                "O crédito não existe nesta plataforma; importe antes o arquivo da geradora.",
            )
        if credito.status != UrvCreditoStatus.TRANSFERIDO or credito.titular_id != empresa.id:
            raise _Rejeicao("TITULARIDADE_DIVERGENTE", "Aqui o crédito não está transferido a esta empresa.")
        if credito.quantidade != c.quantidade:
            raise _Rejeicao("QUANTIDADE_DIVERGENTE", "A quantidade difere da registrada nesta plataforma.")
        ja_entrou = s.scalar(
            select(UrvLancamento.id).where(
                UrvLancamento.credito_id == credito.id,
                UrvLancamento.tipo == LancamentoTipo.TRANSFERENCIA_ENTRADA,
            )
        )
        if ja_entrou is not None:  # RF-17: transferência única
            raise _Rejeicao("TRANSFERENCIA_JA_REGISTRADA", "A entrada deste crédito já está no extrato.")
        s.add(
            UrvLancamento(
                empresa_id=empresa.id,
                tipo=LancamentoTipo.TRANSFERENCIA_ENTRADA,
                quantidade=credito.quantidade,
                credito_id=credito.id,
                contraparte_id=credito.geradora_id,
                criado_em=c.transferido_em or c.gerado_em,
            )
        )
        s.flush()
        self.evento(
            "TRANSFERENCIA_IMPORTADA",
            "urv_credito",
            credito.id,
            {
                "certificado_numero": c.certificado_numero,
                "quantidade": credito.quantidade,
                "geradora_id": credito.geradora_id,
                "fabricante_id": empresa.id,
            },
        )

    def consumo(self, c: ConsumoPortavel) -> None:
        s, empresa = self.session, self.empresa
        self._exigir_fabricante()
        mmv = self._mmv(c.mmv_codigo)
        if mmv is None:
            raise _Rejeicao("MMV_NAO_ENCONTRADO", f"O MMV {c.mmv_codigo} não está cadastrado para a empresa.")
        chassis = [normalizar_chassi(ch) for ch in c.chassis]
        if c.qv != len(chassis) or len(set(chassis)) != len(chassis):
            raise _Rejeicao("QV_DIVERGENTE", "qv difere da quantidade de chassis distintos informados.")
        if any(not ch or len(ch) > 30 for ch in chassis):
            raise _Rejeicao("CHASSI_INVALIDO", "Há chassi vazio ou com mais de 30 caracteres.")
        if c.rm != rm_do_nivel(mmv.nivel):
            raise _Rejeicao("RM_DIVERGENTE", f"RM {c.rm} não corresponde ao nível {mmv.nivel} do MMV.")
        if calcular_debito(c.qv, c.rm, c.pm, c.pb) != c.urv_debito:  # RF-18, art. 3º §3º
            raise _Rejeicao(
                "DEBITO_DIVERGENTE", "O débito informado não confere com a fórmula do art. 3º §3º."
            )
        # RF-21, arts. 28 e 29: um chassi novo consome uma única vez, em qualquer plataforma.
        ja = s.scalars(
            select(ConsumoChassi.chassi)
            .where(ConsumoChassi.chassi.in_(chassis))
            .order_by(ConsumoChassi.chassi)
        ).all()
        if ja:
            raise _Rejeicao("CHASSI_JA_CONSUMIDO", "Chassi já usado em outro consumo: " + ", ".join(ja[:10]))

        saldo = saldo_empresa(s, empresa.id)
        consumo = Consumo(
            fabricante_id=empresa.id,
            mmv_id=mmv.id,
            periodo=c.periodo,
            qv=c.qv,
            rm=c.rm,
            pm=c.pm,
            pb=c.pb,
            urv_debito=c.urv_debito,
            saldo_apos=saldo - c.urv_debito,  # o saldo deste livro, não o da origem
            regularizar_ate=c.regularizar_ate,
            prazo_reporte=c.prazo_reporte,
            registrado_em=c.registrado_em,
            chassis=[ConsumoChassi(chassi=ch) for ch in chassis],
        )
        s.add(consumo)
        s.flush()
        s.add(
            UrvLancamento(
                empresa_id=empresa.id,
                tipo=LancamentoTipo.DEBITO,
                quantidade=-c.urv_debito,
                consumo_id=consumo.id,
                criado_em=c.registrado_em,
            )
        )
        s.flush()
        self.evento(
            "CONSUMO_IMPORTADO",
            "consumo",
            consumo.id,
            {
                "referencia_origem": c.referencia,
                "mmv_codigo": mmv.codigo,
                "periodo": c.periodo,
                "qv": c.qv,
                "rm": c.rm,
                "pm": c.pm,
                "pb": c.pb,
                "urv_debito": c.urv_debito,
                "saldo_apos": consumo.saldo_apos,
                "saldo_apos_origem": c.saldo_apos,
                "regularizar_ate": c.regularizar_ate,
                "registrado_em": c.registrado_em,
                "chassis": chassis,
            },
        )


def importar(
    session: Session,
    usuario: Usuario,
    arquivo: ArquivoPortabilidade,
    *,
    documento: dict[str, Any] | None = None,
) -> ResultadoImportacao:
    """Importa o histórico de uma empresa vindo de outra plataforma. RF-25, RNF-04, art. 22.

    `documento` é o JSON como recebido, usado para conferir `hash_conteudo`.
    """
    if arquivo.versao_formato != VERSAO_FORMATO:
        raise ErroNegocio(
            422,
            "VERSAO_FORMATO_NAO_SUPORTADA",
            f"Formato {arquivo.versao_formato!r} não suportado; esta plataforma lê {VERSAO_FORMATO!r}.",
        )
    if documento is not None and arquivo.hash_conteudo and hash_documento(documento) != arquivo.hash_conteudo:
        raise ErroNegocio(422, "HASH_INVALIDO", "O conteúdo do arquivo não confere com hash_conteudo.")

    # Credenciamento e registro de compromissos são atos do MDIC lançados pelo ADMIN: não vêm do arquivo.
    empresa = session.scalar(select(Empresa).where(Empresa.cnpj == arquivo.empresa.cnpj))
    if empresa is None:
        raise ErroNegocio(
            422,
            "EMPRESA_NAO_CADASTRADA",
            "Cadastre a empresa nesta plataforma antes de importar o histórico.",
        )
    if empresa.tipo != arquivo.empresa.tipo:
        raise ErroNegocio(
            422, "EMPRESA_TIPO_DIVERGENTE", "O tipo da empresa no arquivo difere do cadastrado."
        )

    # Mesma ordem de bloqueios do livro de URV: empresa, depois a cadeia de auditoria. A cadeia é
    # travada já aqui, fora dos savepoints dos itens, para que o desfazimento de um item não a solte.
    travar_empresas(session, empresa.id)
    session.execute(text("SELECT pg_advisory_xact_lock(:chave)"), {"chave": CHAVE_BLOQUEIO_CADEIA})

    imp = _Importacao(session, usuario, empresa, arquivo)

    certificados = {normalizar_chassi(c.chassi): c for c in arquivo.certificados}
    creditos = {c.certificado_numero: c for c in arquivo.creditos}
    chassis_no_arquivo = set()
    for v in arquivo.veiculos:
        chassi = normalizar_chassi(v.chassi)
        chassis_no_arquivo.add(chassi)
        cert = certificados.get(chassi)
        cred = creditos.get(cert.numero) if cert else None
        imp.tentar("veiculo", chassi, lambda v=v, cert=cert, cred=cred: imp.veiculo(v, cert, cred))

    for m in arquivo.mmvs:
        imp.tentar("mmv", m.codigo, lambda m=m: imp.mmv(m))

    recebidos = [
        c
        for c in arquivo.creditos
        if c.status == UrvCreditoStatus.TRANSFERIDO
        and c.titular_cnpj == empresa.cnpj
        and c.geradora_cnpj != empresa.cnpj
    ]
    for c in recebidos:
        imp.tentar("credito_recebido", c.certificado_numero, lambda c=c: imp.credito_recebido(c))

    for c in arquivo.creditos:
        if c.geradora_cnpj == empresa.cnpj and normalizar_chassi(c.chassi) not in chassis_no_arquivo:
            imp.rejeitados.append(
                ItemRejeitado(
                    tipo="credito",
                    chave=c.certificado_numero,
                    motivo="CREDITO_SEM_VEICULO",
                    detalhe="O arquivo traz o crédito, mas não o veículo que o gerou.",
                )
            )

    for c in sorted(arquivo.consumos, key=lambda c: c.registrado_em):
        imp.tentar("consumo", c.referencia, lambda c=c: imp.consumo(c))

    saldo_local = saldo_empresa(session, empresa.id)
    saldo_arquivo = quantizar(arquivo.saldo)
    resultado = ResultadoImportacao(
        versao_formato=arquivo.versao_formato,
        empresa_id=empresa.id,
        importados=imp.importados,
        rejeitados=imp.rejeitados,
        total_importados=len(imp.importados),
        total_rejeitados=len(imp.rejeitados),
        saldo_arquivo=saldo_arquivo,
        saldo_local=saldo_local,
        saldo_confere=saldo_local == saldo_arquivo,
    )
    registrar_evento(
        session,
        usuario,
        "PORTABILIDADE_IMPORTADA",
        "empresa",
        empresa.id,
        {
            "origem": arquivo.origem.plataforma,
            "versao_formato": arquivo.versao_formato,
            "gerado_em": arquivo.gerado_em,
            "hash_conteudo": arquivo.hash_conteudo,
            "importados": _contar(i.tipo for i in imp.importados),
            "rejeitados": [{"tipo": r.tipo, "chave": r.chave, "motivo": r.motivo} for r in imp.rejeitados],
            "saldo_arquivo": saldo_arquivo,
            "saldo_local": saldo_local,
        },
        empresa_id=empresa.id,
    )
    return resultado


def _contar(tipos: Any) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for t in tipos:
        contagem[t] = contagem.get(t, 0) + 1
    return contagem
