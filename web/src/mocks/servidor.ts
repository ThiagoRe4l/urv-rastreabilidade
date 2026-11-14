// Backend simulado em memória, usado com VITE_MOCK=1 (npm run dev:mock) para demonstrar sem backend.
// Desde a integração, as respostas têm a forma dos schemas reais (src/api/schema.d.ts, gerado de
// /openapi.json): se o backend mudar um campo, o mock deixa de compilar.
// É uma função pura (requisição → resposta), sem dependência do MSW, para poder ser testada em Node.
// Segue docs/03-contrato-api.md e as regras de docs/02-arquitetura.md. Não é a fonte de verdade
// de nenhuma regra: o backend real decide; aqui só há o suficiente para o roteiro de demonstração.

import type * as T from "../api/types";
import { deEscala, dividirHalfUp, paraEscala } from "../lib/decimal";
import { metaDoAno } from "../lib/dominio";
import { cnpjValido, hojeIso } from "../lib/formato";

export interface Armazenamento {
  ler(): string | null;
  gravar(texto: string): void;
}

export interface Requisicao {
  metodo: string;
  /** Sem o prefixo /api/v1. */
  caminho: string;
  consulta?: URLSearchParams;
  corpo?: unknown;
  token?: string | null;
}

export interface Resposta {
  status: number;
  corpo: unknown;
}

interface UsuarioReg {
  id: string;
  nome: string;
  email: string;
  senha: string;
  papel: T.Papel;
  empresa_id: string | null;
}

type EmpresaReg = Omit<T.Empresa, "credenciamento_vigente">;
type VinculoReg = Omit<T.Vinculo, "geradora" | "fabricante">;
type CreditoReg = Omit<T.Credito, "certificado" | "chassi" | "geradora" | "titular">;
type CertificadoReg = Omit<T.Certificado, "credito">;
type ConsumoReg = Omit<T.Consumo, "fora_do_prazo" | "mmv_codigo">;
type LancamentoReg = Omit<T.Lancamento, "contraparte">;
/** `rebaixado` é calculado no backend (só leitura no schema); aqui é guardado e atualizado. */
type VeiculoReg = Omit<T.Veiculo, "rebaixado"> & { rebaixado: boolean };

interface Estado {
  versao: number;
  empresas: EmpresaReg[];
  usuarios: UsuarioReg[];
  vinculos: VinculoReg[];
  mmvs: T.Mmv[];
  veiculos: VeiculoReg[];
  etapas: T.Etapa[];
  anexos: T.Anexo[];
  pecas: T.Peca[];
  pesagens: T.Pesagem[];
  dmrs: T.Dmr[];
  laudos: T.Laudo[];
  certificados: CertificadoReg[];
  creditos: CreditoReg[];
  lancamentos: LancamentoReg[];
  consumos: ConsumoReg[];
  eventos: T.Evento[];
}

const VERSAO = 2;
// Art. 3º §2º.
const FATORES: Record<T.TipoVeiculo, string> = {
  LICENCIADO_RODAGEM: "1.00",
  SINISTRADO_PEQUENA_MEDIA: "0.94",
  SUCATA_APROVEITAVEL: "0.85",
  SINISTRADO_GRANDE: "0.79",
  SUCATA_MOTOR_INSERVIVEL: "0.68",
  SUCATA_INSERVIVEL: "0.38",
};
const PRECO_BASE = "150000.00"; // art. 3º §5º
const FIM_SALDO_NEGATIVO = "2027-12-31"; // art. 8º §1º
const VIGENCIA = "2026-11-09";

export const ID_DESMONTADORA = "00000000-0000-4000-8000-000000000001";
export const ID_FABRICANTE = "00000000-0000-4000-8000-000000000002";

class Falha extends Error {
  constructor(
    public status: number,
    public codigo: string,
    detail: string,
    public pendencias?: string[],
  ) {
    super(detail);
  }
}

function uuid(): string {
  return crypto.randomUUID();
}

