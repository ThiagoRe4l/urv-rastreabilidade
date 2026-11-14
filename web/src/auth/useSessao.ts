import { useOutletContext } from "react-router-dom";

import type { Usuario } from "../api/types";

/** Usuário já carregado, disponível para toda página dentro do Layout. */
export function useSessao(): Usuario {
  return useOutletContext<Usuario>();
}
