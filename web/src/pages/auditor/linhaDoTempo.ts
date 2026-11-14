// Monta a linha do tempo de um chassi, do recebimento ao consumo, a partir das rotas de leitura.
// Não depende do nome dos eventos da trilha: usa os próprios registros (etapas, anexos, peças,
// pesagens, DMRs, laudo, certificado, crédito, transferência e consumos).

import * as api from "../../api";
import type { CertificadoDetalhe, Consumo, Evento, Laudo, VeiculoDetalhe } from "../../api/types";
import { formatarDecimal } from "../../lib/decimal";
import {
  ROTULO_ANEXO,
  ROTULO_CLASSIFICACAO,
  ROTULO_DESTINO_PESAGEM,
  ROTULO_ETAPA,
  ROTULO_FRACAO,
  ROTULO_ORIGEM,
  ROTULO_TIPO_VEICULO,
} from "../../lib/dominio";
import { fmtCnpj, fmtPeriodo } from "../../lib/formato";

export interface Marco {
  quando: string;
  titulo: string;
  detalhe?: string;
  artigo?: string;
  /** Em que parte da história o marco cai. */
  fase: "fluxo" | "documento" | "urv";
}

export interface LinhaDoTempo {
  chassi: string;
  veiculo: VeiculoDetalhe | null;
  certificado: CertificadoDetalhe | null;
  marcos: Marco[];
  /** Eventos da trilha ligados ao veículo, como a API os registrou. */
  eventos: Evento[];
  /** Consumos em que o chassi buscado aparece como veículo novo. */
  consumosDoChassi: Consumo[];
}

