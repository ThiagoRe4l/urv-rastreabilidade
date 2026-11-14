import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listarEventos, verificarCadeia } from "../../api";
import type { Evento } from "../../api/types";
import { Erro } from "../../components/Erro";
import { Artigo, Consulta, Titulo } from "../../components/ui";
import { fmtDataHora, hashCurto } from "../../lib/formato";

const TAMANHO = 20;

export function TabelaEventos({ eventos }: { eventos: Evento[] }) {
  return (
    <table className="tabela">
      <thead>
        <tr>
          <th className="num">Seq.</th>
          <th>Quando</th>
          <th>Evento</th>
          <th>Entidade</th>
          <th>Dados</th>
          <th>Hash</th>
        </tr>
      </thead>
      <tbody>
        {eventos.map((e) => (
          <tr key={e.id}>
            <td className="num">{e.sequencia}</td>
            <td>{fmtDataHora(e.ocorrido_em)}</td>
            <td className="mono">{e.tipo}</td>
            <td>{e.entidade}</td>
            <td>
              <details>
                <summary>ver</summary>
                <pre>{JSON.stringify(e.payload, null, 2)}</pre>
              </details>
            </td>
            <td className="mono" title={`anterior: ${e.hash_anterior}\nhash: ${e.hash}`}>
              {hashCurto(e.hash)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Trilha de auditoria e verificação da cadeia de hashes (RF-22, RF-23). */
export function AuditoriaPage() {
  const [entidade, setEntidade] = useState("");
  const [tipo, setTipo] = useState("");
  const [pagina, setPagina] = useState(1);
  const filtros = { entidade: entidade.trim(), tipo: tipo.trim(), pagina, tamanho: TAMANHO };
  const eventos = useQuery({ queryKey: ["eventos", filtros], queryFn: () => listarEventos(filtros) });
  const verificar = useMutation({ mutationFn: verificarCadeia });
  const v = verificar.data;
  const paginas = Math.max(1, Math.ceil((eventos.data?.total ?? 0) / TAMANHO));

  return (
    <>
      <Titulo
        titulo="Trilha de auditoria"
        sub={
          <>
            Cada evento guarda o hash do anterior; alterar um registro quebra a cadeia. <Artigo>art. 20 V; art. 24 I</Artigo>
          </>
        }
        acoes={
          <button type="button" disabled={verificar.isPending} onClick={() => verificar.mutate()}>
            {verificar.isPending ? "Verificando…" : "Verificar integridade"}
          </button>
        }
      />
      <Erro erro={verificar.error} titulo="A verificação falhou" />
      {v &&
        (v.integra ? (
          <p className="alerta alerta-ok" role="status">
            <strong>Cadeia íntegra.</strong> {v.total} {v.total === 1 ? "evento conferido" : "eventos conferidos"}, nenhum
            alterado.
          </p>
        ) : (
          <p className="alerta alerta-erro" role="alert">
            <strong>Cadeia quebrada.</strong> O primeiro evento que não confere é o de sequência{" "}
            <strong>{v.primeira_quebra}</strong>, entre {v.total} eventos. Esse registro, ou algum anterior a ele, foi
            alterado depois de gravado.
          </p>
        ))}
      <div className="painel filtros">
        <label>
          Entidade
          <input
            value={entidade}
            onChange={(e) => {
              setEntidade(e.target.value);
              setPagina(1);
            }}
            placeholder="veiculo"
          />
        </label>
        <label>
          Tipo de evento
          <input
            value={tipo}
            onChange={(e) => {
              setTipo(e.target.value);
              setPagina(1);
            }}
            placeholder="exato, como aparece na tabela"
          />
        </label>
      </div>
      <section className="painel">
        <Consulta consulta={eventos} vazio={(d) => d.total === 0 && "Nenhum evento encontrado."}>
          {(d) => (
            <>
              <TabelaEventos eventos={d.itens} />
              <div className="linha paginacao">
                <button type="button" className="botao-secundario" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>
                  Anterior
                </button>
                <span>
                  Página {pagina} de {paginas} · {d.total} eventos
                </span>
                <button type="button" className="botao-secundario" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>
                  Próxima
                </button>
              </div>
            </>
          )}
        </Consulta>
      </section>
    </>
  );
}
