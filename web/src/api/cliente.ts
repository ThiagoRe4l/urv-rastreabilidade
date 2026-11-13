// Cliente HTTP mínimo. O frontend (agente 03) amplia; os tipos completos vêm de /openapi.json.

import { lerToken } from "../auth/sessao";

export const BASE_API = "/api/v1";

/** Corpo de erro do contrato: { detail, codigo, pendencias? }. */
export interface ErroApi {
  detail: string;
  codigo: string;
  pendencias?: string[];
}

export class ErroHttp extends Error {
  constructor(
    public readonly status: number,
    public readonly corpo: ErroApi,
  ) {
    super(corpo.detail);
  }
}

export async function api<T>(caminho: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = lerToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const resposta = await fetch(`${BASE_API}${caminho}`, { ...init, headers });
  if (!resposta.ok) {
    const corpo = (await resposta.json().catch(() => null)) as ErroApi | null;
    throw new ErroHttp(resposta.status, corpo ?? { detail: resposta.statusText, codigo: "ERRO_HTTP" });
  }
  return (resposta.status === 204 ? undefined : await resposta.json()) as T;
}
