// Formatação de datas e documentos para exibição.

/** "2026-11-13" → "13/11/2026", sem passar por fuso. */
export function fmtData(valor: string | null | undefined): string {
  if (!valor) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(valor);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : valor;
}

export function fmtDataHora(valor: string | null | undefined): string {
  if (!valor) return "—";
  const d = new Date(valor);
  if (Number.isNaN(d.getTime())) return valor;
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

/** "2026-11" → "11/2026". */
export function fmtPeriodo(valor: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(valor);
  return m ? `${m[2]}/${m[1]}` : valor;
}

export function fmtCnpj(valor: string | null | undefined): string {
  if (!valor) return "—";
  const d = valor.replace(/\D/g, "");
  if (d.length !== 14) return valor;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

/** Confere os dois dígitos verificadores do CNPJ. */
export function cnpjValido(valor: string): boolean {
  const d = valor.replace(/\D/g, "");
  if (d.length !== 14 || /^(\d)\1{13}$/.test(d)) return false;
  const digito = (tamanho: number) => {
    let soma = 0;
    for (let i = 0; i < tamanho; i++) soma += Number(d[i]) * (((tamanho - 1 - i) % 8) + 2);
    const resto = soma % 11;
    return resto < 2 ? 0 : 11 - resto;
  };
  return digito(12) === Number(d[12]) && digito(13) === Number(d[13]);
}

/** Data local de hoje como "AAAA-MM-DD". */
export function hojeIso(agora = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${agora.getFullYear()}-${p(agora.getMonth() + 1)}-${p(agora.getDate())}`;
}

/** Valor para <input type="datetime-local"> no horário local. */
export function agoraLocal(agora = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${hojeIso(agora)}T${p(agora.getHours())}:${p(agora.getMinutes())}`;
}

export function hashCurto(hash: string): string {
  return hash.length > 16 ? `${hash.slice(0, 8)}…${hash.slice(-6)}` : hash;
}
