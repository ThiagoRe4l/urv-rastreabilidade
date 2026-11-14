// Tipos da API, gerados de /openapi.json (npm run tipos → src/api/schema.d.ts).
// Este arquivo só dá nomes curtos aos schemas do backend; nada aqui é escrito à mão,
// exceto os aliases de data e o corpo de erro. Os nomes de campo que valem são os dos
// backends (PM-WEB-05, docs/03-contrato-api.md, "Formatos de resposta").
// Todo Decimal (URV, fator, preço, peso, percentual) é string.

import type { components } from "./schema";

type S = components["schemas"];

export type Decimal = string;
/** Data ISO "AAAA-MM-DD". */
export type DataIso = string;
/** Data e hora ISO 8601. */
export type DataHoraIso = string;

export type Papel = S["Papel"];
export type TipoEmpresa = S["TipoEmpresa"];
export type CredenciamentoStatus = S["CredenciamentoStatus"];
export type MmvStatus = S["MmvStatus"];
export type TipoVeiculo = S["TipoVeiculo"];
export type OrigemAquisicao = S["OrigemAquisicao"];
export type DocumentoEntradaTipo = S["DocumentoEntradaTipo"];
export type EstadoVeiculo = S["EstadoVeiculo"];
export type EtapaTipo = S["EtapaTipo"];
export type AnexoTipo = S["AnexoTipo"];
export type PecaClassificacao = S["PecaClassificacao"];
export type PecaCondicao = S["PecaCondicao"];
export type PecaDestino = S["PecaDestino"];
export type Fracao = S["Fracao"];
export type DestinoPesagem = S["DestinoPesagem"];
export type UrvCreditoStatus = S["UrvCreditoStatus"];
export type LancamentoTipo = S["LancamentoTipo"];

export interface Pagina<T> {
  itens: T[];
  total: number;
}

/** Corpo de erro do contrato. `pendencias` só em 422 de pré-condição. */
export interface ErroApi {
  detail: string;
  codigo: string;
  pendencias?: string[] | null;
}

// ---------- Fundação ----------
export type EmpresaResumo = S["EmpresaResumo"];
export type Empresa = S["EmpresaSaida"];
export type EmpresaCriar = S["EmpresaCriar"];
export type Usuario = S["UsuarioSaida"];
export type LoginSaida = S["LoginSaida"];
export type Vinculo = S["VinculoSaida"];
export type Evento = S["EventoSaida"];
export type Verificacao = S["VerificacaoSaida"];
export type Fator = S["FatorSaida"];
export type Fatores = S["FatoresSaida"];

// ---------- Fluxo do veículo ----------
export type VeiculoCriar = S["VeiculoCriar"];
export type Veiculo = S["VeiculoSaida"];
export type VeiculoDetalhe = S["VeiculoDetalhe"];
export type Etapa = S["EtapaSaida"];
export type EtapaEntrada = S["EtapaEntrada"];
export type Anexo = S["AnexoSaida"];
/** Conteúdo da etiqueta: nome, chassi, data e CNPJ (art. 18 V; Anexo III 6 a 8). */
export type Etiqueta = S["Etiqueta"];
export type PecaCriar = S["PecaCriar"];
export type Peca = S["PecaSaida"];
/** Resposta pública de GET /pecas/rastreio/{codigo}: só a etiqueta e o destino. */
export type Rastreio = S["RastreioSaida"];
export type PesagemCriar = S["PesagemCriar"];
export type Pesagem = S["PesagemSaida"];
export type Pesagens = S["PesagensSaida"];
export type DmrCriar = S["DmrCriar"];
export type Dmr = S["DmrSaida"];
export type Laudo = S["LaudoSaida"];
export type Certificado = S["CertificadoSaida"];
export type CertificadoDetalhe = S["CertificadoDetalhe"];
export type CreditoResumo = S["CreditoResumo"];

// ---------- URV e MMV ----------
export type Credito = S["CreditoSaida"];
export type Lancamento = S["LancamentoSaida"];
export type Saldo = S["SaldoSaida"];
export type MmvCriar = S["MmvCriar"];
export type Mmv = S["MmvSaida"];
export type SimulacaoEntrada = S["ConsumoSimular"];
export type MemoriaCalculo = S["MemoriaCalculo"];
export type Simulacao = S["SimulacaoSaida"];
export type ConsumoCriar = S["ConsumoCriar"];
export type Consumo = S["ConsumoSaida"];
export type MaterialRelatorio = S["MaterialSaida"];
export type RelatorioMdic = S["RelatorioMdicSaida"];
export type ResultadoImportacao = S["ResultadoImportacao"];
