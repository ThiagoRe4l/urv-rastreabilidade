import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { assinarLaudo, emitirCertificado } from "../../api";
import type { Laudo, VeiculoDetalhe } from "../../api/types";
import { Erro } from "../../components/Erro";
import { Artigo, Selo } from "../../components/ui";
import { formatarDecimal } from "../../lib/decimal";
import { ROTULO_CREDITO, ROTULO_TIPO_VEICULO } from "../../lib/dominio";
import { fmtDataHora, hashCurto } from "../../lib/formato";
import { useRecarregar } from "../../lib/useRecarregar";
import { useCertificadoDoVeiculo } from "./apoio";

function DadosLaudo({ laudo }: { laudo: Laudo }) {
  return (
    <dl className="dados">
      <dt>Responsável técnico</dt>
      <dd>
        {laudo.responsavel_nome} · registro {laudo.responsavel_registro}
      </dd>
      <dt>Assinado em</dt>
      <dd>{fmtDataHora(laudo.assinado_em)}</dd>
      <dt>Hash do conteúdo</dt>
      <dd className="mono" title={laudo.hash_conteudo}>
        {hashCurto(laudo.hash_conteudo)}
      </dd>
    </dl>
  );
}

/** Laudo de Reciclagem (RF-14) e Certificado de Reciclagem Veicular com o crédito de URV (RF-15, RF-16). */
export function LaudoCertificado({ veiculo, podeEscrever }: { veiculo: VeiculoDetalhe; podeEscrever: boolean }) {
  const recarregar = useRecarregar();
  const certificado = useCertificadoDoVeiculo(veiculo);
  const [nome, setNome] = useState("");
  const [registro, setRegistro] = useState("");

  const laudo = useMutation({
    mutationFn: () => assinarLaudo(veiculo.id, nome.trim(), registro.trim()),
    onSuccess: recarregar,
  });
  const emitir = useMutation({ mutationFn: () => emitirCertificado(veiculo.id), onSuccess: recarregar });

  const temLaudo = veiculo.estado !== "RECEBIDO" && veiculo.estado !== "EM_PROCESSO";
  const temCertificado = veiculo.estado === "CERTIFICADO" || veiculo.estado === "ENCERRADO";
  const cert = certificado.data ?? emitir.data ?? null;
  const dadosLaudo = cert?.laudo ?? laudo.data ?? null;
  const etapaConcluida = (tipo: string) => veiculo.etapas.some((e) => e.tipo === tipo && e.concluida_em);
  const laudoLiberado = etapaConcluida("DESCONTAMINACAO") && etapaConcluida("DESTRUICAO");

  function enviarLaudo(e: FormEvent) {
    e.preventDefault();
    laudo.mutate();
  }

  return (
    <>
      <section className={`painel etapa etapa-${temLaudo ? "concluida" : "pendente"}`} id="laudo">
        <header className="etapa-cabecalho">
          <span className="etapa-numero">{temLaudo ? "✓" : "6"}</span>
          <div>
            <h2>Laudo de Reciclagem</h2>
            <Artigo>art. 18 VII; Anexo III 15.b</Artigo>
          </div>
          <div className="etapa-situacao">{temLaudo ? <Selo tom="ok">Assinado</Selo> : <Selo>Não emitido</Selo>}</div>
        </header>
        {temLaudo ? (
          dadosLaudo ? (
            <DadosLaudo laudo={dadosLaudo} />
          ) : (
            <p className="sutil">Laudo assinado pelo responsável técnico.</p>
          )
        ) : (
          <>
            {!laudoLiberado && (
              <p className="alerta alerta-info">
                O laudo exige as etapas de descontaminação e de destruição concluídas. <Artigo>art. 18 VII</Artigo>
              </p>
            )}
            {podeEscrever && (
              <form className="grade grade-compacta" onSubmit={enviarLaudo}>
                <label>
                  Responsável técnico
                  <input value={nome} onChange={(e) => setNome(e.target.value)} required />
                </label>
                <label>
                  Registro profissional
                  <input value={registro} onChange={(e) => setRegistro(e.target.value)} placeholder="CREA-PR 12345" required />
                </label>
                <button type="submit" disabled={laudo.isPending}>
                  Assinar laudo
                </button>
              </form>
            )}
            <p className="sutil">A assinatura é simulada neste MVP; não é ICP-Brasil.</p>
          </>
        )}
        <Erro erro={laudo.error} titulo="O laudo não foi assinado" />
      </section>

      <section className={`painel etapa etapa-${temCertificado ? "concluida" : "pendente"}`} id="certificado">
        <header className="etapa-cabecalho">
          <span className="etapa-numero">{temCertificado ? "✓" : "7"}</span>
          <div>
            <h2>Certificado de Reciclagem Veicular</h2>
            <Artigo>art. 18 VIII; art. 8º I</Artigo>
          </div>
          <div className="etapa-situacao">{temCertificado ? <Selo tom="ok">Emitido</Selo> : <Selo>Não emitido</Selo>}</div>
        </header>
        {temCertificado ? (
          cert ? (
            <>
              <dl className="dados">
                <dt>Número</dt>
                <dd className="mono">{cert.numero}</dd>
                <dt>Emitido em</dt>
                <dd>{fmtDataHora(cert.emitido_em)}</dd>
                <dt>Tipo do veículo</dt>
                <dd>{ROTULO_TIPO_VEICULO[cert.tipo_veiculo]}</dd>
                <dt>Fator</dt>
                <dd>
                  {formatarDecimal(cert.fator)} <Artigo>art. 3º §2º</Artigo>
                </dd>
                <dt>Percentual aproveitado</dt>
                <dd>
                  {cert.percentual_aproveitado ? `${formatarDecimal(cert.percentual_aproveitado, 2)}%` : "—"}
                  {cert.meta_ano && ` · meta ${formatarDecimal(cert.meta_ano)}%`}
                  {cert.atende_meta === true && " · atende"}
                  {cert.atende_meta === false && " · abaixo da meta"}
                </dd>
                <dt>Hash do conteúdo</dt>
                <dd className="mono" title={cert.hash_conteudo}>
                  {hashCurto(cert.hash_conteudo)}
                </dd>
              </dl>
              {cert.credito && (
                <p className="alerta alerta-ok">
                  Crédito gerado: <strong>{formatarDecimal(cert.credito.quantidade)} URV</strong> ·{" "}
                  {ROTULO_CREDITO[cert.credito.status]}. <Artigo>art. 3º §§1º e 2º</Artigo>{" "}
                  {podeEscrever && <Link to="/creditos">Ver créditos e transferir</Link>}
                </p>
              )}
            </>
          ) : (
            <p className="sutil">{certificado.isPending ? "Carregando…" : "Certificado emitido."}</p>
          )
        ) : (
          <>
            <p className="sutil">
              O certificado só sai com todas as etapas e evidências completas. A emissão gera o crédito de URV no valor do
              fator do veículo; um chassi gera crédito uma única vez. <Artigo>arts. 28 e 29</Artigo>
            </p>
            {podeEscrever && (
              <button type="button" disabled={emitir.isPending} onClick={() => emitir.mutate()}>
                {emitir.isPending ? "Emitindo…" : "Emitir certificado"}
              </button>
            )}
          </>
        )}
        <Erro erro={emitir.error} titulo="O certificado não foi emitido" />
        <Erro erro={certificado.error} />
      </section>
    </>
  );
}
