import { useMutation, useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { criarDmr, criarPesagem, listarDmrs, listarPesagens } from "../../api";
import type { DestinoPesagem, Fracao, Veiculo } from "../../api/types";
import { Erro } from "../../components/Erro";
import { Artigo, Consulta, Selecao } from "../../components/ui";
import { compararDecimal, formatarDecimal, normalizarEntrada } from "../../lib/decimal";
import { metaDoAno, ROTULO_DESTINO_PESAGEM, ROTULO_FRACAO } from "../../lib/dominio";
import { cnpjValido, fmtCnpj, fmtDataHora } from "../../lib/formato";
import { useRecarregar } from "../../lib/useRecarregar";

const PESO = { inputMode: "decimal", pattern: "\\d+([.,]\\d{1,3})?", title: "Peso em kg, com até três casas decimais" } as const;

/** Percentual aproveitado frente à meta do ano (RF-12). A meta gera alerta, não bloqueia o certificado. */
export function Aproveitamento({ percentual, ano = new Date().getFullYear() }: { percentual: string | null; ano?: number }) {
  const meta = metaDoAno(ano);
  if (percentual === null) return <p className="sutil">O percentual aproveitado aparece depois da primeira pesagem.</p>;
  const atende = meta === null || compararDecimal(percentual, meta) >= 0;
  return (
    <div className={`aproveitamento ${atende ? "atende" : "nao-atende"}`}>
      <div className="aproveitamento-numero">{formatarDecimal(percentual, 2)}%</div>
      <div>
        <strong>do peso destinado foi aproveitado</strong>
        <div className="barra" aria-hidden="true">
          <span style={{ width: `${Math.min(100, Math.max(0, parseFloat(percentual)))}%` }} />
          {meta && <i style={{ left: `${meta}%` }} />}
        </div>
        {meta === null ? (
          <span className="sutil">
            Em {ano} não há meta, só registro. <Artigo>art. 18 §7º</Artigo>
          </span>
        ) : atende ? (
          <span>
            Atende a meta de {meta}% de {ano}. <Artigo>art. 18 §5º</Artigo>
          </span>
        ) : (
          <span>
            Abaixo da meta de {meta}% de {ano}. É um alerta: não impede o certificado, mas o descumprimento é apurado
            pelo MDIC. <Artigo>art. 18 §5º; art. 17 §2º</Artigo>
          </span>
        )}
      </div>
    </div>
  );
}

/** Pesos por fração de material e destino (RF-11). */
export function Pesagens({ veiculo, podeEscrever }: { veiculo: Veiculo; podeEscrever: boolean }) {
  const pesagens = useQuery({ queryKey: ["pesagens", veiculo.id], queryFn: () => listarPesagens(veiculo.id) });
  const recarregar = useRecarregar();
  const [fracao, setFracao] = useState<Fracao>("FERROSO");
  const [destino, setDestino] = useState<DestinoPesagem>("RECICLAGEM");
  const [peso, setPeso] = useState("");
  const criar = useMutation({
    mutationFn: () => criarPesagem(veiculo.id, { fracao, destino, peso_kg: normalizarEntrada(peso, 3) }),
    onSuccess: () => {
      setPeso("");
      recarregar();
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    criar.mutate();
  }

  return (
    <div className="bloco">
      <h3>
        Pesagens por material <Artigo>art. 18 §6º; Anexo III 14.c</Artigo>
      </h3>
      <Consulta consulta={pesagens}>
        {(d) => (
          <>
            <Aproveitamento percentual={d.percentual_aproveitado} />
            {d.itens.length > 0 && (
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Fração</th>
                    <th>Destino</th>
                    <th className="num">Peso (kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {d.itens.map((p) => (
                    <tr key={p.id}>
                      <td>{ROTULO_FRACAO[p.fracao]}</td>
                      <td>{ROTULO_DESTINO_PESAGEM[p.destino]}</td>
                      <td className="num">{formatarDecimal(p.peso_kg)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </Consulta>
      {podeEscrever && (
        <form className="grade grade-compacta" onSubmit={enviar}>
          <label>
            Fração
            <Selecao valor={fracao} aoMudar={setFracao} opcoes={ROTULO_FRACAO} />
          </label>
          <label>
            Destino
            <Selecao valor={destino} aoMudar={setDestino} opcoes={ROTULO_DESTINO_PESAGEM} />
          </label>
          <label>
            Peso (kg)
            <input value={peso} onChange={(e) => setPeso(e.target.value)} placeholder="820,5" required {...PESO} />
          </label>
          <button type="submit" disabled={criar.isPending}>
            Registrar pesagem
          </button>
        </form>
      )}
      <Erro erro={criar.error} titulo="A pesagem não foi registrada" />
    </div>
  );
}

/** Declarações de Movimentação de Resíduos, com o MTR do SINIR simulado (RF-13). */
export function Dmrs({ veiculo, podeEscrever }: { veiculo: Veiculo; podeEscrever: boolean }) {
  const dmrs = useQuery({ queryKey: ["dmrs", veiculo.id], queryFn: () => listarDmrs(veiculo.id) });
  const recarregar = useRecarregar();
  const vazio = { numero: "", destinatario_nome: "", destinatario_cnpj: "", tipo_material: "", peso_kg: "" };
  const [f, setF] = useState(vazio);
  const campo = (chave: keyof typeof vazio, valor: string) => setF((a) => ({ ...a, [chave]: valor }));
  const cnpjOk = cnpjValido(f.destinatario_cnpj);
  const criar = useMutation({
    mutationFn: () =>
      criarDmr(veiculo.id, {
        ...f,
        destinatario_cnpj: f.destinatario_cnpj.replace(/\D/g, ""),
        peso_kg: normalizarEntrada(f.peso_kg, 3),
      }),
    onSuccess: () => {
      setF(vazio);
      recarregar();
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (cnpjOk) criar.mutate();
  }

  return (
    <div className="bloco">
      <h3>
        DMRs <Artigo>art. 6º III d; Anexo III 14.d</Artigo>
      </h3>
      <Consulta consulta={dmrs} vazio={(d) => d.itens.length === 0 && "Nenhuma DMR emitida."}>
        {(d) => (
          <table className="tabela">
            <thead>
              <tr>
                <th>Número</th>
                <th>MTR (simulado)</th>
                <th>Destinatário</th>
                <th>Material</th>
                <th className="num">Peso (kg)</th>
                <th>Emitida em</th>
              </tr>
            </thead>
            <tbody>
              {d.itens.map((x) => (
                <tr key={x.id}>
                  <td>{x.numero}</td>
                  <td className="mono">{x.mtr_numero}</td>
                  <td>
                    {x.destinatario_nome}
                    <div className="sutil">{fmtCnpj(x.destinatario_cnpj)}</div>
                  </td>
                  <td>{x.tipo_material}</td>
                  <td className="num">{formatarDecimal(x.peso_kg)}</td>
                  <td>{fmtDataHora(x.emitida_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Consulta>
      {podeEscrever && (
        <form className="grade grade-compacta" onSubmit={enviar}>
          <label>
            Número da DMR
            <input value={f.numero} onChange={(e) => campo("numero", e.target.value)} required />
          </label>
          <label>
            Destinatário
            <input value={f.destinatario_nome} onChange={(e) => campo("destinatario_nome", e.target.value)} required />
          </label>
          <label>
            CNPJ do destinatário
            <input
              value={f.destinatario_cnpj}
              onChange={(e) => campo("destinatario_cnpj", e.target.value)}
              placeholder="00.000.000/0000-00"
              aria-invalid={f.destinatario_cnpj !== "" && !cnpjOk}
              required
            />
            {f.destinatario_cnpj !== "" && !cnpjOk && <span className="erro">CNPJ inválido</span>}
          </label>
          <label>
            Tipo de material
            <input value={f.tipo_material} onChange={(e) => campo("tipo_material", e.target.value)} placeholder="Sucata ferrosa" required />
          </label>
          <label>
            Peso (kg)
            <input value={f.peso_kg} onChange={(e) => campo("peso_kg", e.target.value)} required {...PESO} />
          </label>
          <button type="submit" disabled={criar.isPending}>
            Emitir DMR
          </button>
        </form>
      )}
      <Erro erro={criar.error} titulo="A DMR não foi emitida" />
    </div>
  );
}
