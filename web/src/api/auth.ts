import { api, post } from "./cliente";
import type { LoginSaida, Usuario } from "./types";

export type { EmpresaResumo, LoginSaida, Papel, Usuario } from "./types";

export const login = (email: string, senha: string) => post<LoginSaida>("/auth/login", { email, senha });

export const me = () => api<Usuario>("/auth/me");