/** Hash de demonstração com 64 hexadecimais. Não é SHA-256; só precisa mudar quando o conteúdo muda. */
export function hashFalso(texto: string): string {
  let saida = "";
  for (let semente = 0; semente < 8; semente++) {
    let h = (0x811c9dc5 ^ (semente * 0x9e3779b1)) >>> 0;
    for (let i = 0; i < texto.length; i++) {
      h ^= texto.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    saida += h.toString(16).padStart(8, "0");
  }
  return saida;
}

function semente(agora: Date): Estado {
  const criado_em = agora.toISOString();
  const validade = `${agora.getFullYear() + 2}-${hojeIso(agora).slice(5)}`;
  const usuario = (n: number, nome: string, email: string, papel: T.Papel, empresa_id: string | null): UsuarioReg => ({
    id: `00000000-0000-4000-8000-0000000001${String(n).padStart(2, "0")}`,
    nome,
    email,
    senha: "demo1234",
    papel,
    empresa_id,
  });
  return {
    versao: VERSAO,
    empresas: [
      {
        id: ID_DESMONTADORA,
        cnpj: "11222333000181",
        razao_social: "Desmonte Paraná S.A.",
        tipo: "DESMONTADORA",
        credenciamento_status: "ATIVO",
        credenciamento_validade: validade,
        registro_compromissos: false,
        criado_em,
      },
      {
        id: ID_FABRICANTE,
        cnpj: "11444777000161",
        razao_social: "Montadora Exemplo S.A.",
        tipo: "FABRICANTE",
        credenciamento_status: null,
        credenciamento_validade: null,
        registro_compromissos: true,
        criado_em,
      },
    ],
    usuarios: [
      usuario(1, "Administrador", "admin@urv.local", "ADMIN", null),
      usuario(2, "Auditor MDIC", "auditor@mdic.local", "AUDITOR", null),
      usuario(3, "Operador da desmontadora", "operador@desmonte.local", "DESMONTADORA", ID_DESMONTADORA),
      usuario(4, "Fiscal da montadora", "fiscal@montadora.local", "FABRICANTE", ID_FABRICANTE),
    ],
    vinculos: [
      {
        id: "00000000-0000-4000-8000-000000000201",
        geradora_id: ID_DESMONTADORA,
        fabricante_id: ID_FABRICANTE,
        ativo: true,
        criado_em,
      },
    ],
    mmvs: [],
    veiculos: [],
    etapas: [],
    anexos: [],
    pecas: [],
    pesagens: [],
    dmrs: [],
    laudos: [],
    certificados: [],
    creditos: [],
    lancamentos: [],
    consumos: [],
    eventos: [],
  };
}

interface Ctx {
  e: Estado;
  u: UsuarioReg | null;
  consulta: URLSearchParams;
  corpo: Record<string, unknown>;
  agora: Date;
  arquivos: Map<string, Blob>;
}

type Manipulador = (c: Ctx, ...params: string[]) => unknown;

// ---------- utilitários ----------

function exigir(c: Ctx, ...papeis: T.Papel[]): UsuarioReg {
  if (!c.u) throw new Falha(401, "NAO_AUTENTICADO", "Não autenticado");
  if (papeis.length && !papeis.includes(c.u.papel)) {
    throw new Falha(403, "SEM_PERMISSAO", "Seu papel não permite esta operação");
  }
  return c.u;
}

function texto(c: Ctx, campo: string, obrigatorio = true): string {
  const v = c.corpo[campo];
  const s = v === undefined || v === null ? "" : String(v).trim();
  if (!s && obrigatorio) throw new Falha(422, "VALIDACAO", `Campo obrigatório: ${campo}`);
  return s;
}

function umDe<V extends string>(c: Ctx, campo: string, valores: readonly V[]): V {
  const s = texto(c, campo) as V;
  if (!valores.includes(s)) throw new Falha(422, "VALIDACAO", `Valor inválido em ${campo}: ${s}`);
  return s;
}

function decimal(c: Ctx, campo: string, casas: number, positivo = true): string {
  let n: bigint;
  try {
    n = paraEscala(texto(c, campo), casas);
  } catch {
    throw new Falha(422, "VALIDACAO", `Número inválido em ${campo}`);
  }
  if (positivo && n <= 0n) throw new Falha(422, "VALIDACAO", `${campo} deve ser maior que zero`);
  return deEscala(n, casas);
}

function paginar<X>(c: Ctx, itens: X[]): T.Pagina<X> {
  const pagina = Math.max(1, Number(c.consulta.get("pagina") ?? 1) || 1);
  const tamanho = Math.min(100, Math.max(1, Number(c.consulta.get("tamanho") ?? 20) || 20));
  return { itens: itens.slice((pagina - 1) * tamanho, pagina * tamanho), total: itens.length };
}

function achar<X extends { id: string }>(lista: X[], id: string, nome: string): X {
  const item = lista.find((x) => x.id === id);
  if (!item) throw new Falha(404, "NAO_ENCONTRADO", `${nome} não encontrado`);
  return item;
}

function verEmpresa(e: EmpresaReg, agora: Date): T.Empresa {
  return {
    ...e,
    credenciamento_vigente:
      e.credenciamento_status === "ATIVO" &&
      e.credenciamento_validade !== null &&
      e.credenciamento_validade >= hojeIso(agora),
  };
}

function resumo(c: Ctx, id: string): T.EmpresaResumo {
  const { cnpj, razao_social, tipo } = achar(c.e.empresas, id, "Empresa");
  return { id, cnpj, razao_social, tipo };
}

function verUsuario(c: Ctx, u: UsuarioReg): T.Usuario {
  return {
    id: u.id,
    nome: u.nome,
    email: u.email,
    papel: u.papel,
    empresa: u.empresa_id ? resumo(c, u.empresa_id) : null,
  };
}

function verVinculo(c: Ctx, v: VinculoReg): T.Vinculo {
  return { ...v, geradora: resumo(c, v.geradora_id), fabricante: resumo(c, v.fabricante_id) };
}

/** RF-22: evento encadeado pelo hash do anterior. */
function registrar(
  c: Ctx,
  tipo: string,
  entidade: string,
  entidade_id: string | null,
  payload: Record<string, unknown>,
) {
  const anterior = c.e.eventos[c.e.eventos.length - 1];
  const base = {
    ocorrido_em: c.agora.toISOString(),
    usuario_id: c.u?.id ?? null,
    empresa_id: c.u?.empresa_id ?? null,
    tipo,
    entidade,
    entidade_id,
    payload,
  };
  const hash_anterior = anterior ? anterior.hash : "0".repeat(64);
  c.e.eventos.push({
    id: uuid(),
    sequencia: (anterior?.sequencia ?? 0) + 1,
    ...base,
    hash_anterior,
    hash: hashEvento(hash_anterior, base),
  });
}

function hashEvento(hash_anterior: string, ev: Omit<T.Evento, "id" | "sequencia" | "hash" | "hash_anterior">): string {
  return hashFalso(
    hash_anterior +
      JSON.stringify([ev.ocorrido_em, ev.usuario_id, ev.empresa_id, ev.tipo, ev.entidade, ev.entidade_id, ev.payload]),
  );
}

function saldoDe(c: Ctx, empresaId: string): bigint {
  return c.e.lancamentos
    .filter((l) => l.empresa_id === empresaId)
    .reduce((soma, l) => soma + paraEscala(l.quantidade, 2), 0n);
}

function lancar(
  c: Ctx,
  empresa_id: string,
  tipo: T.LancamentoTipo,
  quantidade: string,
  extra: Partial<Pick<LancamentoReg, "credito_id" | "consumo_id" | "contraparte_id">>,
) {
  c.e.lancamentos.push({
    id: uuid(),
    empresa_id,
    tipo,
    quantidade,
    credito_id: null,
    consumo_id: null,
    contraparte_id: null,
    criado_em: c.agora.toISOString(),
    ...extra,
  });
}

// ---------- veículo ----------

/** Veículo visível ao usuário; `escrita` exige ser a geradora dona. */
function veiculoDe(c: Ctx, id: string, escrita: boolean): VeiculoReg {
  const u = escrita ? exigir(c, "DESMONTADORA", "RECICLADORA") : exigir(c, "DESMONTADORA", "RECICLADORA", "AUDITOR", "ADMIN");
  const v = achar(c.e.veiculos, id, "Veículo");
  if (u.empresa_id && v.empresa_id !== u.empresa_id) throw new Falha(404, "NAO_ENCONTRADO", "Veículo não encontrado");
  return v;
}

/** RF-12: soma dos pesos com destino diferente de REJEITO sobre o total, em pontos de 0 a 100. */
function percentualAproveitado(c: Ctx, veiculoId: string): string | null {
  const pesagens = c.e.pesagens.filter((p) => p.veiculo_id === veiculoId);
  const total = pesagens.reduce((s, p) => s + paraEscala(p.peso_kg, 3), 0n);
  if (total === 0n) return null;
  const aproveitado = pesagens
    .filter((p) => p.destino !== "REJEITO")
    .reduce((s, p) => s + paraEscala(p.peso_kg, 3), 0n);
  return deEscala(dividirHalfUp(aproveitado * 10000n, total), 2);
}

/** RF-15: pré-condições do certificado (arquitetura, "Pré-condições do certificado"). */
function pendenciasCertificado(c: Ctx, v: T.Veiculo): string[] {
  if (c.e.certificados.some((x) => x.veiculo_id === v.id)) return [];
  const faltas: string[] = [];
  const empresa = verEmpresa(achar(c.e.empresas, v.empresa_id, "Empresa"), c.agora);
  if (!empresa.credenciamento_vigente) faltas.push("Credenciamento da empresa não está ativo ou está vencido");
  const concluida = (t: T.EtapaTipo) =>
    c.e.etapas.some((x) => x.veiculo_id === v.id && x.tipo === t && x.concluida_em !== null);
  const tem = (tipo: T.AnexoTipo, etapa?: T.EtapaTipo) =>
    c.e.anexos.some((a) => a.veiculo_id === v.id && a.tipo === tipo && (!etapa || a.etapa_tipo === etapa));

  if (!concluida("RECEPCAO")) faltas.push("Etapa de recepção não concluída");
  if (!tem("DOCUMENTO_ENTRADA")) faltas.push("Falta anexar o documento de entrada (nota fiscal ou auto de arrematação)");
  if (!tem("CERTIDAO_BAIXA")) faltas.push("Falta anexar a certidão de baixa");
  if (!tem("FOTO", "RECEPCAO")) faltas.push("Falta ao menos uma foto da recepção");
  if (!concluida("DESCONTAMINACAO")) faltas.push("Etapa de descontaminação não concluída");
  if (!tem("FOTO", "DESCONTAMINACAO")) faltas.push("Falta ao menos uma foto da descontaminação");
  if (!v.sem_viabilidade_desmontagem) {
    if (!concluida("DESMONTAGEM")) faltas.push("Etapa de desmontagem não concluída");
    if (!tem("FOTO", "DESMONTAGEM")) faltas.push("Falta ao menos uma foto da desmontagem");
  }
  const pecas = c.e.pecas.filter((p) => p.veiculo_id === v.id);
  if (pecas.some((p) => p.classificacao === "REUTILIZAVEL" && !p.codigo_rastreio)) {
    faltas.push("Há peça reutilizável sem código de rastreio");
  }
  const naoDescaracterizadas = pecas.filter((p) => p.classificacao === "NAO_REUTILIZAVEL" && !p.descaracterizada);
  if (naoDescaracterizadas.length) {
    faltas.push(`Peça não reutilizável sem descaracterização: ${naoDescaracterizadas.map((p) => p.nome).join(", ")}`);
  }
  if (!concluida("DESTRUICAO")) faltas.push("Etapa de destruição não concluída");
  if (!c.e.pesagens.some((p) => p.veiculo_id === v.id)) faltas.push("Falta ao menos uma pesagem de material");
  if (!tem("FOTO", "DESTRUICAO")) faltas.push("Falta ao menos uma foto da destruição e separação dos materiais");
  if (!c.e.laudos.some((l) => l.veiculo_id === v.id)) faltas.push("Falta o laudo assinado pelo responsável técnico");
  return faltas;
}

function atualizarEstado(c: Ctx, v: T.Veiculo) {
  const certificado = c.e.certificados.some((x) => x.veiculo_id === v.id);
  const destinado =
    c.e.etapas.some((x) => x.veiculo_id === v.id && x.tipo === "DESTINACAO" && x.concluida_em !== null) &&
    c.e.dmrs.some((d) => d.veiculo_id === v.id);
  if (certificado) v.estado = destinado ? "ENCERRADO" : "CERTIFICADO";
  else if (c.e.laudos.some((l) => l.veiculo_id === v.id)) v.estado = "LAUDO_EMITIDO";
  else if (v.estado === "RECEBIDO") v.estado = "EM_PROCESSO";
}

function verCredito(c: Ctx, cr: CreditoReg): T.Credito {
  const cert = achar(c.e.certificados, cr.certificado_id, "Certificado");
  return {
    ...cr,
    certificado: {
      id: cert.id,
      numero: cert.numero,
      tipo_veiculo: cert.tipo_veiculo,
      fator: cert.fator,
      emitido_em: cert.emitido_em,
    },
    chassi: cert.chassi,
    geradora: resumo(c, cr.geradora_id),
    titular: resumo(c, cr.titular_id),
  };
}

function resumoCredito(c: Ctx, certificadoId: string): T.CreditoResumo | null {
  const cr = c.e.creditos.find((x) => x.certificado_id === certificadoId);
  return cr
    ? { id: cr.id, quantidade: cr.quantidade, status: cr.status, geradora_id: cr.geradora_id, titular_id: cr.titular_id }
    : null;
}

function verCertificado(c: Ctx, cert: CertificadoReg): T.Certificado {
  return { ...cert, credito: resumoCredito(c, cert.id) };
}

// ---------- consumo ----------

function mmvDoFabricante(c: Ctx, u: UsuarioReg): T.Mmv {
  const mmv = achar(c.e.mmvs, texto(c, "mmv_id"), "MMV");
  if (mmv.fabricante_id !== u.empresa_id) throw new Falha(404, "NAO_ENCONTRADO", "MMV não encontrado");
  return mmv;
}

/** RF-18: urv_debito = (qv / rm) * max(1, pm / pb), em 0.01, ROUND_HALF_UP. */
export function calcularDebito(
  qv: number,
  rm: number,
  pm: string,
  pb: string,
): { debito: string; razao_preco: string; multiplicador: string } {
  const pmC = paraEscala(pm, 2);
  const pbC = paraEscala(pb, 2);
  const maior = pmC > pbC ? pmC : pbC;
  return {
    debito: deEscala(dividirHalfUp(BigInt(qv) * maior * 100n, BigInt(rm) * pbC), 2),
    razao_preco: deEscala(dividirHalfUp(pmC * 10000n, pbC), 4),
    multiplicador: deEscala(dividirHalfUp(maior * 10000n, pbC), 4),
  };
}

/** RF-20: décimo dia útil (segunda a sexta, sem feriados) do mês seguinte ao período. */
export function prazoReporte(periodo: string): string {
  const [ano, mes] = periodo.split("-").map(Number);
  const dia = new Date(ano, mes, 1); // `mes` já é o mês seguinte em base zero
  let uteis = 0;
  for (;;) {
    const semana = dia.getDay();
    if (semana !== 0 && semana !== 6 && ++uteis === 10) return hojeIso(dia);
    dia.setDate(dia.getDate() + 1);
  }
}

/** RF-19: último dia do terceiro mês seguinte ao do registro. */
export function regularizarAte(registro: Date): string {
  return hojeIso(new Date(registro.getFullYear(), registro.getMonth() + 4, 0));
}

function verConsumo(c: Ctx, x: ConsumoReg): T.Consumo {
  const mmv = c.e.mmvs.find((m) => m.id === x.mmv_id);
  return { ...x, mmv_codigo: mmv?.codigo ?? "", fora_do_prazo: x.registrado_em.slice(0, 10) > x.prazo_reporte };
}

// ---------- rotas ----------

const ROTAS: [string, RegExp, Manipulador][] = [
  [
    "POST",
    /^\/auth\/login$/,
    (c) => {
      const email = texto(c, "email").toLowerCase();
      const u = c.e.usuarios.find((x) => x.email === email && x.senha === c.corpo.senha);
      if (!u) throw new Falha(401, "CREDENCIAIS_INVALIDAS", "E-mail ou senha incorretos");
      return { access_token: `mock.${u.id}`, token_type: "bearer", usuario: verUsuario(c, u) };
    },
  ],
  ["GET", /^\/auth\/me$/, (c) => verUsuario(c, exigir(c))],

  // ----- empresas e vínculos (RF-01, RF-02) -----
  [
    "POST",
    /^\/empresas$/,
    (c) => {
      exigir(c, "ADMIN");
      const cnpj = texto(c, "cnpj").replace(/\D/g, "");
      if (!cnpjValido(cnpj)) throw new Falha(422, "VALIDACAO", "CNPJ inválido");
      if (c.e.empresas.some((x) => x.cnpj === cnpj)) throw new Falha(409, "CNPJ_DUPLICADO", "Já existe empresa com este CNPJ");
      const tipo = umDe(c, "tipo", ["FABRICANTE", "DESMONTADORA", "RECICLADORA"] as const);
      const empresa: EmpresaReg = {
        id: uuid(),
        cnpj,
        razao_social: texto(c, "razao_social"),
        tipo,
        credenciamento_status: tipo === "FABRICANTE" ? null : "PENDENTE",
        credenciamento_validade: null,
        registro_compromissos: tipo === "FABRICANTE" && c.corpo.registro_compromissos === true,
        criado_em: c.agora.toISOString(),
      };
      c.e.empresas.push(empresa);
      registrar(c, "EMPRESA_CRIADA", "empresa", empresa.id, { cnpj, tipo });
      return verEmpresa(empresa, c.agora);
    },
  ],
  [
    "GET",
    /^\/empresas$/,
    (c) => {
      const u = exigir(c);
      let lista = c.e.empresas;
      if (u.empresa_id) {
        // Demais papéis veem só as contrapartes com vínculo.
        const contrapartes = c.e.vinculos
          .filter((v) => v.ativo && (v.geradora_id === u.empresa_id || v.fabricante_id === u.empresa_id))
          .map((v) => (v.geradora_id === u.empresa_id ? v.fabricante_id : v.geradora_id));
        lista = lista.filter((x) => contrapartes.includes(x.id));
      }
      const tipo = c.consulta.get("tipo");
      if (tipo) lista = lista.filter((x) => x.tipo === tipo);
      return paginar(c, lista.map((x) => verEmpresa(x, c.agora)));
    },
  ],
  [
    "PATCH",
    /^\/empresas\/([^/]+)$/,
    (c, id) => {
      exigir(c, "ADMIN");
      const empresa = achar(c.e.empresas, id, "Empresa");
      if (empresa.tipo !== "FABRICANTE") {
        throw new Falha(422, "EMPRESA_NAO_FABRICANTE", "Registro de compromissos só se aplica a fabricante");
      }
      empresa.registro_compromissos = c.corpo.registro_compromissos === true;
      registrar(c, "EMPRESA_ATUALIZADA", "empresa", id, { registro_compromissos: empresa.registro_compromissos });
      return verEmpresa(empresa, c.agora);
    },
  ],
  [
    "PATCH",
    /^\/empresas\/([^/]+)\/credenciamento$/,
    (c, id) => {
      exigir(c, "ADMIN");
      const empresa = achar(c.e.empresas, id, "Empresa");
      if (empresa.tipo === "FABRICANTE") {
        throw new Falha(422, "FABRICANTE_SEM_CREDENCIAMENTO", "Fabricante não tem credenciamento");
      }
      const status = umDe(c, "status", ["PENDENTE", "ATIVO", "SUSPENSO", "CANCELADO"] as const);
      const validade = texto(c, "validade", false) || null;
      if (status === "ATIVO" && !validade) throw new Falha(422, "VALIDACAO", "Validade obrigatória quando o status é ATIVO");
      empresa.credenciamento_status = status;
      empresa.credenciamento_validade = validade;
      registrar(c, "CREDENCIAMENTO_ATUALIZADO", "empresa", id, { status, validade });
      return verEmpresa(empresa, c.agora);
    },
  ],
  [
    "POST",
    /^\/vinculos$/,
    (c) => {
      exigir(c, "ADMIN");
      const geradora = achar(c.e.empresas, texto(c, "geradora_id"), "Geradora");
      const fabricante = achar(c.e.empresas, texto(c, "fabricante_id"), "Fabricante");
      if (geradora.tipo === "FABRICANTE" || fabricante.tipo !== "FABRICANTE") {
        throw new Falha(422, "VINCULO_INVALIDO", "O vínculo liga uma desmontadora ou recicladora a um fabricante");
      }
      if (c.e.vinculos.some((v) => v.geradora_id === geradora.id && v.fabricante_id === fabricante.id)) {
        throw new Falha(409, "VINCULO_DUPLICADO", "Este vínculo já existe");
      }
      const vinculo: VinculoReg = {
        id: uuid(),
        geradora_id: geradora.id,
        fabricante_id: fabricante.id,
        ativo: true,
        criado_em: c.agora.toISOString(),
      };
      c.e.vinculos.push(vinculo);
      registrar(c, "VINCULO_CRIADO", "vinculo", vinculo.id, { geradora_id: geradora.id, fabricante_id: fabricante.id });
      return verVinculo(c, vinculo);
    },
  ],
  [
    "GET",
    /^\/vinculos$/,
    (c) => {
      const u = exigir(c);
      const lista = c.e.vinculos.filter(
        (v) => !u.empresa_id || v.geradora_id === u.empresa_id || v.fabricante_id === u.empresa_id,
      );
      return paginar(c, lista.map((v) => verVinculo(c, v)));
    },
  ],
  [
    "PATCH",
    /^\/vinculos\/([^/]+)$/,
    (c, id) => {
      exigir(c, "ADMIN");
      const vinculo = achar(c.e.vinculos, id, "Vínculo");
      vinculo.ativo = c.corpo.ativo === true;
      registrar(c, "VINCULO_ATUALIZADO", "vinculo", id, { ativo: vinculo.ativo });
      return verVinculo(c, vinculo);
    },
  ],

  // ----- auditoria (RF-22, RF-23) -----
  [
    "GET",
    /^\/auditoria\/eventos$/,
    (c) => {
      exigir(c, "AUDITOR", "ADMIN");
      const filtro = (campo: "entidade" | "entidade_id" | "tipo") => {
        const valor = c.consulta.get(campo);
        return (ev: T.Evento) => !valor || ev[campo] === valor;
      };
      return paginar(c, c.e.eventos.filter(filtro("entidade")).filter(filtro("entidade_id")).filter(filtro("tipo")));
    },
  ],
  [
    "GET",
    /^\/auditoria\/verificar$/,
    (c) => {
      exigir(c, "AUDITOR", "ADMIN");
      let anterior = "0".repeat(64);
      for (const ev of c.e.eventos) {
        if (ev.hash_anterior !== anterior || ev.hash !== hashEvento(anterior, ev)) {
          return { integra: false, total: c.e.eventos.length, primeira_quebra: ev.sequencia };
        }
        anterior = ev.hash;
      }
      return { integra: true, total: c.e.eventos.length, primeira_quebra: null };
    },
  ],
  [
    "GET",
    /^\/configuracao\/fatores$/,
    (c) => {
      exigir(c);
      const itens = (Object.keys(FATORES) as T.TipoVeiculo[]).map((tipo) => ({
        tipo,
        fator: FATORES[tipo],
        vigente_desde: VIGENCIA,
      }));
      return { itens, total: itens.length, preco_base: PRECO_BASE };
    },
  ],

  // ----- veículos (RF-06 a RF-08) -----
  [
    "POST",
    /^\/veiculos$/,
    (c) => {
      const u = exigir(c, "DESMONTADORA", "RECICLADORA");
      const chassi = texto(c, "chassi").toUpperCase();
      if (!/^[A-HJ-NPR-Z0-9]{17}$/.test(chassi)) {
        throw new Falha(422, "VALIDACAO", "Chassi deve ter 17 caracteres (letras e números, sem I, O e Q)");
      }
      // RF-21, arts. 28 e 29
      if (c.e.veiculos.some((v) => v.chassi === chassi)) {
        throw new Falha(409, "CHASSI_DUPLICADO", `O chassi ${chassi} já foi registrado`);
      }
      const tipo_declarado = umDe(c, "tipo", Object.keys(FATORES) as T.TipoVeiculo[]);
      const veiculo: VeiculoReg = {
        id: uuid(),
        empresa_id: u.empresa_id!,
        chassi,
        placa: texto(c, "placa").toUpperCase(),
        renavam: texto(c, "renavam"),
        data_entrada: texto(c, "data_entrada"),
        tipo_declarado,
        // RF-07: sem evidência de classificação, todo tipo é tratado como sucata inservível.
        tipo: "SUCATA_INSERVIVEL",
        origem_aquisicao: umDe(c, "origem_aquisicao", ["COMPRA_DIRETA", "LEILAO_ORGAO_PUBLICO", "LEILAO_SEGURADORA"] as const),
        documento_entrada_tipo: umDe(c, "documento_entrada_tipo", ["NF_ENTRADA", "AUTO_ARREMATACAO"] as const),
        documento_entrada_numero: texto(c, "documento_entrada_numero"),
        certidao_baixa_numero: texto(c, "certidao_baixa_numero"),
        peso_entrada_kg: decimal(c, "peso_entrada_kg", 3),
        sem_viabilidade_desmontagem: c.corpo.sem_viabilidade_desmontagem === true,
        estado: "RECEBIDO",
        criado_em: c.agora.toISOString(),
        rebaixado: tipo_declarado !== "SUCATA_INSERVIVEL",
      };
      c.e.veiculos.push(veiculo);
      registrar(c, "VEICULO_RECEBIDO", "veiculo", veiculo.id, { chassi, tipo_declarado, tipo: veiculo.tipo });
      return veiculo;
    },
  ],
  [
    "GET",
    /^\/veiculos$/,
    (c) => {
      const u = exigir(c, "DESMONTADORA", "RECICLADORA", "AUDITOR", "ADMIN");
      const estado = c.consulta.get("estado");
      const chassi = c.consulta.get("chassi")?.toUpperCase();
      const lista = c.e.veiculos
        .filter((v) => !u.empresa_id || v.empresa_id === u.empresa_id)
        .filter((v) => !estado || v.estado === estado)
        .filter((v) => !chassi || v.chassi.includes(chassi));
      return paginar(c, [...lista].reverse());
    },
  ],
  [
    "GET",
    /^\/veiculos\/([^/]+)$/,
    (c, id): T.VeiculoDetalhe => {
      const v = veiculoDe(c, id, false);
      return {
        ...v,
        etapas: c.e.etapas.filter((x) => x.veiculo_id === id),
        anexos: c.e.anexos.filter((x) => x.veiculo_id === id),
        pendencias_certificado: pendenciasCertificado(c, v),
        percentual_aproveitado: percentualAproveitado(c, id),
        laudo_id: c.e.laudos.find((l) => l.veiculo_id === id)?.id ?? null,
        certificado_id: c.e.certificados.find((x) => x.veiculo_id === id)?.id ?? null,
      };
    },
  ],
  [
    "POST",
    /^\/veiculos\/([^/]+)\/anexos$/,
    (c, id) => {
      const v = veiculoDe(c, id, true);
      const arquivo = c.corpo.arquivo;
      if (!(arquivo instanceof Blob)) throw new Falha(422, "VALIDACAO", "Arquivo obrigatório");
      if (!/^image\/|^application\/pdf$/.test(arquivo.type)) {
        throw new Falha(422, "TIPO_DE_ARQUIVO_INVALIDO", "Envie uma imagem ou um PDF");
      }
      if (arquivo.size > 10 * 1024 * 1024) throw new Falha(413, "ARQUIVO_GRANDE", "O arquivo passa de 10 MB");
      const tipo = umDe(c, "tipo", ["FOTO", "DOCUMENTO_ENTRADA", "CERTIDAO_BAIXA", "EVIDENCIA_CLASSIFICACAO"] as const);
      const nome = arquivo instanceof File ? arquivo.name : "arquivo";
      const anexo: T.Anexo = {
        id: uuid(),
        veiculo_id: id,
        etapa_tipo: umDe(c, "etapa_tipo", ["RECEPCAO", "DESCONTAMINACAO", "DESMONTAGEM", "DESTRUICAO", "DESTINACAO"] as const),
        tipo,
        sha256: hashFalso(`${nome}:${arquivo.size}:${arquivo.type}`),
        nome_original: nome,
        content_type: arquivo.type || null,
        tamanho_bytes: arquivo.size,
        enviado_por: exigir(c).id,
        criado_em: c.agora.toISOString(),
      };
      c.e.anexos.push(anexo);
      c.arquivos.set(anexo.id, arquivo);
      // RF-07: a evidência aplica o tipo declarado.
      if (tipo === "EVIDENCIA_CLASSIFICACAO") {
        v.tipo = v.tipo_declarado;
        v.rebaixado = false;
      }
      registrar(c, "ANEXO_ADICIONADO", "veiculo", id, { anexo_id: anexo.id, tipo, etapa_tipo: anexo.etapa_tipo, sha256: anexo.sha256 });
      return anexo;
    },
  ],
  [
    "GET",
    /^\/anexos\/([^/]+)\/arquivo$/,
    (c, id) => {
      const anexo = achar(c.e.anexos, id, "Anexo");
      veiculoDe(c, anexo.veiculo_id, false);
      return (
        c.arquivos.get(id) ??
        new Blob(
          [
            `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="160"><rect width="100%" height="100%" fill="#eee"/>` +
              `<text x="24" y="70" font-family="sans-serif" font-size="16">Arquivo de demonstração</text>` +
              `<text x="24" y="100" font-family="sans-serif" font-size="13">O mock guarda os arquivos só até recarregar a página.</text></svg>`,
          ],
          { type: "image/svg+xml" },
        )
      );
    },
  ],
  [
    "PUT",
    /^\/veiculos\/([^/]+)\/etapas\/([^/]+)$/,
    (c, id, tipo) => {
      const v = veiculoDe(c, id, true);
      if (!["RECEPCAO", "DESCONTAMINACAO", "DESMONTAGEM", "DESTRUICAO", "DESTINACAO"].includes(tipo)) {
        throw new Falha(422, "VALIDACAO", "Etapa inválida");
      }
      const iniciada_em = texto(c, "iniciada_em");
      const concluida_em = texto(c, "concluida_em", false) || null;
      if (concluida_em && concluida_em < iniciada_em) {
        throw new Falha(422, "VALIDACAO", "A conclusão não pode ser anterior ao início");
      }
      let etapa = c.e.etapas.find((x) => x.veiculo_id === id && x.tipo === tipo);
      if (!etapa) {
        etapa = { id: uuid(), veiculo_id: id, tipo: tipo as T.EtapaTipo, iniciada_em, concluida_em: null, observacoes: null };
        c.e.etapas.push(etapa);
      }
      etapa.iniciada_em = iniciada_em;
      etapa.concluida_em = concluida_em;
      etapa.observacoes = texto(c, "observacoes", false) || null;
      atualizarEstado(c, v);
      registrar(c, "ETAPA_REGISTRADA", "veiculo", id, { etapa: tipo, iniciada_em, concluida_em });
      return etapa;
    },
  ],

  // ----- peças (RF-09, RF-10) -----
  [
    "POST",
    /^\/veiculos\/([^/]+)\/pecas$/,
    (c, id) => {
      const v = veiculoDe(c, id, true);
      const classificacao = umDe(c, "classificacao", ["REUTILIZAVEL", "NAO_REUTILIZAVEL"] as const);
      const nome = texto(c, "nome");
      const codigo = classificacao === "REUTILIZAVEL" ? `P${uuid().replace(/-/g, "").slice(0, 10).toUpperCase()}` : null;
      const peca: T.Peca = {
        id: uuid(),
        veiculo_id: id,
        chassi: v.chassi,
        nome,
        descricao: texto(c, "descricao", false),
        classificacao,
        condicao: umDe(c, "condicao", ["USADA", "REMANUFATURADA"] as const),
        destino: umDe(c, "destino", ["ESTOQUE", "REVENDA", "EXPORTACAO", "REMANUFATURA", "RECONDICIONAMENTO", "RECICLAGEM", "DESCARTE"] as const),
        codigo_rastreio: codigo,
        // Art. 18 V; Anexo III 6 a 8: nome, chassi, data e CNPJ.
        etiqueta: codigo
          ? { nome, chassi: v.chassi, data: hojeIso(c.agora), cnpj: resumo(c, v.empresa_id).cnpj, codigo }
          : null,
        descaracterizada: false,
        criado_em: c.agora.toISOString(),
      };
      c.e.pecas.push(peca);
      atualizarEstado(c, v);
      registrar(c, "PECA_REGISTRADA", "veiculo", id, { peca_id: peca.id, nome, classificacao, codigo_rastreio: codigo });
      return peca;
    },
  ],
  [
    "PATCH",
    /^\/pecas\/([^/]+)$/,
    (c, id) => {
      const peca = achar(c.e.pecas, id, "Peça");
      veiculoDe(c, peca.veiculo_id, true);
      if (c.corpo.destino !== undefined) {
        peca.destino = umDe(c, "destino", ["ESTOQUE", "REVENDA", "EXPORTACAO", "REMANUFATURA", "RECONDICIONAMENTO", "RECICLAGEM", "DESCARTE"] as const);
      }
      if (c.corpo.descaracterizada !== undefined) peca.descaracterizada = c.corpo.descaracterizada === true;
      registrar(c, "PECA_ATUALIZADA", "veiculo", peca.veiculo_id, {
        peca_id: id,
        destino: peca.destino,
        descaracterizada: peca.descaracterizada,
      });
      return peca;
    },
  ],
  [
    "GET",
    /^\/pecas$/,
    (c) => {
      const u = exigir(c, "DESMONTADORA", "RECICLADORA", "AUDITOR", "ADMIN");
      const visiveis = new Set(c.e.veiculos.filter((v) => !u.empresa_id || v.empresa_id === u.empresa_id).map((v) => v.id));
      const igual = (campo: "condicao" | "destino" | "classificacao") => {
        const valor = c.consulta.get(campo);
        return (p: T.Peca) => !valor || p[campo] === valor;
      };
      const chassi = c.consulta.get("chassi")?.toUpperCase();
      const nome = c.consulta.get("nome")?.toLowerCase();
      const veiculoId = c.consulta.get("veiculo_id");
      return paginar(
        c,
        c.e.pecas
          .filter((p) => visiveis.has(p.veiculo_id))
          .filter((p) => !veiculoId || p.veiculo_id === veiculoId)
          .filter((p) => !chassi || p.chassi.includes(chassi))
          .filter((p) => !nome || p.nome.toLowerCase().includes(nome))
          .filter(igual("condicao"))
          .filter(igual("destino"))
          .filter(igual("classificacao")),
      );
    },
  ],
  [
    "GET",
    /^\/pecas\/rastreio\/([^/]+)$/,
    (c, codigo): T.Rastreio => {
      // Rota pública: sem token.
      const peca = c.e.pecas.find((p) => p.codigo_rastreio === decodeURIComponent(codigo).toUpperCase());
      if (!peca?.etiqueta) throw new Falha(404, "NAO_ENCONTRADO", "Código de rastreio não encontrado");
      return { ...peca.etiqueta, destino: peca.destino };
    },
  ],

  // ----- pesagens e DMR (RF-11 a RF-13) -----
  [
    "POST",
    /^\/veiculos\/([^/]+)\/pesagens$/,
    (c, id) => {
      const v = veiculoDe(c, id, true);
      const pesagem: T.Pesagem = {
        id: uuid(),
        veiculo_id: id,
        fracao: umDe(c, "fracao", ["FERROSO", "NAO_FERROSO", "NAO_METALICO", "FLUIDOS", "BATERIAS", "PNEUS"] as const),
        destino: umDe(c, "destino", ["REAPROVEITAMENTO", "RECICLAGEM", "RECUPERACAO_ENERGETICA", "REJEITO"] as const),
        peso_kg: decimal(c, "peso_kg", 3),
        criado_em: c.agora.toISOString(),
      };
      c.e.pesagens.push(pesagem);
      atualizarEstado(c, v);
      registrar(c, "PESAGEM_REGISTRADA", "veiculo", id, { fracao: pesagem.fracao, destino: pesagem.destino, peso_kg: pesagem.peso_kg });
      return pesagem;
    },
  ],
  [
    "GET",
    /^\/veiculos\/([^/]+)\/pesagens$/,
    (c, id): T.Pesagens => {
      veiculoDe(c, id, false);
      const pesagens = c.e.pesagens.filter((p) => p.veiculo_id === id);
      const percentual = percentualAproveitado(c, id);
      const meta = metaDoAno(c.agora.getFullYear());
      return {
        itens: pesagens,
        total: pesagens.length,
        peso_total_kg: deEscala(
          pesagens.reduce((s, p) => s + paraEscala(p.peso_kg, 3), 0n),
          3,
        ),
        percentual_aproveitado: percentual,
        meta_ano: meta,
        atende_meta: meta && percentual ? paraEscala(percentual, 2) >= paraEscala(meta, 2) : null,
      };
    },
  ],
  [
    "POST",
    /^\/veiculos\/([^/]+)\/dmrs$/,
    (c, id) => {
      const v = veiculoDe(c, id, true);
      const destinatario_cnpj = texto(c, "destinatario_cnpj").replace(/\D/g, "");
      if (!cnpjValido(destinatario_cnpj)) throw new Falha(422, "VALIDACAO", "CNPJ do destinatário inválido");
      const dmr: T.Dmr = {
        id: uuid(),
        veiculo_id: id,
        numero: texto(c, "numero"),
        // MTR do SINIR simulado (RF-13).
        mtr_numero: `MTR-SIM-${String(c.e.dmrs.length + 1).padStart(6, "0")}`,
        destinatario_nome: texto(c, "destinatario_nome"),
        destinatario_cnpj,
        tipo_material: texto(c, "tipo_material"),
        peso_kg: decimal(c, "peso_kg", 3),
        emitida_em: c.agora.toISOString(),
      };
      c.e.dmrs.push(dmr);
      atualizarEstado(c, v);
      registrar(c, "DMR_EMITIDA", "veiculo", id, { numero: dmr.numero, mtr_numero: dmr.mtr_numero, peso_kg: dmr.peso_kg });
      return dmr;
    },
  ],
  [
    "GET",
    /^\/veiculos\/([^/]+)\/dmrs$/,
    (c, id) => {
      veiculoDe(c, id, false);
      return paginar(c, c.e.dmrs.filter((d) => d.veiculo_id === id));
    },
  ],

  // ----- laudo e certificado (RF-14 a RF-16) -----
  [
    "POST",
    /^\/veiculos\/([^/]+)\/laudo$/,
    (c, id) => {
      const v = veiculoDe(c, id, true);
      if (c.e.laudos.some((l) => l.veiculo_id === id)) throw new Falha(409, "LAUDO_JA_EMITIDO", "Este veículo já tem laudo");
      const faltas = (["DESCONTAMINACAO", "DESTRUICAO"] as const)
        .filter((t) => !c.e.etapas.some((x) => x.veiculo_id === id && x.tipo === t && x.concluida_em))
        .map((t) => (t === "DESCONTAMINACAO" ? "Etapa de descontaminação não concluída" : "Etapa de destruição não concluída"));
      if (faltas.length) {
        throw new Falha(422, "PENDENCIAS_LAUDO", "O laudo exige descontaminação e destruição concluídas", faltas);
      }
      const responsavel_nome = texto(c, "responsavel_nome");
      const responsavel_registro = texto(c, "responsavel_registro");
      const assinado_em = c.agora.toISOString();
      const laudo: T.Laudo = {
        id: uuid(),
        veiculo_id: id,
        responsavel_nome,
        responsavel_registro,
        assinado_em,
        hash_conteudo: hashFalso(JSON.stringify([v.chassi, responsavel_nome, responsavel_registro, assinado_em])),
        assinatura: { algoritmo: "SIMULADA-MOCK", valor: hashFalso(`${responsavel_registro}:${assinado_em}`) },
      };
      c.e.laudos.push(laudo);
      atualizarEstado(c, v);
      registrar(c, "LAUDO_ASSINADO", "veiculo", id, { laudo_id: laudo.id, hash_conteudo: laudo.hash_conteudo });
      return laudo;
    },
  ],
  [
    "GET",
    /^\/veiculos\/([^/]+)\/laudo$/,
    (c, id): T.Laudo => {
      veiculoDe(c, id, false);
      const laudo = c.e.laudos.find((l) => l.veiculo_id === id);
      if (!laudo) throw new Falha(404, "NAO_ENCONTRADO", "Laudo não encontrado");
      return laudo;
    },
  ],
  [
    "POST",
    /^\/veiculos\/([^/]+)\/certificado$/,
    (c, id) => {
      const v = veiculoDe(c, id, true);
      // RF-21: um chassi gera crédito uma vez.
      if (c.e.certificados.some((x) => x.veiculo_id === id)) {
        throw new Falha(409, "CERTIFICADO_JA_EMITIDO", "Este chassi já tem certificado emitido");
      }
      const pendencias = pendenciasCertificado(c, v);
      if (pendencias.length) {
        throw new Falha(422, "PENDENCIAS_CERTIFICADO", "O certificado ainda não pode ser emitido", pendencias);
      }
      const percentual = percentualAproveitado(c, id);
      const meta = metaDoAno(c.agora.getFullYear());
      const emitido_em = c.agora.toISOString();
      const numero = `CRV-${c.agora.getFullYear()}-${String(c.e.certificados.length + 1).padStart(6, "0")}`;
      const certificado: CertificadoReg = {
        id: uuid(),
        veiculo_id: id,
        chassi: v.chassi,
        numero,
        empresa_id: v.empresa_id,
        tipo_veiculo: v.tipo,
        fator: FATORES[v.tipo],
        percentual_aproveitado: percentual,
        meta_ano: meta,
        atende_meta: meta && percentual ? paraEscala(percentual, 2) >= paraEscala(meta, 2) : null,
        emitido_em,
        hash_conteudo: hashFalso(JSON.stringify([numero, v.chassi, v.tipo, emitido_em])),
      };
      c.e.certificados.push(certificado);
      // RF-16: crédito no valor do fator do veículo.
      const credito: CreditoReg = {
        id: uuid(),
        certificado_id: certificado.id,
        geradora_id: v.empresa_id,
        titular_id: v.empresa_id,
        quantidade: certificado.fator,
        status: "DISPONIVEL",
        criado_em: emitido_em,
      };
      c.e.creditos.push(credito);
      lancar(c, v.empresa_id, "CREDITO", credito.quantidade, { credito_id: credito.id });
      atualizarEstado(c, v);
      registrar(c, "CERTIFICADO_EMITIDO", "veiculo", id, { certificado_id: certificado.id, numero, fator: certificado.fator });
      registrar(c, "CREDITO_GERADO", "urv_credito", credito.id, { veiculo_id: id, chassi: v.chassi, quantidade: credito.quantidade });
      return verCertificado(c, certificado);
    },
  ],
  [
    "GET",
    /^\/certificados$/,
    (c) => {
      const u = exigir(c);
      const empresa = u.empresa_id ?? c.consulta.get("empresa_id");
      return paginar(
        c,
        c.e.certificados.filter((x) => !empresa || x.empresa_id === empresa).map((x) => verCertificado(c, x)),
      );
    },
  ],
  [
    "GET",
    /^\/certificados\/([^/]+)$/,
    (c, id): T.CertificadoDetalhe => {
      const u = exigir(c);
      const cert = achar(c.e.certificados, id, "Certificado");
      if (u.empresa_id && cert.empresa_id !== u.empresa_id) throw new Falha(404, "NAO_ENCONTRADO", "Certificado não encontrado");
      return {
        ...verCertificado(c, cert),
        laudo: c.e.laudos.find((l) => l.veiculo_id === cert.veiculo_id) ?? null,
        veiculo: achar(c.e.veiculos, cert.veiculo_id, "Veículo"),
      };
    },
  ],

  // ----- MMV (RF-03, RF-04) -----
  [
    "POST",
    /^\/mmvs$/,
    (c) => {
      const u = exigir(c, "FABRICANTE");
      const codigo = texto(c, "codigo");
      if (c.e.mmvs.some((m) => m.fabricante_id === u.empresa_id && m.codigo === codigo)) {
        throw new Falha(409, "MMV_DUPLICADO", "Já existe MMV com este código");
      }
      const nivel = Number(c.corpo.nivel);
      if (nivel !== 1 && nivel !== 2) throw new Falha(422, "VALIDACAO", "Nível deve ser 1 ou 2");
      const percentual = decimal(c, "percentual_reciclabilidade", 2);
      if (paraEscala(percentual, 2) > 10000n) throw new Falha(422, "VALIDACAO", "Percentual acima de 100");
      const ja_comercializado = c.corpo.ja_comercializado === true;
      const mmv: T.Mmv = {
        id: uuid(),
        fabricante_id: u.empresa_id!,
        codigo,
        ncm: texto(c, "ncm"),
        nivel,
        percentual_reciclabilidade: percentual,
        ja_comercializado,
        // RF-04, art. 5º §§2º e 3º
        efeitos_a_partir_de: ja_comercializado ? `${c.agora.getFullYear() + 1}-01-01` : hojeIso(c.agora),
        status: "ATIVO",
        rm: nivel === 1 ? 10 : 5,
        criado_em: c.agora.toISOString(),
      };
      c.e.mmvs.push(mmv);
      registrar(c, "MMV_CADASTRADO", "mmv", mmv.id, { codigo, nivel, efeitos_a_partir_de: mmv.efeitos_a_partir_de });
      return mmv;
    },
  ],
  [
    "GET",
    /^\/mmvs$/,
    (c) => {
      const u = exigir(c, "FABRICANTE", "AUDITOR", "ADMIN");
      return paginar(c, c.e.mmvs.filter((m) => !u.empresa_id || m.fabricante_id === u.empresa_id));
    },
  ],

  // ----- livro de URV (RF-16 a RF-21) -----
  [
    "GET",
    /^\/urv\/saldo$/,
    (c): T.Saldo => {
      const u = exigir(c, "DESMONTADORA", "RECICLADORA", "FABRICANTE");
      const saldo = saldoDe(c, u.empresa_id!);
      const prazos = c.e.consumos
        .filter((x) => x.fabricante_id === u.empresa_id && x.regularizar_ate)
        .map((x) => x.regularizar_ate!)
        .sort();
      return {
        empresa_id: u.empresa_id!,
        saldo: deEscala(saldo, 2),
        regularizar_ate: saldo < 0n ? (prazos[0] ?? null) : null,
      };
    },
  ],
  [
    "GET",
    /^\/urv\/extrato$/,
    (c) => {
      const u = exigir(c);
      const empresa = u.empresa_id ?? c.consulta.get("empresa_id");
      if (!empresa) throw new Falha(422, "VALIDACAO", "Informe empresa_id");
      return paginar(
        c,
        c.e.lancamentos
          .filter((l) => l.empresa_id === empresa)
          .map((l) => ({ ...l, contraparte: l.contraparte_id ? resumo(c, l.contraparte_id) : null }))
          .reverse(),
      );
    },
  ],
  [
    "GET",
    /^\/urv\/creditos$/,
    (c) => {
      const u = exigir(c, "DESMONTADORA", "RECICLADORA", "FABRICANTE");
      const status = c.consulta.get("status");
      return paginar(
        c,
        c.e.creditos
          .filter((x) => x.geradora_id === u.empresa_id || x.titular_id === u.empresa_id)
          .filter((x) => !status || x.status === status)
          .map((x) => verCredito(c, x)),
      );
    },
  ],
  [
    "POST",
    /^\/urv\/creditos\/([^/]+)\/transferir$/,
    (c, id) => {
      const u = exigir(c, "DESMONTADORA", "RECICLADORA");
      const credito = achar(c.e.creditos, id, "Crédito");
      if (credito.geradora_id !== u.empresa_id) throw new Falha(404, "NAO_ENCONTRADO", "Crédito não encontrado");
      // RF-17, art. 8º II e §3º: transferência direta e única.
      if (credito.status !== "DISPONIVEL" || credito.titular_id !== u.empresa_id) {
        throw new Falha(409, "CREDITO_JA_TRANSFERIDO", "Este crédito já foi transferido e não pode ser transferido de novo");
      }
      const fabricante_id = texto(c, "fabricante_id");
      const vinculo = c.e.vinculos.find(
        (v) => v.ativo && v.geradora_id === u.empresa_id && v.fabricante_id === fabricante_id,
      );
      const fabricante = c.e.empresas.find((x) => x.id === fabricante_id);
      if (!vinculo || !fabricante) {
        throw new Falha(422, "SEM_VINCULO", "Não há vínculo ativo com este fabricante");
      }
      if (!fabricante.registro_compromissos) {
        throw new Falha(422, "FABRICANTE_SEM_REGISTRO", "O fabricante não tem registro de compromissos no MDIC");
      }
      credito.status = "TRANSFERIDO";
      credito.titular_id = fabricante_id;
      lancar(c, u.empresa_id!, "TRANSFERENCIA_SAIDA", `-${credito.quantidade}`, { credito_id: id, contraparte_id: fabricante_id });
      lancar(c, fabricante_id, "TRANSFERENCIA_ENTRADA", credito.quantidade, { credito_id: id, contraparte_id: u.empresa_id });
      registrar(c, "CREDITO_TRANSFERIDO", "urv_credito", id, { fabricante_id, quantidade: credito.quantidade });
      return verCredito(c, credito);
    },
  ],
  [
    "POST",
    /^\/urv\/consumos\/simular$/,
    (c): T.Simulacao => {
      const u = exigir(c, "FABRICANTE");
      const mmv = mmvDoFabricante(c, u);
      const qv = Number(c.corpo.quantidade);
      if (!Number.isInteger(qv) || qv <= 0) throw new Falha(422, "VALIDACAO", "Quantidade deve ser um inteiro positivo");
      const pm = decimal(c, "preco_medio", 2);
      const { debito, razao_preco, multiplicador } = calcularDebito(qv, mmv.rm, pm, PRECO_BASE);
      const saldo = saldoDe(c, u.empresa_id!);
      const suficiente = saldo >= paraEscala(debito, 2);
      const permitido = suficiente || hojeIso(c.agora) <= FIM_SALDO_NEGATIVO;
      return {
        urv_debito: debito,
        saldo_atual: deEscala(saldo, 2),
        saldo_apos: deEscala(saldo - paraEscala(debito, 2), 2),
        saldo_suficiente: suficiente,
        permitido,
        regularizar_ate: !suficiente && permitido ? regularizarAte(c.agora) : null,
        prazo_saldo_negativo: FIM_SALDO_NEGATIVO,
        memoria_calculo: {
          formula: "urv_debito = (qv / rm) * max(1, pm / pb)",
          qv,
          nivel: mmv.nivel,
          rm: mmv.rm,
          pm,
          pb: PRECO_BASE,
          razao_preco,
          multiplicador,
        },
      };
    },
  ],
  [
    "POST",
    /^\/urv\/consumos$/,
    (c) => {
      const u = exigir(c, "FABRICANTE");
      const mmv = mmvDoFabricante(c, u);
      const hoje = hojeIso(c.agora);
      if (mmv.status !== "ATIVO" || hoje < mmv.efeitos_a_partir_de) {
        throw new Falha(422, "MMV_SEM_EFEITOS", `Este MMV só produz efeitos a partir de ${mmv.efeitos_a_partir_de}`);
      }
      const periodo = texto(c, "periodo");
      if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(periodo)) throw new Falha(422, "VALIDACAO", "Período no formato AAAA-MM");
      const bruto = Array.isArray(c.corpo.chassis) ? c.corpo.chassis : [];
      const chassis = bruto.map((x) => String(x).trim().toUpperCase()).filter(Boolean);
      if (!chassis.length) throw new Falha(422, "VALIDACAO", "Informe ao menos um chassi");
      if (new Set(chassis).size !== chassis.length) {
        throw new Falha(422, "CHASSI_REPETIDO_NA_LISTA", "Há chassi repetido na lista");
      }
      // RF-21, art. 29: um chassi novo consome uma vez.
      const usados = new Set(c.e.consumos.flatMap((x) => x.chassis));
      const repetidos = chassis.filter((x) => usados.has(x));
      if (repetidos.length) {
        throw new Falha(409, "CHASSI_JA_CONSUMIDO", `Chassi já consumido: ${repetidos.join(", ")}`);
      }
      const pm = decimal(c, "preco_medio", 2);
      const { debito } = calcularDebito(chassis.length, mmv.rm, pm, PRECO_BASE);
      const saldoApos = saldoDe(c, u.empresa_id!) - paraEscala(debito, 2);
      // RF-19, art. 8º III e §1º: saldo negativo só até 31/12/2027, com prazo de regularização.
      if (saldoApos < 0n && hoje > FIM_SALDO_NEGATIVO) {
        throw new Falha(409, "SALDO_INSUFICIENTE", "Saldo de URV insuficiente para este consumo");
      }
      const consumo: ConsumoReg = {
        id: uuid(),
        fabricante_id: u.empresa_id!,
        mmv_id: mmv.id,
        periodo,
        qv: chassis.length,
        rm: mmv.rm,
        pm,
        pb: PRECO_BASE,
        urv_debito: debito,
        saldo_apos: deEscala(saldoApos, 2),
        regularizar_ate: saldoApos < 0n ? regularizarAte(c.agora) : null,
        prazo_reporte: prazoReporte(periodo),
        registrado_em: c.agora.toISOString(),
        chassis,
      };
      c.e.consumos.push(consumo);
      lancar(c, u.empresa_id!, "DEBITO", `-${debito}`, { consumo_id: consumo.id });
      registrar(c, "CONSUMO_REGISTRADO", "consumo", consumo.id, { mmv_id: mmv.id, periodo, qv: consumo.qv, urv_debito: debito, chassis });
      return verConsumo(c, consumo);
    },
  ],
  [
    "GET",
    /^\/urv\/consumos$/,
    (c) => {
      const u = exigir(c, "FABRICANTE", "AUDITOR", "ADMIN");
      const chassi = c.consulta.get("chassi")?.trim().toUpperCase(); // PM-WEB-06: busca exata
      return paginar(
        c,
        c.e.consumos
          .filter((x) => !u.empresa_id || x.fabricante_id === u.empresa_id)
          .filter((x) => !chassi || x.chassis.includes(chassi))
          .map((x) => verConsumo(c, x))
          .reverse(),
      );
    },
  ],

  // ----- relatório e portabilidade (RF-24, RF-25) -----
  [
    "GET",
    /^\/relatorios\/mdic$/,
    (c): T.RelatorioMdic => {
      exigir(c, "AUDITOR", "ADMIN");
      const ano = c.consulta.get("ano");
      const noAno = (data: string) => !ano || data.startsWith(ano);
      const somar = (tipo: T.LancamentoTipo) =>
        deEscala(
          c.e.lancamentos
            .filter((l) => l.tipo === tipo && noAno(l.criado_em))
            .reduce((s, l) => s + paraEscala(l.quantidade, 2), 0n),
          2,
        ).replace("-", "");
      const materiais = new Map<string, T.MaterialRelatorio & { soma: bigint }>();
      for (const p of c.e.pesagens.filter((x) => noAno(x.criado_em))) {
        const chave = `${p.fracao}|${p.destino}`;
        const atual = materiais.get(chave) ?? { fracao: p.fracao, destino: p.destino, peso_kg: "0", soma: 0n };
        atual.soma += paraEscala(p.peso_kg, 3);
        materiais.set(chave, atual);
      }
      const linhas = [...materiais.values()];
      return {
        ano: ano ? Number(ano) : c.agora.getFullYear(),
        peso_total_kg: deEscala(
          linhas.reduce((s, m) => s + m.soma, 0n),
          3,
        ),
        registros: c.e.veiculos.filter((v) => noAno(v.criado_em)).length,
        certificados_emitidos: c.e.certificados.filter((x) => noAno(x.emitido_em)).length,
        urv_gerada: somar("CREDITO"),
        urv_transferida: somar("TRANSFERENCIA_ENTRADA"),
        urv_consumida: somar("DEBITO"),
        materiais: linhas.map(({ fracao, destino, soma }) => ({ fracao, destino, peso_kg: deEscala(soma, 3) })),
      };
    },
  ],
  [
    "GET",
    /^\/portabilidade\/exportar$/,
    (c) => {
      const u = exigir(c, "DESMONTADORA", "RECICLADORA", "FABRICANTE");
      const id = u.empresa_id!;
      const veiculos = c.e.veiculos.filter((v) => v.empresa_id === id);
      const ids = new Set(veiculos.map((v) => v.id));
      const dosVeiculos = <X extends { veiculo_id: string }>(lista: X[]) => lista.filter((x) => ids.has(x.veiculo_id));
      return {
        formato: "urv-portabilidade",
        versao: "1",
        exportado_em: c.agora.toISOString(),
        empresa: resumo(c, id),
        veiculos,
        etapas: dosVeiculos(c.e.etapas),
        anexos: dosVeiculos(c.e.anexos),
        pecas: dosVeiculos(c.e.pecas),
        pesagens: dosVeiculos(c.e.pesagens),
        dmrs: dosVeiculos(c.e.dmrs),
        laudos: dosVeiculos(c.e.laudos),
        certificados: c.e.certificados.filter((x) => x.empresa_id === id),
        creditos: c.e.creditos.filter((x) => x.geradora_id === id || x.titular_id === id),
        lancamentos: c.e.lancamentos.filter((l) => l.empresa_id === id),
        mmvs: c.e.mmvs.filter((m) => m.fabricante_id === id),
        consumos: c.e.consumos.filter((x) => x.fabricante_id === id),
      };
    },
  ],

  // ----- só do mock: apoio à demonstração -----
  [
    "POST",
    /^\/__mock\/adulterar$/,
    (c) => {
      // Faz o papel de scripts/adulterar.py: altera um evento sem recalcular o hash.
      const alvo = c.e.eventos[Math.floor(c.e.eventos.length / 2)];
      if (!alvo) throw new Falha(422, "SEM_EVENTOS", "Ainda não há eventos para adulterar");
      alvo.payload = { ...alvo.payload, adulterado: true };
      return { sequencia: alvo.sequencia };
    },
  ],
];

