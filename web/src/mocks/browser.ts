// Liga o backend simulado ao navegador por MSW. Só é carregado com VITE_MOCK=1.

import { http, HttpResponse } from "msw";
import { setupWorker } from "msw/browser";

import { BASE_API } from "../api/cliente";
import { criarServidor } from "./servidor";

const CHAVE = "urv.mock.estado";

// localStorage, e não sessionStorage, para que a página pública da etiqueta, aberta em outra aba
// pelo QR Code, veja as mesmas peças.
const servidor = criarServidor({
  ler: () => {
    try {
      return localStorage.getItem(CHAVE);
    } catch {
      return null;
    }
  },
  gravar: (texto) => {
    try {
      localStorage.setItem(CHAVE, texto);
    } catch {
      // sem armazenamento: o estado vale só até a próxima requisição
    }
  },
});

const manipulador = http.all(`${BASE_API}/*`, async ({ request }) => {
  const url = new URL(request.url);
  const tipo = request.headers.get("content-type") ?? "";
  let corpo: unknown;
  if (tipo.includes("multipart/form-data")) {
    corpo = Object.fromEntries((await request.formData()).entries());
  } else if (request.method !== "GET") {
    corpo = await request.json().catch(() => undefined);
  }
  const resposta = servidor.responder({
    metodo: request.method,
    caminho: url.pathname.slice(BASE_API.length),
    consulta: url.searchParams,
    corpo,
    token: request.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ?? null,
  });
  if (resposta.corpo instanceof Blob) return new HttpResponse(resposta.corpo, { status: resposta.status });
  return HttpResponse.json(resposta.corpo as Record<string, unknown>, { status: resposta.status });
});

export async function iniciarMock(): Promise<void> {
  await setupWorker(manipulador).start({ onUnhandledRequest: "bypass", quiet: true });
}
