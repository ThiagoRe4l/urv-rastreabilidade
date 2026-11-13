import { api } from "./cliente";

export type Papel = "ADMIN" | "DESMONTADORA" | "RECICLADORA" | "FABRICANTE" | "AUDITOR";

export interface EmpresaResumo {
  id: string;
  cnpj: string;
  razao_social: string;
  tipo: "FABRICANTE" | "DESMONTADORA" | "RECICLADORA";
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

export const login = (email: string, senha: string) =>
  api<LoginSaida>("/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) });

export const me = () => api<Usuario>("/auth/me");
