import type { ReactNode } from "react";

import type { EstadoVeiculo } from "../api/types";
import { ROTULO_ESTADO } from "../lib/dominio";
import { Erro } from "./Erro";

export type Tom = "ok" | "aviso" | "erro" | "neutro" | "info";

export function Selo({ tom = "neutro", children }: { tom?: Tom; children: ReactNode }) {
  return <span className={`selo selo-${tom}`}>{children}</span>;
}

const TOM_ESTADO: Record<EstadoVeiculo, Tom> = {
  RECEBIDO: "neutro",
  EM_PROCESSO: "info",
  LAUDO_EMITIDO: "aviso",
  CERTIFICADO: "ok",
  ENCERRADO: "ok",
};

export function SeloEstado({ estado }: { estado: EstadoVeiculo }) {
  return <Selo tom={TOM_ESTADO[estado]}>{ROTULO_ESTADO[estado]}</Selo>;
}

/** Referência ao artigo da portaria ao lado de uma regra. */
export function Artigo({ children }: { children: ReactNode }) {
  return <span className="artigo">{children}</span>;
}

/** Estados de carregamento, erro e lista vazia de uma consulta, em um só lugar. */
export function Consulta<D>({
  consulta,
  vazio,
  children,
}: {
  consulta: { data: D | undefined; error: unknown; isPending: boolean };
  vazio?: (dados: D) => string | false;
  children: (dados: D) => ReactNode;
}) {
  if (consulta.error) return <Erro erro={consulta.error} />;
  if (consulta.isPending || consulta.data === undefined) return <p className="sutil">Carregando…</p>;
  const mensagem = vazio?.(consulta.data);
  if (mensagem) return <p className="sutil">{mensagem}</p>;
  return <>{children(consulta.data)}</>;
}

export function Titulo({ titulo, sub, acoes }: { titulo: string; sub?: ReactNode; acoes?: ReactNode }) {
  return (
    <div className="titulo">
      <div>
        <h1>{titulo}</h1>
        {sub && <p className="sutil">{sub}</p>}
      </div>
      {acoes && <div className="linha">{acoes}</div>}
    </div>
  );
}

/** <select> a partir de um mapa valor → rótulo. */
export function Selecao<V extends string>({
  valor,
  aoMudar,
  opcoes,
  vazio,
  ...resto
}: {
  valor: V | "";
  aoMudar: (valor: V) => void;
  opcoes: Record<V, string>;
  vazio?: string;
  required?: boolean;
  disabled?: boolean;
}) {
  return (
    <select value={valor} onChange={(e) => aoMudar(e.target.value as V)} {...resto}>
      {vazio !== undefined && <option value="">{vazio}</option>}
      {(Object.keys(opcoes) as V[]).map((v) => (
        <option key={v} value={v}>
          {opcoes[v]}
        </option>
      ))}
    </select>
  );
}
