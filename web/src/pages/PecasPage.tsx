import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listarPecas } from "../api";
import type { Etiqueta as DadosEtiqueta, PecaClassificacao, PecaCondicao, PecaDestino } from "../api/types";
import { Etiqueta } from "../components/Etiqueta";
import { Consulta, Selecao, Titulo } from "../components/ui";
import { ROTULO_CLASSIFICACAO, ROTULO_CONDICAO, ROTULO_DESTINO_PECA } from "../lib/dominio";

/** Consulta de peças por origem, tipo, condição e destino (RF-10; Anexo III 16). */
export function PecasPage() {
  const [chassi, setChassi] = useState("");
  const [nome, setNome] = useState("");
  const [classificacao, setClassificacao] = useState<PecaClassificacao | "">("");
  const [condicao, setCondicao] = useState<PecaCondicao | "">("");
  const [destino, setDestino] = useState<PecaDestino | "">("");
  const [etiqueta, setEtiqueta] = useState<DadosEtiqueta | null>(null);
  const pecas = useQuery({
    queryKey: ["pecas", chassi, nome, classificacao, condicao, destino],
    queryFn: () => listarPecas({ chassi: chassi.trim(), nome: nome.trim(), classificacao, condicao, destino }),
  });

  return (
    <>
      <Titulo titulo="Peças" sub="Consulta por veículo de origem, nome, classificação, condição e destino (Anexo III, item 16)." />
      <div className="painel filtros">
        <label>
          Chassi de origem
          <input value={chassi} onChange={(e) => setChassi(e.target.value)} />
        </label>
        <label>
          Nome
          <input value={nome} onChange={(e) => setNome(e.target.value)} />
        </label>
        <label>
          Classificação
          <Selecao valor={classificacao} aoMudar={setClassificacao} opcoes={ROTULO_CLASSIFICACAO} vazio="Todas" />
        </label>
        <label>
          Condição
          <Selecao valor={condicao} aoMudar={setCondicao} opcoes={ROTULO_CONDICAO} vazio="Todas" />
        </label>
        <label>
          Destino
          <Selecao valor={destino} aoMudar={setDestino} opcoes={ROTULO_DESTINO_PECA} vazio="Todos" />
        </label>
      </div>
      <div className="painel">
        <Consulta consulta={pecas} vazio={(d) => d.itens.length === 0 && "Nenhuma peça encontrada."}>
          {(d) => (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Peça</th>
                  <th>Veículo de origem</th>
                  <th>Classificação</th>
                  <th>Condição</th>
                  <th>Destino</th>
                  <th>Rastreio</th>
                </tr>
              </thead>
              <tbody>
                {d.itens.map((p) => (
                  <tr key={p.id}>
                    <td>{p.nome}</td>
                    <td>
                      <Link className="mono" to={`/veiculos/${p.veiculo_id}`}>
                        {p.chassi ?? p.etiqueta?.chassi ?? "ver veículo"}
                      </Link>
                    </td>
                    <td>{ROTULO_CLASSIFICACAO[p.classificacao]}</td>
                    <td>{ROTULO_CONDICAO[p.condicao]}</td>
                    <td>{ROTULO_DESTINO_PECA[p.destino]}</td>
                    <td>
                      {p.etiqueta ? (
                        <button type="button" className="botao-link mono" onClick={() => setEtiqueta(p.etiqueta)}>
                          {p.codigo_rastreio}
                        </button>
                      ) : p.descaracterizada ? (
                        "Descaracterizada"
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Consulta>
      </div>
      {etiqueta && <Etiqueta etiqueta={etiqueta} aoFechar={() => setEtiqueta(null)} />}
    </>
  );
}
