// Decimais do contrato trafegam como string ("0.94", "150000.00").
// Aqui nada vira float: as contas usam BigInt em escala fixa e o arredondamento é ROUND_HALF_UP.

/** Converte "12.345" em inteiro na escala pedida (casas decimais). Casas além da escala arredondam HALF_UP. */
export function paraEscala(valor: string | number, casas: number): bigint {
  const texto = String(valor).trim().replace(",", ".");
  if (!/^-?\d*(\.\d*)?$/.test(texto) || texto === "" || texto === "-" || texto === ".") {
    throw new Error(`Decimal inválido: ${valor}`);
  }
  const negativo = texto.startsWith("-");
  const [inteiro = "0", fracao = ""] = texto.replace("-", "").split(".");
  const mantida = fracao.slice(0, casas).padEnd(casas, "0");
  let n = BigInt((inteiro || "0") + mantida);
  if (fracao.length > casas && fracao[casas] >= "5") n += 1n;
  return negativo ? -n : n;
}

/** Inverso de paraEscala: inteiro escalado para string decimal com ponto. */
export function deEscala(n: bigint, casas: number): string {
  const negativo = n < 0n;
  const digitos = (negativo ? -n : n).toString().padStart(casas + 1, "0");
  const corpo = casas === 0 ? digitos : `${digitos.slice(0, -casas)}.${digitos.slice(-casas)}`;
  return negativo ? `-${corpo}` : corpo;
}

/** Divisão inteira com arredondamento ROUND_HALF_UP (metade se afasta do zero). */
export function dividirHalfUp(numerador: bigint, denominador: bigint): bigint {
  if (denominador === 0n) throw new Error("Divisão por zero");
  const negativo = numerador < 0n !== denominador < 0n;
  const n = numerador < 0n ? -numerador : numerador;
  const d = denominador < 0n ? -denominador : denominador;
  const q = (2n * n + d) / (2n * d);
  return negativo ? -q : q;
}

export function decimalValido(valor: string): boolean {
  try {
    paraEscala(valor, 6);
    return true;
  } catch {
    return false;
  }
}

/** -1, 0 ou 1. Compara sem passar por float. */
export function compararDecimal(a: string, b: string): number {
  const x = paraEscala(a, 6);
  const y = paraEscala(b, 6);
  return x < y ? -1 : x > y ? 1 : 0;
}

/** Normaliza a entrada do usuário ("1.234,5" ou "1234.5") para o formato do contrato. */
export function normalizarEntrada(valor: string, casas: number): string {
  const limpo = valor.trim();
  const texto = limpo.includes(",") ? limpo.replace(/\./g, "").replace(",", ".") : limpo;
  return deEscala(paraEscala(texto, casas), casas);
}

/** Exibição em pt-BR: "150000.00" → "150.000,00". */
export function formatarDecimal(valor: string | null | undefined, casas?: number): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  let texto = String(valor);
  if (casas !== undefined) texto = deEscala(paraEscala(texto, casas), casas);
  const negativo = texto.startsWith("-");
  const [inteiro, fracao] = texto.replace("-", "").split(".");
  const agrupado = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${negativo ? "−" : ""}${agrupado}${fracao ? `,${fracao}` : ""}`;
}
