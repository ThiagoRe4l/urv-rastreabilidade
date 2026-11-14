// Rótulos em português para os enums do contrato e regras de apresentação ligadas à portaria.

import type * as T from "../api/types";

export const ROTULO_PAPEL: Record<T.Papel, string> = {
  ADMIN: "Administrador",
  DESMONTADORA: "Desmontadora",
  RECICLADORA: "Recicladora",
  FABRICANTE: "Fabricante ou importador",
  AUDITOR: "Auditor (MDIC)",
};

export const ROTULO_TIPO_EMPRESA: Record<T.TipoEmpresa, string> = {
  FABRICANTE: "Fabricante ou importador",
  DESMONTADORA: "Desmontadora",
  RECICLADORA: "Recicladora",
};

export const ROTULO_CREDENCIAMENTO: Record<T.CredenciamentoStatus, string> = {
  PENDENTE: "Pendente",
  ATIVO: "Ativo",
  SUSPENSO: "Suspenso",
  CANCELADO: "Cancelado",
};

// Ordem e fatores do art. 3º §2º. O fator exibido vem de GET /configuracao/fatores.
export const ROTULO_TIPO_VEICULO: Record<T.TipoVeiculo, string> = {
  LICENCIADO_RODAGEM: "Licenciado em condições de rodagem",
  SINISTRADO_PEQUENA_MEDIA: "Sinistrado de pequena ou média monta",
  SUCATA_APROVEITAVEL: "Sucata aproveitável",
  SINISTRADO_GRANDE: "Sinistrado de grande monta",
  SUCATA_MOTOR_INSERVIVEL: "Sucata com motor inservível",
  SUCATA_INSERVIVEL: "Sucata inservível",
};

export const ROTULO_ORIGEM: Record<T.OrigemAquisicao, string> = {
  COMPRA_DIRETA: "Compra direta",
  LEILAO_ORGAO_PUBLICO: "Leilão de órgão público",
  LEILAO_SEGURADORA: "Leilão de seguradora",
};

export const ROTULO_DOC_ENTRADA: Record<T.DocumentoEntradaTipo, string> = {
  NF_ENTRADA: "Nota fiscal de entrada",
  AUTO_ARREMATACAO: "Auto de arrematação",
};

export const ROTULO_ESTADO: Record<T.EstadoVeiculo, string> = {
  RECEBIDO: "Recebido",
  EM_PROCESSO: "Em processo",
  LAUDO_EMITIDO: "Laudo emitido",
  CERTIFICADO: "Certificado",
  ENCERRADO: "Encerrado",
};

export const ESTADOS: T.EstadoVeiculo[] = ["RECEBIDO", "EM_PROCESSO", "LAUDO_EMITIDO", "CERTIFICADO", "ENCERRADO"];

export const ETAPAS: T.EtapaTipo[] = ["RECEPCAO", "DESCONTAMINACAO", "DESMONTAGEM", "DESTRUICAO", "DESTINACAO"];

export const ROTULO_ETAPA: Record<T.EtapaTipo, string> = {
  RECEPCAO: "Recepção",
  DESCONTAMINACAO: "Descontaminação",
  DESMONTAGEM: "Desmontagem",
  DESTRUICAO: "Destruição e separação",
  DESTINACAO: "Destinação",
};

export const ROTULO_ANEXO: Record<T.AnexoTipo, string> = {
  FOTO: "Foto",
  DOCUMENTO_ENTRADA: "Documento de entrada",
  CERTIDAO_BAIXA: "Certidão de baixa",
  EVIDENCIA_CLASSIFICACAO: "Evidência de classificação",
};

export const ROTULO_CLASSIFICACAO: Record<T.PecaClassificacao, string> = {
  REUTILIZAVEL: "Reutilizável",
  NAO_REUTILIZAVEL: "Não reutilizável",
};

export const ROTULO_CONDICAO: Record<T.PecaCondicao, string> = {
  USADA: "Usada",
  REMANUFATURADA: "Remanufaturada",
};

