import { useQuery } from "@tanstack/react-query";

import { me } from "../api/auth";
import { lerToken } from "./sessao";

/** Usuário da sessão. O login já preenche o cache ["me"]. */
export function useUsuario() {
  return useQuery({ queryKey: ["me"], queryFn: me, enabled: !!lerToken(), staleTime: Infinity });
}
