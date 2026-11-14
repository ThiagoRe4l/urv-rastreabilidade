import qrcode from "qrcode-generator";
import { useMemo } from "react";

import type { Etiqueta as DadosEtiqueta } from "../api/types";
import { fmtCnpj, fmtData } from "../lib/formato";

/**
 * Conteúdo do QR Code: o endereço público da etiqueta com nome, chassi, data e CNPJ na própria URL,
 * de modo que o código carrega os quatro dados mesmo lido fora de linha (RF-09; art. 18 V; Anexo III 6 a 8).
 */
function urlDaEtiqueta(e: DadosEtiqueta): string {
  const dados = new URLSearchParams({ nome: e.nome, chassi: e.chassi, data: e.data, cnpj: e.cnpj });
  return `${window.location.origin}/rastreio/${encodeURIComponent(e.codigo)}?${dados.toString()}`;
}

function QrCode({ conteudo }: { conteudo: string }) {
  const { tamanho, caminho } = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(conteudo);
    qr.make();
    const n = qr.getModuleCount();
    let d = "";
    for (let l = 0; l < n; l++) {
      for (let c = 0; c < n; c++) if (qr.isDark(l, c)) d += `M${c} ${l}h1v1h-1z`;
    }
    return { tamanho: n, caminho: d };
  }, [conteudo]);
  return (
    <svg
      className="qr"
      viewBox={`-2 -2 ${tamanho + 4} ${tamanho + 4}`}
      role="img"
      aria-label="QR Code da etiqueta"
      shapeRendering="crispEdges"
    >
      <rect x="-2" y="-2" width={tamanho + 4} height={tamanho + 4} fill="#fff" />
      <path d={caminho} fill="#000" />
    </svg>
  );
}

/** Etiqueta da peça reutilizável, pronta para imprimir. */
export function Etiqueta({ etiqueta, aoFechar }: { etiqueta: DadosEtiqueta; aoFechar: () => void }) {
  return (
    <div className="sobreposicao" role="dialog" aria-modal="true" aria-label="Etiqueta da peça">
      <div className="etiqueta-caixa">
        <div className="etiqueta imprimivel">
          <QrCode conteudo={urlDaEtiqueta(etiqueta)} />
          <dl>
            <dt>Peça</dt>
            <dd>{etiqueta.nome}</dd>
            <dt>Chassi de origem</dt>
            <dd className="mono">{etiqueta.chassi}</dd>
            <dt>Data</dt>
            <dd>{fmtData(etiqueta.data)}</dd>
            <dt>CNPJ</dt>
            <dd>{fmtCnpj(etiqueta.cnpj)}</dd>
            <dt>Código</dt>
            <dd className="mono">{etiqueta.codigo}</dd>
          </dl>
        </div>
        <div className="linha nao-imprimir">
          <button type="button" onClick={() => window.print()}>
            Imprimir
          </button>
          <a className="botao botao-secundario" href={urlDaEtiqueta(etiqueta)} target="_blank" rel="noreferrer">
            Abrir página pública
          </a>
          <button type="button" className="botao-secundario" onClick={aoFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
