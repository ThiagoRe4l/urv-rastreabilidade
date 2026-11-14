import { useMutation, useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { criarMmv, listarMmvs } from "../../api";
import { useSessao } from "../../auth/useSessao";
import { Erro } from "../../components/Erro";
import { Artigo, Consulta, Selo, Titulo } from "../../components/ui";
import { formatarDecimal, normalizarEntrada } from "../../lib/decimal";
import { fmtData, hojeIso } from "../../lib/formato";
import { useRecarregar } from "../../lib/useRecarregar";

/** MMVs (marca, modelo e versão) do fabricante e o cadastro de um novo (RF-03, RF-04). */
export function MmvsPage() {
  const { papel } = useSessao();
  const mmvs = useQuery({ queryKey: ["mmvs"], queryFn: listarMmvs });
  const recarregar = useRecarregar();
  const [codigo, setCodigo] = useState("");
  const [ncm, setNcm] = useState("");
  const [nivel, setNivel] = useState<1 | 2>(1);
  const [percentual, setPercentual] = useState("");
  const [jaComercializado, setJaComercializado] = useState(false);

  const criar = useMutation({
    mutationFn: () =>
      criarMmv({
        codigo: codigo.trim(),
        ncm: ncm.trim(),
        nivel,
        percentual_reciclabilidade: normalizarEntrada(percentual, 2),
        ja_comercializado: jaComercializado,
      }),
    onSuccess: () => {
      setCodigo("");
      setNcm("");
      setPercentual("");
      recarregar();
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    criar.mutate();
  }

  const hoje = hojeIso();
  return (
    <>
      <Titulo titulo="MMVs" sub="Marca, modelo e versão dos veículos novos, com nível e percentual de reciclabilidade (art. 5º)." />
      <section className="painel">
        <Consulta consulta={mmvs} vazio={(d) => d.itens.length === 0 && "Nenhum MMV cadastrado."}>
          {(d) => (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>NCM</th>
                  <th>Nível</th>
                  <th className="num">RM</th>
                  <th className="num">Reciclabilidade</th>
                  <th>Efeitos a partir de</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {d.itens.map((m) => (
                  <tr key={m.id}>
                    <td className="mono">{m.codigo}</td>
                    <td>{m.ncm}</td>
                    <td>{m.nivel}</td>
                    <td className="num">{m.rm}</td>
                    <td className="num">{formatarDecimal(m.percentual_reciclabilidade)}%</td>
                    <td>
                      {fmtData(m.efeitos_a_partir_de)}{" "}
                      {m.efeitos_a_partir_de > hoje && <Selo tom="aviso">Ainda sem efeitos</Selo>}
                    </td>
                    <td>
                      <Selo tom={m.status === "ATIVO" ? "ok" : "neutro"}>{m.status === "ATIVO" ? "Ativo" : "Retirado"}</Selo>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Consulta>
      </section>

      {papel === "FABRICANTE" && (
        <form className="painel" onSubmit={enviar}>
          <h2>Novo MMV</h2>
          <div className="grade">
            <label>
              Código do MMV
              <input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="EX-SEDAN-1.0-2027" required />
            </label>
            <label>
              NCM
              <input value={ncm} onChange={(e) => setNcm(e.target.value)} placeholder="8703.22.10" required />
            </label>
            <label>
              Nível de reciclabilidade
              <select value={nivel} onChange={(e) => setNivel(Number(e.target.value) === 2 ? 2 : 1)}>
                <option value={1}>Nível 1 — RM 10 (10 veículos novos por URV)</option>
                <option value={2}>Nível 2 — RM 5 (5 veículos novos por URV)</option>
              </select>
            </label>
            <label>
              Percentual de reciclabilidade (%)
              <input
                value={percentual}
                onChange={(e) => setPercentual(e.target.value)}
                inputMode="decimal"
                pattern="\d{1,3}([.,]\d{1,2})?"
                title="De 0 a 100, com até duas casas decimais"
                placeholder="85"
                required
              />
            </label>
          </div>
          <label className="marcacao">
            <input type="checkbox" checked={jaComercializado} onChange={(e) => setJaComercializado(e.target.checked)} />
            Este MMV já é comercializado
          </label>
          <p className="alerta alerta-info">
            {jaComercializado
              ? "MMV já comercializado: o cadastro só produz efeitos em 1º de janeiro do ano seguinte. Até lá, consumos com ele são recusados."
              : "MMV novo: o cadastro produz efeitos na data de hoje."}{" "}
            <Artigo>art. 5º §§2º e 3º</Artigo>
          </p>
          <Erro erro={criar.error} titulo="O MMV não foi cadastrado" />
          <div className="linha">
            <button type="submit" disabled={criar.isPending}>
              Cadastrar MMV
            </button>
          </div>
        </form>
      )}
    </>
  );
}
