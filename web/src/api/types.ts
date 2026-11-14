// Tipos escritos à mão a partir de docs/03-contrato-api.md.
// Na integração passam a ser gerados de /openapi.json (agents/03-frontend.md).
// Os tipos da fundação espelham os schemas já existentes; os de fluxo e URV seguem o contrato
// e a arquitetura, e podem precisar de ajuste fino quando os backends chegarem.
// Todo Decimal (URV, fator, preço, peso, percentual) é string.

export type Decimal = string;
/** Data ISO "AAAA-MM-DD". */
export type DataIso = string;
/** Data e hora ISO 8601. */
export type DataHoraIso = string;

export type Papel = "ADMIN" | "DESMONTADORA" | "RECICLADORA" | "FABRICANTE" | "AUDITOR";
export type TipoEmpresa = "FABRICANTE" | "DESMONTADORA" | "RECICLADORA";
export type CredenciamentoStatus = "PENDENTE" | "ATIVO" | "SUSPENSO" | "CANCELADO";
export type MmvStatus = "ATIVO" | "RETIRADO";
export type TipoVeiculo =
  | "LICENCIADO_RODAGEM"
  | "SINISTRADO_PEQUENA_MEDIA"
  | "SUCATA_APROVEITAVEL"
  | "SINISTRADO_GRANDE"
  | "SUCATA_MOTOR_INSERVIVEL"
  | "SUCATA_INSERVIVEL";
export type OrigemAquisicao = "COMPRA_DIRETA" | "LEILAO_ORGAO_PUBLICO" | "LEILAO_SEGURADORA";
export type DocumentoEntradaTipo = "NF_ENTRADA" | "AUTO_ARREMATACAO";
export type EstadoVeiculo = "RECEBIDO" | "EM_PROCESSO" | "LAUDO_EMITIDO" | "CERTIFICADO" | "ENCERRADO";
export type EtapaTipo = "RECEPCAO" | "DESCONTAMINACAO" | "DESMONTAGEM" | "DESTRUICAO" | "DESTINACAO";
export type AnexoTipo = "FOTO" | "DOCUMENTO_ENTRADA" | "CERTIDAO_BAIXA" | "EVIDENCIA_CLASSIFICACAO";
export type PecaClassificacao = "REUTILIZAVEL" | "NAO_REUTILIZAVEL";
export type PecaCondicao = "USADA" | "REMANUFATURADA";
export type PecaDestino =
  | "ESTOQUE"
  | "REVENDA"
  | "EXPORTACAO"
  | "REMANUFATURA"
  | "RECONDICIONAMENTO"
  | "RECICLAGEM"
  | "DESCARTE";
export type Fracao = "FERROSO" | "NAO_FERROSO" | "NAO_METALICO" | "FLUIDOS" | "BATERIAS" | "PNEUS";
export type DestinoPesagem = "REAPROVEITAMENTO" | "RECICLAGEM" | "RECUPERACAO_ENERGETICA" | "REJEITO";
export type UrvCreditoStatus = "DISPONIVEL" | "TRANSFERIDO";
export type LancamentoTipo = "CREDITO" | "TRANSFERENCIA_SAIDA" | "TRANSFERENCIA_ENTRADA" | "DEBITO";

export interface Pagina<T> {
  itens: T[];
  total: number;
}

/** Corpo de erro do contrato. `pendencias` só em 422 de pré-condição. */
export interface ErroApi {
  detail: string;
  codigo: string;
  pendencias?: string[];
}

// ---------- Fundação ----------

export interface EmpresaResumo {
  id: string;
  cnpj: string;
  razao_social: string;
  tipo: TipoEmpresa;
}

export interface Empresa extends EmpresaResumo {
  credenciamento_status: CredenciamentoStatus | null;
  credenciamento_validade: DataIso | null;
  registro_compromissos: boolean;
  criado_em: DataHoraIso;
  credenciamento_vigente: boolean;
}