export const ROTULO_DESTINO_PECA: Record<T.PecaDestino, string> = {
  ESTOQUE: "Estoque",
  REVENDA: "Revenda",
  EXPORTACAO: "Exportação",
  REMANUFATURA: "Remanufatura",
  RECONDICIONAMENTO: "Recondicionamento",
  RECICLAGEM: "Reciclagem",
  DESCARTE: "Descarte",
};

export const ROTULO_FRACAO: Record<T.Fracao, string> = {
  FERROSO: "Metais ferrosos",
  NAO_FERROSO: "Metais não ferrosos",
  NAO_METALICO: "Não metálicos",
  FLUIDOS: "Fluidos",
  BATERIAS: "Baterias",
  PNEUS: "Pneus",
};

export const ROTULO_DESTINO_PESAGEM: Record<T.DestinoPesagem, string> = {
  REAPROVEITAMENTO: "Reaproveitamento",
  RECICLAGEM: "Reciclagem",
  RECUPERACAO_ENERGETICA: "Recuperação energética",
  REJEITO: "Rejeito",
};

export const ROTULO_LANCAMENTO: Record<T.LancamentoTipo, string> = {
  CREDITO: "Crédito por certificado",
  TRANSFERENCIA_SAIDA: "Transferência enviada",
  TRANSFERENCIA_ENTRADA: "Transferência recebida",
  DEBITO: "Débito por consumo",
};

export const ROTULO_CREDITO: Record<T.UrvCreditoStatus, string> = {
  DISPONIVEL: "Disponível",
  TRANSFERIDO: "Transferido",
};

export function ehGeradora(papel: T.Papel): boolean {
  return papel === "DESMONTADORA" || papel === "RECICLADORA";
}

/** Tela inicial de cada papel. */
export function inicioDoPapel(papel: T.Papel): string {
  if (ehGeradora(papel)) return "/veiculos";
  if (papel === "FABRICANTE") return "/urv";
  if (papel === "AUDITOR") return "/painel";
  return "/empresas";
}

/**
 * Meta de aproveitamento do ano, em pontos percentuais (RF-12, art. 18 §5º).
 * Em 2026 não há meta, só registro (art. 18 §7º).
 */
export function metaDoAno(ano: number): string | null {
  if (ano <= 2026) return null;
  if (ano <= 2028) return "80";
  if (ano <= 2030) return "85";
  if (ano <= 2032) return "90";
  return "95";
}

/** Artigo da portaria por código de erro estável da API, para mostrar ao lado da regra que barrou. */
export const ARTIGO_DO_ERRO: Record<string, string> = {
  SALDO_INSUFICIENTE: "art. 8º, III",
  CREDITO_JA_TRANSFERIDO: "art. 8º, II e §3º",
  SEM_VINCULO: "art. 8º, II; art. 13 §1º VI",
  CHASSI_DUPLICADO: "arts. 28 e 29",
  CHASSI_JA_CONSUMIDO: "arts. 28 e 29",
  CHASSI_JA_CREDITADO: "art. 28",
  MMV_SEM_EFEITOS: "art. 5º §§2º e 3º",
  PENDENCIAS_CERTIFICADO: "art. 18 VIII; art. 8º I",
  PENDENCIAS_LAUDO: "art. 18 VII",
  PM_DIVERGENTE_NO_PERIODO: "art. 3º §4º",
  PESO_ACIMA_DA_ENTRADA: "art. 18 §§5º e 6º",
  RENAVAM_DUPLICADO: "art. 18 II; art. 21 III",
  CERTIDAO_BAIXA_DUPLICADA: "art. 18 II; art. 21 III",
  EVIDENCIA_REUTILIZADA: "art. 6º I c; art. 21 III",
  ITEM_SEGURANCA_NAO_REUTILIZAVEL: "Anexo III, item 7",
  AUDITOR_SOMENTE_LEITURA: "art. 24 V",
};
