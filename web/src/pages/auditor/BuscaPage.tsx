import { useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Artigo, Consulta, SeloEstado, Titulo } from "../../components/ui";
import { formatarDecimal } from "../../lib/decimal";
import { ROTULO_TIPO_VEICULO } from "../../lib/dominio";
import { fmtData, fmtDataHora, fmtPeriodo } from "../../lib/formato";
import { TabelaEventos } from "./AuditoriaPage";
import { type LinhaDoTempo, montarLinhaDoTempo } from "./linhaDoTempo";

const ROTULO_FASE = { fluxo: "Processo", documento: "Documento", urv: "URV" } as const;

function Resultado({ r }: { r: LinhaDoTempo }) {
  return (
    <>
      {r.consumosDoChassi.length > 0 && (
        <section className="painel">
          <h2>Chassi de veículo novo</h2>
          {r.consumosDoChassi.map((c) => (
            <p key={c.id}>
              O chassi <span className="mono">{r.chassi}</span> foi informado em consumo de{" "}
              <strong>{formatarDecimal(c.urv_debito)} URV</strong>, período {fmtPeriodo(c.periodo)}, registrado em{" "}
              {fmtDataHora(c.registrado_em)}. Um chassi novo consome uma única vez. <Artigo>art. 29</Artigo>
            </p>
          ))}
        </section>
      )}
      {!r.veiculo ? (
        r.consumosDoChassi.length === 0 && (
          <p className="alerta alerta-info">Nenhum veículo em fim de vida nem consumo com o chassi {r.chassi}.</p>
        )
      ) : (
        <>
          <section className="painel">
            <div className="titulo">
              <h2>
                Veículo em fim de vida <span className="mono">{r.veiculo.chassi}</span>
              </h2>
              <SeloEstado estado={r.veiculo.estado} />
            </div>
            <dl className="dados">
              <dt>Placa</dt>
              <dd>{r.veiculo.placa}</dd>
              <dt>Entrada</dt>
              <dd>{fmtData(r.veiculo.data_entrada)}</dd>
              <dt>Tipo efetivo</dt>
              <dd>{ROTULO_TIPO_VEICULO[r.veiculo.tipo]}</dd>
              <dt>Certificado</dt>
              <dd>{r.certificado ? r.certificado.numero : "não emitido"}</dd>
              <dt>Pendências para o certificado</dt>
              <dd>{r.certificado ? "nenhuma" : r.veiculo.pendencias_certificado.length}</dd>
            </dl>
            <Link to={`/veiculos/${r.veiculo.id}`}>Abrir a página do veículo, com anexos e evidências</Link>
          </section>

          <section className="painel">
            <h2>Linha do tempo</h2>
            <ol className="linha-do-tempo">
              {r.marcos.map((m, i) => (
                <li key={i} className={`marco marco-${m.fase}`}>
                  <time>{fmtDataHora(m.quando)}</time>
                  <div>
                    <strong>{m.titulo}</strong> <span className="selo selo-neutro">{ROTULO_FASE[m.fase]}</span>{" "}
                    {m.artigo && <Artigo>{m.artigo}</Artigo>}
                    {m.detalhe && <div className="sutil">{m.detalhe}</div>}
                  </div>
                </li>
              ))}
            </ol>
            <p className="sutil">
              Depois da transferência, a URV entra no saldo do fabricante e deixa de ser identificável por chassi de
              origem; a linha mostra os consumos registrados por esse fabricante a partir de então.
            </p>
          </section>

          <section className="painel">
            <h2>Eventos da trilha de auditoria ligados ao veículo</h2>
            {r.eventos.length === 0 ? (
              <p className="sutil">Nenhum evento com este veículo como entidade.</p>
            ) : (
              <TabelaEventos eventos={r.eventos} />
            )}
          </section>
        </>
      )}
    </>
  );
}

/** Busca por chassi com a linha do tempo completa, do recebimento ao consumo (RF-23). */
export function BuscaPage() {
  const [params, setParams] = useSearchParams();
  const chassi = params.get("chassi") ?? "";
  const [texto, setTexto] = useState(chassi);
  const linha = useQuery({
    queryKey: ["linha-do-tempo", chassi],
    queryFn: () => montarLinhaDoTempo(chassi),
    enabled: chassi !== "",
  });

  function buscar(e: FormEvent) {
    e.preventDefault();
    setParams(texto.trim() ? { chassi: texto.trim().toUpperCase() } : {});
  }

  return (
    <>
      <Titulo titulo="Busca por chassi" sub="Toda a história de um veículo: recebimento, etapas, documentos, crédito, transferência e consumo." />
      <form className="painel filtros" onSubmit={buscar}>
        <label className="cresce">
          Chassi
          <input className="mono" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="17 caracteres" required />
        </label>
        <button type="submit">Buscar</button>
      </form>
      {chassi !== "" && <Consulta consulta={linha}>{(r) => <Resultado r={r} />}</Consulta>}
    </>
  );
}
