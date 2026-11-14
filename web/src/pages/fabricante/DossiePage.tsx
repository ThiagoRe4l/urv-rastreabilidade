import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { listarDmrs, obterCertificado, obterLaudo, obterVeiculo } from "../../api";
import { Artigo, Consulta, Selo, Titulo } from "../../components/ui";
import { formatarDecimal } from "../../lib/decimal";
import { ROTULO_CREDITO, ROTULO_TIPO_VEICULO } from "../../lib/dominio";
import { fmtCnpj, fmtDataHora, hashCurto } from "../../lib/formato";
import { ListaAnexos } from "../veiculo/Anexos";

/**
 * Dossiê do crédito que o fabricante detém: certificado, laudo, anexos e DMRs do veículo de origem.
 * O fabricante guarda e apresenta essa documentação (art. 9º) e responde pela falta dela (art. 10).
 * A API só entrega o dossiê ao titular do crédito; os demais recebem 404.
 */
export function DossiePage() {
  const { certificadoId = "" } = useParams();
  const certificado = useQuery({ queryKey: ["certificado", certificadoId], queryFn: () => obterCertificado(certificadoId) });
  const veiculoId = certificado.data?.veiculo_id;
  const veiculo = useQuery({
    queryKey: ["veiculo", veiculoId],
    queryFn: () => obterVeiculo(veiculoId!),
    enabled: !!veiculoId,
  });
  const laudo = useQuery({ queryKey: ["laudo", veiculoId], queryFn: () => obterLaudo(veiculoId!), enabled: !!veiculoId });
  const dmrs = useQuery({ queryKey: ["dmrs", veiculoId], queryFn: () => listarDmrs(veiculoId!), enabled: !!veiculoId });

  return (
    <>
      <Titulo
        titulo="Dossiê do crédito"
        sub={
          <>
            Documentação comprobatória do veículo que gerou o crédito recebido. <Artigo>art. 9º</Artigo>
          </>
        }
        acoes={
          <Link className="botao-secundario" to="/urv">
            Voltar ao extrato
          </Link>
        }
      />
      <Consulta consulta={certificado}>
        {(c) => (
          <section className="painel">
            <h2>
              Certificado {c.numero} {c.importado && <Selo tom="info">Importado de outra plataforma</Selo>}
            </h2>
            <dl className="dados">
              <dt>Chassi reciclado</dt>
              <dd className="mono">{c.chassi}</dd>
              <dt>Tipo e fator</dt>
              <dd>
                {ROTULO_TIPO_VEICULO[c.tipo_veiculo]} · fator {formatarDecimal(c.fator)}
              </dd>
              <dt>Aproveitamento</dt>
              <dd>
                {c.percentual_aproveitado ? `${formatarDecimal(c.percentual_aproveitado)} % do peso do veículo` : "—"}
                {c.meta_ano && ` · meta do ano ${formatarDecimal(c.meta_ano)} %`} <Artigo>art. 18 §5º</Artigo>
              </dd>
              <dt>Emitido em</dt>
              <dd>{fmtDataHora(c.emitido_em)}</dd>
              <dt>Hash do conteúdo</dt>
              <dd className="mono" title={c.hash_conteudo}>
                {hashCurto(c.hash_conteudo)}
              </dd>
              {c.credito && (
                <>
                  <dt>Crédito</dt>
                  <dd>
                    {formatarDecimal(c.credito.quantidade)} URV · {ROTULO_CREDITO[c.credito.status]}
                  </dd>
                </>
              )}
            </dl>
          </section>
        )}
      </Consulta>
      {veiculoId && (
        <>
          <section className="painel">
            <h2>Laudo de Reciclagem</h2>
            <Consulta consulta={laudo}>
              {(l) => (
                <dl className="dados">
                  <dt>Responsável técnico</dt>
                  <dd>
                    {l.responsavel_nome} · registro {l.responsavel_registro}
                  </dd>
                  <dt>Assinado em</dt>
                  <dd>{fmtDataHora(l.assinado_em)}</dd>
                  <dt>Hash do conteúdo</dt>
                  <dd className="mono" title={l.hash_conteudo}>
                    {hashCurto(l.hash_conteudo)}
                  </dd>
                </dl>
              )}
            </Consulta>
          </section>
          <section className="painel">
            <h2>Anexos</h2>
            <Consulta consulta={veiculo} vazio={(v) => v.anexos.length === 0 && "Nenhum anexo nesta plataforma."}>
              {(v) => <ListaAnexos anexos={v.anexos} />}
            </Consulta>
          </section>
          <section className="painel">
            <h2>
              Declarações de Movimentação de Resíduos <Artigo>art. 6º, III, d</Artigo>
            </h2>
            <Consulta consulta={dmrs} vazio={(d) => d.itens.length === 0 && "Nenhuma DMR emitida."}>
              {(d) => (
                <table className="tabela">
                  <thead>
                    <tr>
                      <th>DMR</th>
                      <th>MTR</th>
                      <th>Destinatário</th>
                      <th>Material</th>
                      <th className="num">Peso (kg)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.itens.map((x) => (
                      <tr key={x.id}>
                        <td className="mono">{x.numero}</td>
                        <td className="mono">{x.mtr_numero}</td>
                        <td>
                          {x.destinatario_nome} · {fmtCnpj(x.destinatario_cnpj)}
                        </td>
                        <td>{x.tipo_material}</td>
                        <td className="num">{formatarDecimal(x.peso_kg)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Consulta>
          </section>
        </>
      )}
    </>
  );
}
