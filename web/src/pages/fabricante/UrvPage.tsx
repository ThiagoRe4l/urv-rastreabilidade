import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listarCreditos, obterSaldo } from "../../api";
import { Erro } from "../../components/Erro";
import { Extrato } from "../../components/Extrato";
import { Artigo, Consulta, Titulo } from "../../components/ui";
import { compararDecimal, formatarDecimal } from "../../lib/decimal";
import { fmtData, fmtDataHora } from "../../lib/formato";

/** Saldo e extrato de URV do fabricante. O saldo é a soma dos lançamentos. */
export function UrvPage() {
  const saldo = useQuery({ queryKey: ["saldo"], queryFn: obterSaldo });
  const creditos = useQuery({ queryKey: ["creditos"], queryFn: () => listarCreditos() });
  const negativo = saldo.data ? compararDecimal(saldo.data.saldo, "0") < 0 : false;

  return (
    <>
      <Titulo
        titulo="Saldo e extrato de URV"
        sub="Créditos recebidos das desmontadoras e recicladoras e débitos pelos veículos novos comercializados."
        acoes={
          <Link className="botao" to="/consumos/novo">
            Registrar consumo
          </Link>
        }
      />
      <div className="cartoes">
        <div className={`cartao-numero ${negativo ? "cartao-alerta" : ""}`}>
          <span>Saldo</span>
          <strong>{saldo.data ? `${formatarDecimal(saldo.data.saldo)} URV` : "…"}</strong>
        </div>
      </div>
      <Erro erro={saldo.error} />
      {negativo && (
        <p className="alerta alerta-aviso">
          Saldo negativo. {saldo.data?.regularizar_ate && <>Regularize até <strong>{fmtData(saldo.data.regularizar_ate)}</strong>. </>}
          O saldo negativo só é admitido até 31/12/2027, com regularização até o último dia do terceiro mês seguinte.{" "}
          <Artigo>art. 8º, III e §1º</Artigo>
        </p>
      )}
      <section className="painel">
        <h2>Extrato</h2>
        <Extrato />
      </section>
      <section className="painel">
        <h2>Créditos recebidos</h2>
        <Consulta consulta={creditos} vazio={(d) => d.itens.length === 0 && "Nenhum crédito recebido."}>
          {(d) => (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Certificado</th>
                  <th>Chassi reciclado</th>
                  <th className="num">URV</th>
                  <th>Gerado em</th>
                </tr>
              </thead>
              <tbody>
                {d.itens.map((c) => (
                  <tr key={c.id}>
                    <td className="mono">{c.certificado?.numero ?? "—"}</td>
                    <td className="mono">{c.chassi ?? "—"}</td>
                    <td className="num">{formatarDecimal(c.quantidade)}</td>
                    <td>{fmtDataHora(c.criado_em)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Consulta>
      </section>
    </>
  );
}
