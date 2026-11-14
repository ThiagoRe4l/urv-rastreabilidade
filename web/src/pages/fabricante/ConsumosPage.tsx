import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listarConsumos, listarMmvs, obterSaldo } from "../../api";
import { Artigo, Consulta, Selo, Titulo } from "../../components/ui";
import { compararDecimal, formatarDecimal } from "../../lib/decimal";
import { fmtData, fmtDataHora, fmtPeriodo } from "../../lib/formato";

/** Consumos de URV já registrados, com o prazo de reporte e a regularização pendente (RF-19, RF-20). */
export function ConsumosPage() {
  const consumos = useQuery({ queryKey: ["consumos"], queryFn: () => listarConsumos() });
  const mmvs = useQuery({ queryKey: ["mmvs"], queryFn: listarMmvs });
  const saldo = useQuery({ queryKey: ["saldo"], queryFn: obterSaldo });
  const negativo = saldo.data ? compararDecimal(saldo.data.saldo, "0") < 0 : false;
  const codigo = (id: string) => mmvs.data?.itens.find((m) => m.id === id)?.codigo ?? "—";

  return (
    <>
      <Titulo
        titulo="Consumos de URV"
        sub="Débitos pelos veículos novos comercializados, informados por chassi (art. 6º II; art. 8º III)."
        acoes={
          <Link className="botao" to="/consumos/novo">
            Registrar consumo
          </Link>
        }
      />
      {negativo && (
        <p className="alerta alerta-aviso">
          Saldo atual de {formatarDecimal(saldo.data!.saldo)} URV: há regularização pendente
          {saldo.data?.regularizar_ate && <> até <strong>{fmtData(saldo.data.regularizar_ate)}</strong></>}.{" "}
          <Artigo>art. 8º §1º</Artigo>
        </p>
      )}
      <section className="painel">
        <Consulta consulta={consumos} vazio={(d) => d.itens.length === 0 && "Nenhum consumo registrado."}>
          {(d) => (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Período</th>
                  <th>MMV</th>
                  <th className="num">Veículos</th>
                  <th className="num">Preço médio (R$)</th>
                  <th className="num">Débito (URV)</th>
                  <th className="num">Saldo após</th>
                  <th>Prazo de reporte</th>
                  <th>Regularização</th>
                </tr>
              </thead>
              <tbody>
                {d.itens.map((c) => (
                  <tr key={c.id}>
                    <td>{fmtPeriodo(c.periodo)}</td>
                    <td className="mono">{codigo(c.mmv_id)}</td>
                    <td className="num">{c.qv}</td>
                    <td className="num">{formatarDecimal(c.pm)}</td>
                    <td className="num">{formatarDecimal(c.urv_debito)}</td>
                    <td className={`num ${compararDecimal(c.saldo_apos, "0") < 0 ? "negativo" : ""}`}>
                      {formatarDecimal(c.saldo_apos)}
                    </td>
                    <td>
                      {fmtData(c.prazo_reporte)}{" "}
                      {c.fora_do_prazo ? <Selo tom="erro">Fora do prazo</Selo> : <Selo tom="ok">No prazo</Selo>}
                      <div className="sutil">Registrado em {fmtDataHora(c.registrado_em)}</div>
                    </td>
                    <td>
                      {c.regularizar_ate ? (
                        <>
                          até {fmtData(c.regularizar_ate)}{" "}
                          {negativo ? <Selo tom="aviso">Pendente</Selo> : <Selo tom="ok">Saldo regularizado</Selo>}
                        </>
                      ) : (
                        <span className="sutil">Não se aplica</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Consulta>
        <p className="sutil">
          O prazo de reporte é o décimo dia útil do mês seguinte ao período. <Artigo>art. 7º, parágrafo único</Artigo>
        </p>
      </section>
    </>
  );
}