export interface EmpresaCriar {
  cnpj: string;
  razao_social: string;
  tipo: TipoEmpresa;
  registro_compromissos?: boolean | null;
}

export interface Usuario {
  id: string;
  nome: string;
  email: string;
  papel: Papel;
  empresa: EmpresaResumo | null;
}

export interface LoginSaida {
  access_token: string;
  token_type: string;
  usuario: Usuario;
}

export interface Vinculo {
  id: string;
  geradora_id: string;
  fabricante_id: string;
  ativo: boolean;
  criado_em: DataHoraIso;
  geradora: EmpresaResumo;
  fabricante: EmpresaResumo;
}

export interface Evento {
  id: string;
  sequencia: number;
  ocorrido_em: DataHoraIso;
  usuario_id: string | null;
  empresa_id: string | null;
  tipo: string;
  entidade: string;
  entidade_id: string | null;
  payload: Record<string, unknown>;
  hash_anterior: string;
  hash: string;
}

export interface Verificacao {
  integra: boolean;
  total: number;
  primeira_quebra: number | null;
}

export interface Fator {
  tipo: TipoVeiculo;
  fator: Decimal;
  vigente_desde: DataIso;
}

export interface Fatores extends Pagina<Fator> {
  preco_base: Decimal;
}

// ---------- Fluxo do veículo ----------

export interface VeiculoCriar {
  chassi: string;
  placa: string;
  renavam: string;
  data_entrada: DataIso;
  tipo: TipoVeiculo;
  origem_aquisicao: OrigemAquisicao;
  documento_entrada_tipo: DocumentoEntradaTipo;
  documento_entrada_numero: string;
  certidao_baixa_numero: string;
  peso_entrada_kg: Decimal;
  sem_viabilidade_desmontagem: boolean;
}

export interface Veiculo extends VeiculoCriar {
  id: string;
  empresa_id: string;
  /** O tipo informado no cadastro. `tipo` é o efetivo, usado no fator (RF-07). */
  tipo_declarado: TipoVeiculo;
  estado: EstadoVeiculo;
  criado_em: DataHoraIso;
}

export interface Etapa {
  id: string;
  veiculo_id: string;
  tipo: EtapaTipo;
  iniciada_em: DataHoraIso;
  concluida_em: DataHoraIso | null;
  observacoes: string | null;
}

export interface EtapaEntrada {
  iniciada_em: DataHoraIso;
  concluida_em?: DataHoraIso | null;
  observacoes?: string | null;
}

export interface Anexo {
  id: string;
  veiculo_id: string;
  etapa_tipo: EtapaTipo;
  tipo: AnexoTipo;
  nome_arquivo?: string | null;
  sha256: string;
  criado_em: DataHoraIso;
}

export interface VeiculoDetalhe extends Veiculo {
  etapas: Etapa[];
  anexos: Anexo[];
  pendencias_certificado: string[];
  percentual_aproveitado: Decimal | null;
}

/** Conteúdo da etiqueta: nome, chassi, data e CNPJ (art. 18 V; Anexo III 6 a 8). */
export interface Etiqueta {
  nome: string;
  chassi: string;
  data: DataIso;
  cnpj: string;
  codigo: string;
}

export interface PecaCriar {
  nome: string;
  descricao: string;
  classificacao: PecaClassificacao;
  condicao: PecaCondicao;
  destino: PecaDestino;
}

export interface Peca extends PecaCriar {
  id: string;
  veiculo_id: string;
  chassi?: string;
  codigo_rastreio: string | null;
  etiqueta: Etiqueta | null;
  descaracterizada: boolean;
  criado_em: DataHoraIso;
}

/** Resposta pública de GET /pecas/rastreio/{codigo}. */
export interface Rastreio extends Etiqueta {
  destino: PecaDestino;
  condicao?: PecaCondicao;
  descricao?: string;
}

export interface PesagemCriar {
  fracao: Fracao;
  destino: DestinoPesagem;
  peso_kg: Decimal;
}