export function criarServidor(armazenamento?: Armazenamento, relogio: () => Date = () => new Date()) {
  let memoria: Estado | null = null;
  const arquivos = new Map<string, Blob>();

  function carregar(): Estado {
    if (armazenamento) {
      // Relê a cada requisição para que abas diferentes (a página pública da etiqueta) vejam os mesmos dados.
      try {
        const salvo = JSON.parse(armazenamento.ler() ?? "null") as Estado | null;
        if (salvo?.versao === VERSAO) return salvo;
      } catch {
        // estado corrompido: recomeça da semente
      }
      return semente(relogio());
    }
    return (memoria ??= semente(relogio()));
  }

  function responder(req: Requisicao): Resposta {
    const metodo = req.metodo.toUpperCase();
    if (metodo === "POST" && req.caminho === "/__mock/reiniciar") {
      memoria = semente(relogio());
      arquivos.clear();
      armazenamento?.gravar(JSON.stringify(memoria));
      return { status: 200, corpo: { ok: true } };
    }
    const e = carregar();
    const id = req.token?.startsWith("mock.") ? req.token.slice(5) : null;
    const c: Ctx = {
      e,
      u: e.usuarios.find((x) => x.id === id) ?? null,
      consulta: req.consulta ?? new URLSearchParams(),
      corpo: (req.corpo && typeof req.corpo === "object" ? req.corpo : {}) as Record<string, unknown>,
      agora: relogio(),
      arquivos,
    };
    try {
      for (const [m, padrao, manipulador] of ROTAS) {
        const achou = m === metodo ? padrao.exec(req.caminho) : null;
        if (!achou) continue;
        // AUDITOR nunca escreve (RNF-06, art. 24 V).
        if (c.u?.papel === "AUDITOR" && metodo !== "GET" && !req.caminho.startsWith("/__mock/")) {
          throw new Falha(403, "AUDITOR_SOMENTE_LEITURA", "O auditor tem acesso somente de leitura");
        }
        const corpo = manipulador(c, ...achou.slice(1));
        if (metodo !== "GET") {
          memoria = e;
          armazenamento?.gravar(JSON.stringify(e));
        }
        const cria = metodo === "POST" && !/simular|login|transferir|__mock/.test(req.caminho);
        return { status: cria ? 201 : 200, corpo };
      }
      throw new Falha(404, "ROTA_NAO_SIMULADA", `Rota não simulada: ${metodo} ${req.caminho}`);
    } catch (erro) {
      if (erro instanceof Falha) {
        return {
          status: erro.status,
          corpo: { detail: erro.message, codigo: erro.codigo, ...(erro.pendencias ? { pendencias: erro.pendencias } : {}) },
        };
      }
      throw erro;
    }
  }

  return { responder };
}