export async function montarLinhaDoTempo(termo: string): Promise<LinhaDoTempo> {
  const chassi = termo.trim().toUpperCase();
  const [veiculos, consumos, doChassi, empresas] = await Promise.all([
    api.listarVeiculos({ chassi }),
    api.listarConsumos(),
    api.listarConsumos({ chassi }), // PM-WEB-06: o consumo em que o chassi foi usado como veículo novo
    api.listarEmpresas(),
  ]);
  const nome = (id: string | null) => empresas.itens.find((e) => e.id === id)?.razao_social ?? "empresa não identificada";
  const consumosDoChassi = doChassi.itens;
  const achado = veiculos.itens.find((v) => v.chassi === chassi) ?? (veiculos.itens.length === 1 ? veiculos.itens[0] : null);
  if (!achado) return { chassi, veiculo: null, certificado: null, marcos: [], eventos: [], consumosDoChassi };

  const [veiculo, pecas, pesagens, dmrs, eventos] = await Promise.all([
    api.obterVeiculo(achado.id),
    api.listarPecas({ veiculo_id: achado.id }), // PM-WEB-04
    api.listarPesagens(achado.id),
    api.listarDmrs(achado.id),
    api.listarEventos({ veiculo_id: achado.id, tamanho: 100 }), // o dossiê inteiro na trilha (L-13)
  ]);
  // O detalhe do veículo traz `laudo_id` e `certificado_id` (PM-03 a); o laudo tem rota própria (PM-WEB-03).
  const [laudo, certificado]: [Laudo | null, CertificadoDetalhe | null] = await Promise.all([
    veiculo.laudo_id ? api.obterLaudo(veiculo.id) : null,
    veiculo.certificado_id ? api.obterCertificado(veiculo.certificado_id) : null,
  ]);

  const marcos: Marco[] = [
    {
      quando: veiculo.criado_em,
      fase: "fluxo",
      titulo: `Veículo recebido por ${nome(veiculo.empresa_id)}`,
      detalhe:
        `Declarado como ${ROTULO_TIPO_VEICULO[veiculo.tipo_declarado].toLowerCase()}; ` +
        `${ROTULO_ORIGEM[veiculo.origem_aquisicao].toLowerCase()}; documento ${veiculo.documento_entrada_numero}; ` +
        `certidão de baixa ${veiculo.certidao_baixa_numero}.`,
      artigo: "art. 6º I",
    },
  ];
  for (const a of veiculo.anexos) {
    marcos.push({
      quando: a.criado_em,
      fase: "documento",
      titulo:
        `${ROTULO_ANEXO[a.tipo]} ${a.tipo === "DOCUMENTO_ENTRADA" ? "anexado" : "anexada"} ` +
        (a.etapa_tipo ? `à etapa de ${ROTULO_ETAPA[a.etapa_tipo].toLowerCase()}` : "ao veículo"),
      detalhe: a.tipo === "EVIDENCIA_CLASSIFICACAO" ? "Passa a valer o tipo declarado." : undefined,
      artigo: a.tipo === "EVIDENCIA_CLASSIFICACAO" ? "art. 6º I c" : undefined,
    });
  }
  for (const e of veiculo.etapas) {
    marcos.push({ quando: e.iniciada_em, fase: "fluxo", titulo: `${ROTULO_ETAPA[e.tipo]}: início` });
    if (e.concluida_em) {
      marcos.push({
        quando: e.concluida_em,
        fase: "fluxo",
        titulo: `${ROTULO_ETAPA[e.tipo]}: conclusão`,
        detalhe: e.observacoes ?? undefined,
      });
    }
  }
  for (const p of pecas.itens) {
    marcos.push({
      quando: p.criado_em,
      fase: "fluxo",
      titulo: `Peça registrada: ${p.nome}`,
      detalhe: `${ROTULO_CLASSIFICACAO[p.classificacao]}${p.codigo_rastreio ? `, etiqueta ${p.codigo_rastreio}` : ""}.`,
      artigo: "art. 18 V",
    });
  }
  for (const p of pesagens.itens) {
    marcos.push({
      quando: p.criado_em,
      fase: "fluxo",
      titulo: `Pesagem: ${formatarDecimal(p.peso_kg)} kg de ${ROTULO_FRACAO[p.fracao].toLowerCase()}`,
      detalhe: `Destino: ${ROTULO_DESTINO_PESAGEM[p.destino].toLowerCase()}.`,
    });
  }
  for (const d of dmrs.itens) {
    marcos.push({
      quando: d.emitida_em,
      fase: "documento",
      titulo: `DMR ${d.numero} emitida (${d.mtr_numero})`,
      detalhe: `${formatarDecimal(d.peso_kg)} kg de ${d.tipo_material} para ${d.destinatario_nome}, CNPJ ${fmtCnpj(d.destinatario_cnpj)}.`,
      artigo: "art. 6º III d",
    });
  }

  if (laudo) {
    marcos.push({
      quando: laudo.assinado_em,
      fase: "documento",
      titulo: "Laudo de Reciclagem assinado",
      detalhe: `${laudo.responsavel_nome}, registro ${laudo.responsavel_registro}.`,
      artigo: "art. 18 VII",
    });
  }
  if (certificado) {
    marcos.push({
      quando: certificado.emitido_em,
      fase: "documento",
      titulo: `Certificado ${certificado.numero} emitido`,
      detalhe:
        `Tipo ${ROTULO_TIPO_VEICULO[certificado.tipo_veiculo].toLowerCase()}, fator ${formatarDecimal(certificado.fator)}` +
        (certificado.percentual_aproveitado ? `; ${formatarDecimal(certificado.percentual_aproveitado, 2)}% aproveitado.` : "."),
      artigo: "art. 18 VIII",
    });
    const credito = certificado.credito;
    if (credito) {
      // O crédito nasce na mesma transação do certificado (RF-16, art. 18 §3º).
      const geradoEm = certificado.emitido_em;
      marcos.push({
        quando: geradoEm,
        fase: "urv",
        titulo: `Crédito de ${formatarDecimal(credito.quantidade)} URV gerado para ${nome(credito.geradora_id)}`,
        artigo: "art. 3º §§1º e 2º",
      });
      if (credito.status === "TRANSFERIDO") {
        const extrato = await api.listarExtrato(credito.geradora_id);
        const saida = extrato.itens.find((l) => l.credito_id === credito.id && l.tipo === "TRANSFERENCIA_SAIDA");
        const transferidoEm = saida?.criado_em ?? geradoEm;
        marcos.push({
          quando: transferidoEm,
          fase: "urv",
          titulo: `Crédito transferido a ${nome(credito.titular_id)}`,
          detalhe: "Transferência direta e única; o crédito não circula de novo.",
          artigo: "art. 8º II e §3º",
        });
        // A URV entra no saldo do fabricante e deixa de ser identificável; mostram-se os consumos
        // que esse fabricante registrou depois de receber o crédito.
        for (const c of consumos.itens.filter((x) => x.fabricante_id === credito.titular_id && x.registrado_em >= transferidoEm)) {
          marcos.push({
            quando: c.registrado_em,
            fase: "urv",
            titulo: `Consumo de ${formatarDecimal(c.urv_debito)} URV por ${nome(c.fabricante_id)}`,
            detalhe:
              `${c.qv} ${c.qv === 1 ? "veículo novo" : "veículos novos"} no período ${fmtPeriodo(c.periodo)}` +
              (c.chassis?.length ? `: ${c.chassis.join(", ")}.` : ".") +
              ` Saldo após: ${formatarDecimal(c.saldo_apos)} URV.`,
            artigo: "art. 8º III",
          });
        }
      }
    }
  }

  marcos.sort((a, b) => Date.parse(a.quando) - Date.parse(b.quando));
  return { chassi, veiculo, certificado, marcos, eventos: eventos.itens, consumosDoChassi };
}
