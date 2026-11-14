import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { rastrearPeca } from "../api";
import { Erro } from "../components/Erro";
import { ROTULO_DESTINO_PECA } from "../lib/dominio";
import { fmtCnpj, fmtData } from "../lib/formato";

/** Página pública da etiqueta, aberta pelo QR Code. Não exige login. */
export function RastreioPage() {
  const { codigo = "" } = useParams();
  const [gravado] = useSearchParams();
  const peca = useQuery({ queryKey: ["rastreio", codigo], queryFn: () => rastrearPeca(codigo) });
  // Sem resposta da plataforma, mostra o que o próprio QR Code carrega.
  const d = peca.data ?? {
    nome: gravado.get("nome"),
    chassi: gravado.get("chassi"),
    data: gravado.get("data"),
    cnpj: gravado.get("cnpj"),
  };

  return (
    <main className="cartao cartao-largo">
      <h1>Rastreio de peça</h1>
      <p className="sutil">
        Peça reutilizável de veículo em fim de vida · Portaria GM/MDIC nº 325/2026, art. 18 V
      </p>
      {peca.isPending ? (
        <p className="sutil">Consultando…</p>
      ) : (
        <>
          {peca.data ? (
            <p className="alerta alerta-ok">Etiqueta confirmada pela plataforma.</p>
          ) : (
            <>
              <Erro erro={peca.error} titulo="A plataforma não confirmou esta etiqueta" />
              {d.nome && <p className="sutil">Abaixo, só os dados gravados no QR Code, sem confirmação.</p>}
            </>
          )}
          {d.nome && (
            <dl className="dados">
              <dt>Peça</dt>
              <dd>{d.nome}</dd>
              <dt>Chassi de origem</dt>
              <dd className="mono">{d.chassi}</dd>
              <dt>Data</dt>
              <dd>{fmtData(d.data)}</dd>
              <dt>CNPJ da desmontadora</dt>
              <dd>{fmtCnpj(d.cnpj)}</dd>
              <dt>Código de rastreio</dt>
              <dd className="mono">{codigo}</dd>
              {peca.data && (
                <>
                  <dt>Destino atual</dt>
                  <dd>{peca.data.destino ? ROTULO_DESTINO_PECA[peca.data.destino] : "—"}</dd>
                </>
              )}
            </dl>
          )}
        </>
      )}
    </main>
  );
}
