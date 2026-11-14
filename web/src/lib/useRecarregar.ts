import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

/**
 * Depois de uma escrita, refaz as consultas em tela. Uma escrita no veículo muda várias leituras
 * de uma vez (estado, pendências, percentual, saldo), então invalidar tudo é o mais seguro.
 */
export function useRecarregar() {
  const queryClient = useQueryClient();
  return useCallback(() => void queryClient.invalidateQueries(), [queryClient]);
}
