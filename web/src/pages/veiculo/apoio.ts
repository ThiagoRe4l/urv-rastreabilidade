import { useQuery } from "@tanstack/react-query";

import { listarCertificados, listarPecas, obterCertificado } from "../../api";
import type { AnexoTipo, Etapa, Veiculo } from "../../api/types";

/** Uma evidência exigida na etapa: já existe ou falta. Com `anexo`, oferece o envio do arquivo. */
export interface Evidencia {
  rotulo: string;
  ok: boolean;
  anexo?: AnexoTipo;
  detalhe?: string;
}

export type SituacaoEtapa = "pendente" | "andamento" | "concluida" | "dispensada";

export function situacaoDaEtapa(etapa: Etapa | undefined, dispensada = false): SituacaoEtapa {
  if (etapa?.concluida_em) return "concluida";
  if (etapa) return "andamento";
  return dispensada ? "dispensada" : "pendente";
}

/** O contrato não tem lista de peças por veículo; usa-se a consulta por chassi (RF-10). */
export function usePecasDoVeiculo(veiculo: Veiculo) {
  return useQuery({
    queryKey: ["pecas", "veiculo", veiculo.id],
    queryFn: async () => (await listarPecas({ chassi: veiculo.chassi })).itens.filter((p) => p.veiculo_id === veiculo.id),
  });
}

/**
 * Certificado do veículo, com laudo e crédito. GET /veiculos/{id} não traz o certificado,
 * então ele é achado na lista da empresa e depois detalhado (pedido de mudança PM-WEB-03).
 */
export function useCertificadoDoVeiculo(veiculo: Veiculo) {
  const emitido = veiculo.estado === "CERTIFICADO" || veiculo.estado === "ENCERRADO";
  return useQuery({
    queryKey: ["certificado", "veiculo", veiculo.id],
    enabled: emitido,
    queryFn: async () => {
      const lista = await listarCertificados(veiculo.empresa_id);
      const achado = lista.itens.find((c) => c.veiculo_id === veiculo.id);
      return achado ? obterCertificado(achado.id) : null;
    },
  });
}
