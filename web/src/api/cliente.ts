// Cliente HTTP mínimo sobre fetch. Os tipos estão em ./types.

import { apagarToken, lerToken } from "../auth/sessao";
import type { ErroApi } from "./types";

export type { ErroApi };

export const BASE_API = "/api/v1";

export class ErroHttp extends Error {
  constructor(
    public readonly status: number,
    public readonly corpo: ErroApi,
  ) {
    super(corpo.detail);
  }
}

async function requisitar(caminho: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = lerToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const resposta = await fetch(`${BASE_API}${caminho}`, { ...init, headers });
  if (!resposta.ok) {
    const bruto = (await resposta.json().catch(() => null)) as Partial<ErroApi> | null;
    // Sessão vencida: volta ao login (menos na própria tentativa de login).
    if (resposta.status === 401 && token && !caminho.startsWith("/auth/login")) {
      apagarToken();
      window.location.assign("/login");
    }
    throw new ErroHttp(resposta.status, {
      // Erros de validação do FastAPI trazem `detail` como lista; vira texto.
      detail: typeof bruto?.detail === "string" ? bruto.detail : resposta.statusText || "Erro na requisição",
      codigo: bruto?.codigo ?? "ERRO_HTTP",
      pendencias: bruto?.pendencias,
    });
  }
  return resposta;
}

export async function api<T>(caminho: string, init: RequestInit = {}): Promise<T> {
  const resposta = await requisitar(caminho, init);
  return (resposta.status === 204 ? undefined : await resposta.json()) as T;
}

/** Para arquivos protegidos por token (anexos, exportação). */
export async function apiBlob(caminho: string): Promise<Blob> {
  return (await requisitar(caminho, {})).blob();
}

export const post = <T>(caminho: string, corpo?: unknown) =>
  api<T>(caminho, { method: "POST", body: corpo === undefined ? undefined : JSON.stringify(corpo) });
export const patch = <T>(caminho: string, corpo: unknown) =>
  api<T>(caminho, { method: "PATCH", body: JSON.stringify(corpo) });
export const put = <T>(caminho: string, corpo: unknown) =>
  api<T>(caminho, { method: "PUT", body: JSON.stringify(corpo) });

/** Monta a query string ignorando valores vazios. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(params)) {
    if (valor !== undefined && valor !== null && valor !== "") busca.set(chave, String(valor));
  }
  const texto = busca.toString();
  return texto ? `?${texto}` : "";
}
