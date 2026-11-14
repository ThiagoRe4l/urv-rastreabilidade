import { useQuery } from "@tanstack/react-query";

import { listarPecas, obterCertificado, obterLaudo } from "../../api";
import type { AnexoTipo, Etapa, Veiculo, VeiculoDetalhe } from "../../api/types";

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

/** Peças do veículo: GET /pecas?veiculo_id= (RF-10; PM-WEB-04). */
export function usePecasDoVeiculo(veiculo: Veiculo) {
  return useQuery({
    queryKey: ["pecas", "veiculo", veiculo.id],
    queryFn: async () => (await listarPecas({ veiculo_id: veiculo.id })).itens,
  });
}

/** Laudo do veículo, antes ou depois do certificado: GET /veiculos/{id}/laudo (RF-14; PM-WEB-03). */
export function useLaudoDoVeiculo(veiculo: VeiculoDetalhe) {
  return useQuery({
    queryKey: ["laudo", "veiculo", veiculo.id, veiculo.laudo_id],
    enabled: veiculo.laudo_id != null,
    queryFn: () => obterLaudo(veiculo.id),
  });
}

/** Certificado do veículo, com laudo e crédito: `certificado_id` vem no detalhe do veículo (PM-03 a). */
export function useCertificadoDoVeiculo(veiculo: VeiculoDetalhe) {
  const id = veiculo.certificado_id;
  return useQuery({
    queryKey: ["certificado", "veiculo", veiculo.id, id],
    enabled: id != null,
    queryFn: () => obterCertificado(id!),
  });
}
