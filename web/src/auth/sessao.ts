// Token guardado no sessionStorage: some ao fechar a aba.

const CHAVE = "urv.token";

export function lerToken(): string | null {
  try {
    return sessionStorage.getItem(CHAVE);
  } catch {
    return null;
  }
}

export function gravarToken(token: string): void {
  sessionStorage.setItem(CHAVE, token);
}

export function apagarToken(): void {
  sessionStorage.removeItem(CHAVE);
}
