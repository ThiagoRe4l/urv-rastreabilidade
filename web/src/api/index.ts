// Uma função por rota do contrato (docs/03-contrato-api.md).

import { api, apiBlob, patch, post, put, qs } from "./cliente";
import type * as T from "./types";

/** Tamanho máximo de página aceito pela API. As listas do MVP cabem em uma página. */
const TUDO = { tamanho: 100 };

// ---------- Fundação ----------
export const listarEmpresas = (tipo?: T.TipoEmpresa) => api<T.Pagina<T.Empresa>>(`/empresas${qs({ tipo, ...TUDO })}`);
export const criarEmpresa = (dados: T.EmpresaCriar) => post<T.Empresa>("/empresas", dados);
export const atualizarEmpresa = (id: string, registro_compromissos: boolean) =>
  patch<T.Empresa>(`/empresas/${id}`, { registro_compromissos });
export const atualizarCredenciamento = (id: string, status: T.CredenciamentoStatus, validade: string | null) =>
  patch<T.Empresa>(`/empresas/${id}/credenciamento`, { status, validade });
export const listarVinculos = () => api<T.Pagina<T.Vinculo>>(`/vinculos${qs(TUDO)}`);
export const criarVinculo = (geradora_id: string, fabricante_id: string) =>
  post<T.Vinculo>("/vinculos", { geradora_id, fabricante_id });
export const atualizarVinculo = (id: string, ativo: boolean) => patch<T.Vinculo>(`/vinculos/${id}`, { ativo });
export const listarEventos = (filtros: {
  entidade?: string;
  entidade_id?: string;
  tipo?: string;
  pagina?: number;
  tamanho?: number;
}) => api<T.Pagina<T.Evento>>(`/auditoria/eventos${qs(filtros)}`);
export const verificarCadeia = () => api<T.Verificacao>("/auditoria/verificar");
export const obterFatores = () => api<T.Fatores>("/configuracao/fatores");

// ---------- Fluxo do veículo ----------
export const listarVeiculos = (filtros: { estado?: string; chassi?: string } = {}) =>
  api<T.Pagina<T.Veiculo>>(`/veiculos${qs({ ...filtros, ...TUDO })}`);
export const criarVeiculo = (dados: T.VeiculoCriar) => post<T.Veiculo>("/veiculos", dados);
export const obterVeiculo = (id: string) => api<T.VeiculoDetalhe>(`/veiculos/${id}`);
export function enviarAnexo(veiculoId: string, arquivo: File, tipo: T.AnexoTipo, etapa_tipo: T.EtapaTipo) {
  const corpo = new FormData();
  corpo.set("arquivo", arquivo);
  corpo.set("tipo", tipo);
  corpo.set("etapa_tipo", etapa_tipo);
  return api<T.Anexo>(`/veiculos/${veiculoId}/anexos`, { method: "POST", body: corpo });
}
export const baixarAnexo = (id: string) => apiBlob(`/anexos/${id}/arquivo`);
export const salvarEtapa = (veiculoId: string, tipo: T.EtapaTipo, dados: T.EtapaEntrada) =>
  put<T.Etapa>(`/veiculos/${veiculoId}/etapas/${tipo}`, dados);
export const criarPeca = (veiculoId: string, dados: T.PecaCriar) =>
  post<T.Peca>(`/veiculos/${veiculoId}/pecas`, dados);
export const atualizarPeca = (id: string, dados: { destino?: T.PecaDestino; descaracterizada?: boolean }) =>
  patch<T.Peca>(`/pecas/${id}`, dados);
export const listarPecas = (
  filtros: {
    veiculo_id?: string;
    chassi?: string;
    nome?: string;
    condicao?: string;
    destino?: string;
    classificacao?: string;
  } = {},
) => api<T.Pagina<T.Peca>>(`/pecas${qs({ ...filtros, ...TUDO })}`);
export const rastrearPeca = (codigo: string) => api<T.Rastreio>(`/pecas/rastreio/${encodeURIComponent(codigo)}`);
export const criarPesagem = (veiculoId: string, dados: T.PesagemCriar) =>
  post<T.Pesagem>(`/veiculos/${veiculoId}/pesagens`, dados);
export const listarPesagens = (veiculoId: string) => api<T.Pesagens>(`/veiculos/${veiculoId}/pesagens${qs(TUDO)}`);
export const criarDmr = (veiculoId: string, dados: T.DmrCriar) => post<T.Dmr>(`/veiculos/${veiculoId}/dmrs`, dados);
export const listarDmrs = (veiculoId: string) => api<T.Pagina<T.Dmr>>(`/veiculos/${veiculoId}/dmrs${qs(TUDO)}`);
export const assinarLaudo = (veiculoId: string, responsavel_nome: string, responsavel_registro: string) =>
  post<T.Laudo>(`/veiculos/${veiculoId}/laudo`, { responsavel_nome, responsavel_registro });
/** PM-WEB-03: o laudo do veículo, antes ou depois do certificado. 404 se ainda não foi assinado. */
export const obterLaudo = (veiculoId: string) => api<T.Laudo>(`/veiculos/${veiculoId}/laudo`);
export const emitirCertificado = (veiculoId: string) => post<T.Certificado>(`/veiculos/${veiculoId}/certificado`);
export const listarCertificados = (empresa_id?: string) =>
  api<T.Pagina<T.Certificado>>(`/certificados${qs({ empresa_id, ...TUDO })}`);
export const obterCertificado = (id: string) => api<T.CertificadoDetalhe>(`/certificados/${id}`);

// ---------- URV e MMV ----------
export const criarMmv = (dados: T.MmvCriar) => post<T.Mmv>("/mmvs", dados);
export const listarMmvs = () => api<T.Pagina<T.Mmv>>(`/mmvs${qs(TUDO)}`);
export const obterSaldo = () => api<T.Saldo>("/urv/saldo");
export const listarExtrato = (empresa_id?: string) =>
  api<T.Pagina<T.Lancamento>>(`/urv/extrato${qs({ empresa_id, ...TUDO })}`);
export const listarCreditos = (status?: T.UrvCreditoStatus) =>
  api<T.Pagina<T.Credito>>(`/urv/creditos${qs({ status, ...TUDO })}`);
export const transferirCredito = (id: string, fabricante_id: string) =>
  post<T.Credito>(`/urv/creditos/${id}/transferir`, { fabricante_id });
export const simularConsumo = (dados: T.SimulacaoEntrada) => post<T.Simulacao>("/urv/consumos/simular", dados);
export const criarConsumo = (dados: T.ConsumoCriar) => post<T.Consumo>("/urv/consumos", dados);
/** PM-WEB-06: `chassi` acha o consumo em que um chassi de veículo novo foi usado (busca exata). */
export const listarConsumos = (filtros: { chassi?: string } = {}) =>
  api<T.Pagina<T.Consumo>>(`/urv/consumos${qs({ ...filtros, ...TUDO })}`);
export const obterRelatorio = (ano?: number) => api<T.RelatorioMdic>(`/relatorios/mdic${qs({ ano })}`);
export const exportarHistorico = () => apiBlob("/portabilidade/exportar");
