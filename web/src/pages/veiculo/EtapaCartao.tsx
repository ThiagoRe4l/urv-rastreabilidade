import { useMutation } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { salvarEtapa } from "../../api";
import type { EtapaTipo, VeiculoDetalhe } from "../../api/types";
import { Erro } from "../../components/Erro";
import { Artigo, Selo } from "../../components/ui";
import { ROTULO_ETAPA } from "../../lib/dominio";
import { agoraLocal, fmtDataHora } from "../../lib/formato";
import { useRecarregar } from "../../lib/useRecarregar";
import { BotaoAnexar, ListaAnexos } from "./Anexos";
import { type Evidencia, type SituacaoEtapa, situacaoDaEtapa } from "./apoio";

const SELO: Record<SituacaoEtapa, ReactNode> = {
  pendente: <Selo>Não iniciada</Selo>,
  andamento: <Selo tom="info">Em andamento</Selo>,
  concluida: <Selo tom="ok">Concluída</Selo>,
  dispensada: <Selo>Dispensada</Selo>,
};

export function EtapaCartao({
  numero,
  tipo,
  artigo,
  veiculo,
  evidencias,
  podeEscrever,
  dispensada,
  children,
}: {
  numero: number;
  tipo: EtapaTipo;
  artigo: string;
  veiculo: VeiculoDetalhe;
  evidencias: Evidencia[];
  podeEscrever: boolean;
  dispensada?: string;
  children?: ReactNode;
}) {
  const etapa = veiculo.etapas.find((e) => e.tipo === tipo);
  const situacao = situacaoDaEtapa(etapa, !!dispensada);
  const anexos = veiculo.anexos.filter((a) => a.etapa_tipo === tipo);
  const recarregar = useRecarregar();
  // null = "agora", lido no momento do envio; evita concluir antes do início dentro do mesmo minuto.
  const [quando, setQuando] = useState<string | null>(null);
  const [observacoes, setObservacoes] = useState(etapa?.observacoes ?? "");

  const salvar = useMutation({
    mutationFn: () => {
      const instante = (quando ? new Date(quando) : new Date()).toISOString();
      return salvarEtapa(
        veiculo.id,
        tipo,
        etapa
          ? { iniciada_em: etapa.iniciada_em, concluida_em: instante, observacoes: observacoes.trim() || null }
          : { iniciada_em: instante, observacoes: observacoes.trim() || null },
      );
    },
    onSuccess: () => {
      setQuando(null);
      recarregar();
    },
  });

  const faltam = evidencias.filter((e) => !e.ok).length;

  return (
    <section className={`painel etapa etapa-${situacao}`} id={`etapa-${tipo}`}>
      <header className="etapa-cabecalho">
        <span className="etapa-numero">{situacao === "concluida" ? "✓" : numero}</span>
        <div>
          <h2>{ROTULO_ETAPA[tipo]}</h2>
          <Artigo>{artigo}</Artigo>
        </div>
        <div className="etapa-situacao">
          {SELO[situacao]}
          {etapa && (
            <span className="sutil">
              Início {fmtDataHora(etapa.iniciada_em)}
              {etapa.concluida_em && ` · Conclusão ${fmtDataHora(etapa.concluida_em)}`}
            </span>
          )}
        </div>
      </header>

      {dispensada && <p className="alerta alerta-info">{dispensada}</p>}

      {evidencias.length > 0 && (
        <ul className="evidencias" aria-label="Evidências da etapa">
          {evidencias.map((e) => (
            <li key={e.rotulo} className={e.ok ? "tem" : "falta"}>
              <span className="marca-evidencia" aria-hidden="true">
                {e.ok ? "✓" : "✗"}
              </span>
              <span>
                {e.rotulo}
                <span className="sutil"> {e.ok ? (e.detalhe ?? "") : "— falta"}</span>
              </span>
              {e.anexo && podeEscrever && (
                <BotaoAnexar
                  veiculoId={veiculo.id}
                  tipo={e.anexo}
                  etapa={tipo}
                  rotulo={e.ok ? "Anexar outro" : "Anexar"}
                />
              )}
            </li>
          ))}
        </ul>
      )}
      <ListaAnexos anexos={anexos} />

      {children}

      {etapa?.observacoes && situacao === "concluida" && <p className="sutil">Observações: {etapa.observacoes}</p>}

      {podeEscrever && situacao !== "concluida" && (
        <form
          className="etapa-acao"
          onSubmit={(e) => {
            e.preventDefault();
            salvar.mutate();
          }}
        >
          <label>
            {etapa ? "Concluída em" : "Iniciada em"}
            <input type="datetime-local" value={quando ?? agoraLocal()} onChange={(e) => setQuando(e.target.value)} required />
          </label>
          <label className="cresce">
            Observações
            <input value={observacoes} onChange={(e) => setObservacoes(e.target.value)} placeholder="Opcional" />
          </label>
          <button type="submit" disabled={salvar.isPending}>
            {etapa ? "Concluir etapa" : "Iniciar etapa"}
          </button>
          {etapa && faltam > 0 && (
            <span className="sutil">
              {faltam === 1 ? "Falta 1 evidência" : `Faltam ${faltam} evidências`} para o certificado.
            </span>
          )}
        </form>
      )}
      <Erro erro={salvar.error} titulo="A etapa não foi gravada" />
    </section>
  );
}
