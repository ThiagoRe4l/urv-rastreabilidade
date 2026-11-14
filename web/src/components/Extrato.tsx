import { useQuery } from "@tanstack/react-query";

import { listarEmpresas, listarExtrato } from "../api";
import { compararDecimal, formatarDecimal } from "../lib/decimal";
import { ROTULO_LANCAMENTO } from "../lib/dominio";
import { fmtDataHora } from "../lib/formato";
import { Consulta } from "./ui";

/** Livro de URV da empresa: só lançamentos, nunca um saldo editável. `empresaId` é para o auditor. */
export function Extrato({ empresaId }: { empresaId?: string }) {
  const extrato = useQuery({ queryKey: ["extrato", empresaId ?? ""], queryFn: () => listarExtrato(empresaId) });
  const empresas = useQuery({ queryKey: ["empresas", ""], queryFn: () => listarEmpresas() });
  const nome = (id: string | null) => (id ? (empresas.data?.itens.find((e) => e.id === id)?.razao_social ?? "—") : "—");

  return (
    <Consulta consulta={extrato} vazio={(d) => d.itens.length === 0 && "Nenhum lançamento."}>
      {(d) => (
        <table className="tabela">
          <thead>
            <tr>
              <th>Data</th>
              <th>Lançamento</th>
              <th>Contraparte</th>
              <th className="num">URV</th>
            </tr>
          </thead>
          <tbody>
            {d.itens.map((l) => (
              <tr key={l.id}>
                <td>{fmtDataHora(l.criado_em)}</td>
                <td>{ROTULO_LANCAMENTO[l.tipo]}</td>
                <td>{nome(l.contraparte_id)}</td>
                <td className={`num ${compararDecimal(l.quantidade, "0") < 0 ? "negativo" : "positivo"}`}>
                  {compararDecimal(l.quantidade, "0") > 0 ? "+" : ""}
                  {formatarDecimal(l.quantidade)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Consulta>
  );
}