export interface Pesagem extends PesagemCriar {
  id: string;
  veiculo_id: string;
  criado_em: DataHoraIso;
}

export interface Pesagens extends Pagina<Pesagem> {
  percentual_aproveitado: Decimal | null;
}

export interface DmrCriar {
  numero: string;
  destinatario_nome: string;
  destinatario_cnpj: string;
  tipo_material: string;
  peso_kg: Decimal;
}

export interface Dmr extends DmrCriar {
  id: string;
  veiculo_id: string;
  mtr_numero: string;
  emitida_em: DataHoraIso;
}

export interface Laudo {
  id: string;
  veiculo_id: string;
  responsavel_nome: string;
  responsavel_registro: string;
  assinado_em: DataHoraIso;
  hash_conteudo: string;
}

export interface Certificado {
  id: string;
  veiculo_id: string;
  numero: string;
  empresa_id: string;
  tipo_veiculo: TipoVeiculo;
  fator: Decimal;
  percentual_aproveitado: Decimal | null;
  meta_ano: Decimal | null;
  atende_meta: boolean | null;
  emitido_em: DataHoraIso;
  hash_conteudo: string;
  credito?: Credito | null;
  laudo?: Laudo | null;
  veiculo?: Veiculo | null;
}

// ---------- URV e MMV ----------

export interface Credito {
  id: string;
  certificado_id: string;
  geradora_id: string;
  titular_id: string;
  quantidade: Decimal;
  status: UrvCreditoStatus;
  criado_em: DataHoraIso;
  certificado?: { id: string; numero: string; emitido_em?: DataHoraIso } | null;
  chassi?: string | null;
}

export interface Lancamento {
  id: string;
  empresa_id: string;
  tipo: LancamentoTipo;
  /** Com sinal: negativo em saída e débito. */
  quantidade: Decimal;
  credito_id: string | null;
  consumo_id: string | null;
  contraparte_id: string | null;
  criado_em: DataHoraIso;
}

export interface Saldo {
  saldo: Decimal;
  regularizar_ate?: DataIso | null;
}

export interface MmvCriar {
  codigo: string;
  ncm: string;
  nivel: 1 | 2;
  percentual_reciclabilidade: Decimal;
  ja_comercializado: boolean;
}

export interface Mmv extends MmvCriar {
  id: string;
  fabricante_id: string;
  efeitos_a_partir_de: DataIso;
  status: MmvStatus;
  rm: number;
  criado_em: DataHoraIso;
}

export interface SimulacaoEntrada {
  mmv_id: string;
  quantidade: number;
  preco_medio: Decimal;
}

export interface MemoriaCalculo {
  qv: number;
  rm: number;
  pm: Decimal;
  pb: Decimal;
  fator_preco: Decimal;
  formula: string;
  saldo_atual?: Decimal;
}

export interface Simulacao {
  urv_debito: Decimal;
  saldo_apos: Decimal;
  memoria_calculo: MemoriaCalculo;
}

export interface ConsumoCriar {
  mmv_id: string;
  /** AAAA-MM */
  periodo: string;
  preco_medio: Decimal;
  chassis: string[];
}

export interface Consumo {
  id: string;
  fabricante_id: string;
  mmv_id: string;
  periodo: string;
  qv: number;
  rm: number;
  pm: Decimal;
  pb: Decimal;
  urv_debito: Decimal;
  saldo_apos: Decimal;
  regularizar_ate: DataIso | null;
  prazo_reporte: DataIso;
  registrado_em: DataHoraIso;
  fora_do_prazo: boolean;
  chassis?: string[];
}

export interface MaterialRelatorio {
  fracao: Fracao;
  destino: DestinoPesagem;
  peso_kg: Decimal;
}

export interface RelatorioMdic {
  registros: number;
  certificados_emitidos: number;
  urv_gerada: Decimal;
  urv_transferida: Decimal;
  urv_consumida: Decimal;
  materiais: MaterialRelatorio[];
}
