import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { obterRelatorio } from "../../api";
import { Artigo, Consulta, Titulo } from "../../components/ui";
import { formatarDecimal } from "../../lib/decimal";
import { ROTULO_DESTINO_PESAGEM, ROTULO_FRACAO } from "../../lib/dominio";

const ANO_ATUAL = new Date().getFullYear();
const ANOS = Array.from({ length: ANO_ATUAL - 2026 + 1 }, (_, i) => 2026 + i);

/** Números do relatório ao MDIC (RF-24, art. 27). */
export function PainelPage() {
  const [ano, setAno] = useState(ANO_ATUAL);
  const relatorio = useQuery({ queryKey: ["relatorio", ano], queryFn: () => obterRelatorio(ano) });

  return (
    <>
      <Titulo
        titulo="Painel do programa"
        sub={
          <>
            Registros, certificados e volume de materiais. <Artigo>art. 27</Artigo>
          </>
        }
        acoes={
          <label className="em-linha">
            Ano
            <select value={ano} onChange={(e) => setAno(Number(e.target.value))}>
              {ANOS.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </label>
        }
      />
      <Consulta consulta={relatorio}>
        {(r) => (
          <>
            <div className="cartoes">
              <div className="cartao-numero">
                <span>Veículos registrados</span>
                <strong>{r.registros}</strong>
              </div>
              <div className="cartao-numero">
                <span>Certificados emitidos</span>
                <strong>{r.certificados_emitidos}</strong>
              </div>
              <div className="cartao-numero">
                <span>URV gerada</span>
                <strong>{formatarDecimal(r.urv_gerada)}</strong>
              </div>
              <div className="cartao-numero">
                <span>URV transferida</span>
                <strong>{formatarDecimal(r.urv_transferida)}</strong>
              </div>
              <div className="cartao-numero">
                <span>URV consumida</span>
                <strong>{formatarDecimal(r.urv_consumida)}</strong>
              </div>
            </div>
            <section className="painel">
              <h2>Materiais por fração e destino</h2>
              {r.materiais.length === 0 ? (
                <p className="sutil">Nenhuma pesagem no ano.</p>
              ) : (
                <table className="tabela">
                  <thead>
                    <tr>
                      <th>Fração</th>
                      <th>Destino</th>
                      <th className="num">Peso (kg)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.materiais.map((m) => (
                      <tr key={`${m.fracao}-${m.destino}`}>
                        <td>{ROTULO_FRACAO[m.fracao]}</td>
                        <td>{ROTULO_DESTINO_PESAGEM[m.destino]}</td>
                        <td className="num">{formatarDecimal(m.peso_kg)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </>
        )}
      </Consulta>
    </>
  );
}
