import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { listarDmrs, listarPesagens, obterFatores, obterVeiculo } from "../../api";
import type { VeiculoDetalhe } from "../../api/types";
import { useSessao } from "../../auth/useSessao";
import { Artigo, Consulta, SeloEstado, Titulo } from "../../components/ui";
import { formatarDecimal } from "../../lib/decimal";
import {
  ehGeradora,
  ESTADOS,
  ROTULO_DOC_ENTRADA,
  ROTULO_ESTADO,
  ROTULO_ORIGEM,
  ROTULO_TIPO_VEICULO,
} from "../../lib/dominio";
import { fmtData } from "../../lib/formato";
import { BotaoAnexar } from "./Anexos";
import { type Evidencia, usePecasDoVeiculo } from "./apoio";
import { EtapaCartao } from "./EtapaCartao";
import { LaudoCertificado } from "./LaudoCertificado";
import { Pecas } from "./Pecas";
import { Dmrs, Pesagens } from "./Residuos";

/** Onde o veículo está na sequência de estados. */
function TrilhaDeEstados({ veiculo }: { veiculo: VeiculoDetalhe }) {
  const atual = ESTADOS.indexOf(veiculo.estado);
  return (
    <ol className="trilha" aria-label="Estado do veículo">
      {ESTADOS.map((estado, i) => (
        <li key={estado} className={i < atual ? "feito" : i === atual ? "atual" : ""} aria-current={i === atual ? "step" : undefined}>
          {ROTULO_ESTADO[estado]}
        </li>
      ))}
    </ol>
  );
}

/** Tipo declarado, tipo efetivo e o fator que vale para o crédito (RF-07). */
function Classificacao({ veiculo, podeEscrever }: { veiculo: VeiculoDetalhe; podeEscrever: boolean }) {
  const fatores = useQuery({ queryKey: ["fatores"], queryFn: obterFatores });
  const fator = (tipo: string) => {
    const valor = fatores.data?.itens.find((f) => f.tipo === tipo)?.fator;
    return valor ? formatarDecimal(valor) : "…";
  };
  const temEvidencia = veiculo.anexos.some((a) => a.tipo === "EVIDENCIA_CLASSIFICACAO");
  const rebaixado = veiculo.tipo !== veiculo.tipo_declarado;
  const certificado = veiculo.estado === "CERTIFICADO" || veiculo.estado === "ENCERRADO";

  return (
    <section className="painel">
      <h2>
        Classificação <Artigo>art. 2º §§2º a 5º; art. 6º I c</Artigo>
      </h2>
      <dl className="dados">
        <dt>Tipo declarado</dt>
        <dd>
          {ROTULO_TIPO_VEICULO[veiculo.tipo_declarado]} · fator {fator(veiculo.tipo_declarado)}
        </dd>
        <dt>Tipo efetivo</dt>
        <dd>
          <strong>{ROTULO_TIPO_VEICULO[veiculo.tipo]}</strong> · fator <strong>{fator(veiculo.tipo)}</strong>
        </dd>
      </dl>
      {rebaixado ? (
        <div className="alerta alerta-aviso">
          <p>
            Sem evidência de classificação, o veículo é tratado como sucata inservível e o crédito sai pelo fator{" "}
            {fator(veiculo.tipo)}, em vez de {fator(veiculo.tipo_declarado)}. Anexe a evidência
            {certificado ? "" : " antes de emitir o certificado"} para valer o tipo declarado.{" "}
            <Artigo>art. 2º §5º</Artigo>
          </p>
          {podeEscrever && !certificado && (
            <BotaoAnexar
              veiculoId={veiculo.id}
              tipo="EVIDENCIA_CLASSIFICACAO"
              etapa="RECEPCAO"
              rotulo="Anexar evidência de classificação"
            />
          )}
        </div>
      ) : (
        <p className="sutil">
          {veiculo.tipo === "SUCATA_INSERVIVEL"
            ? "Sucata inservível não exige evidência de classificação."
            : temEvidencia
              ? "Evidência de classificação anexada: vale o tipo declarado."
              : ""}
        </p>
      )}
    </section>
  );
}

/** O que falta para o certificado, direto das pendências que a API calcula (RF-15). */
function PainelPendencias({ veiculo }: { veiculo: VeiculoDetalhe }) {
  const certificado = veiculo.estado === "CERTIFICADO" || veiculo.estado === "ENCERRADO";
  const pendencias = veiculo.pendencias_certificado;
  return (
    <section className="painel pendencias" aria-live="polite">
      <h2>O que falta para o certificado</h2>
      {certificado ? (
        <p className="alerta alerta-ok">Certificado emitido. Nada falta.</p>
      ) : pendencias.length === 0 ? (
        <p className="alerta alerta-ok">
          Tudo pronto: o certificado já pode ser emitido. <a href="#certificado">Ir para a emissão</a>
        </p>
      ) : (
        <>
          <p className="sutil">
            {pendencias.length === 1 ? "1 pendência" : `${pendencias.length} pendências`} <Artigo>art. 18 VIII; art. 8º I</Artigo>
          </p>
          <ul className="lista-pendencias">
            {pendencias.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function DadosDoVeiculo({ veiculo }: { veiculo: VeiculoDetalhe }) {
  return (
    <section className="painel">
      <h2>Dados de entrada</h2>
      <dl className="dados">
        <dt>Chassi</dt>
        <dd className="mono">{veiculo.chassi}</dd>
        <dt>Placa</dt>
        <dd>{veiculo.placa}</dd>
        <dt>Renavam</dt>
        <dd>{veiculo.renavam}</dd>
        <dt>Entrada</dt>
        <dd>{fmtData(veiculo.data_entrada)}</dd>
        <dt>Peso de entrada</dt>
        <dd>{formatarDecimal(veiculo.peso_entrada_kg)} kg</dd>
        <dt>Origem</dt>
        <dd>{ROTULO_ORIGEM[veiculo.origem_aquisicao]}</dd>
        <dt>{ROTULO_DOC_ENTRADA[veiculo.documento_entrada_tipo]}</dt>
        <dd>{veiculo.documento_entrada_numero}</dd>
        <dt>Certidão de baixa</dt>
        <dd>{veiculo.certidao_baixa_numero}</dd>
      </dl>
    </section>
  );
}

function Conteudo({ veiculo }: { veiculo: VeiculoDetalhe }) {
  const usuario = useSessao();
  // Só a geradora dona do veículo escreve; AUDITOR e ADMIN leem.
  const podeEscrever = ehGeradora(usuario.papel) && usuario.empresa?.id === veiculo.empresa_id;
  const pecas = usePecasDoVeiculo(veiculo);
  const pesagens = useQuery({ queryKey: ["pesagens", veiculo.id], queryFn: () => listarPesagens(veiculo.id) });
  const dmrs = useQuery({ queryKey: ["dmrs", veiculo.id], queryFn: () => listarDmrs(veiculo.id) });

  const fotos = (etapa: string) => veiculo.anexos.filter((a) => a.tipo === "FOTO" && a.etapa_tipo === etapa).length;
  const tem = (tipo: string) => veiculo.anexos.some((a) => a.tipo === tipo);
  const foto = (etapa: string, rotulo: string): Evidencia => {
    const n = fotos(etapa);
    return { rotulo, ok: n > 0, anexo: "FOTO", detalhe: n === 1 ? "(1 foto)" : `(${n} fotos)` };
  };

  const listaPecas = pecas.data ?? [];
  const semTratar = listaPecas.filter((p) =>
    p.classificacao === "REUTILIZAVEL" ? !p.codigo_rastreio : !p.descaracterizada,
  ).length;
  const nPesagens = pesagens.data?.total ?? 0;
  const nDmrs = dmrs.data?.total ?? 0;

  const evidenciasDesmontagem: Evidencia[] = veiculo.sem_viabilidade_desmontagem ? [] : [foto("DESMONTAGEM", "Foto da desmontagem")];
  if (listaPecas.length > 0) {
    evidenciasDesmontagem.push({
      rotulo: "Peças reutilizáveis etiquetadas e não reutilizáveis descaracterizadas",
      ok: semTratar === 0,
      detalhe: `(${listaPecas.length} ${listaPecas.length === 1 ? "peça" : "peças"})`,
    });
  }

  return (
    <>
      <Titulo
        titulo={`Veículo ${veiculo.chassi}`}
        sub={
          <>
            Placa {veiculo.placa} · entrada em {fmtData(veiculo.data_entrada)} · <Link to="/veiculos">voltar à lista</Link>
          </>
        }
        acoes={<SeloEstado estado={veiculo.estado} />}
      />
      <TrilhaDeEstados veiculo={veiculo} />

      <div className="duas-colunas">
        <div className="coluna">
          <Classificacao veiculo={veiculo} podeEscrever={podeEscrever} />

          <EtapaCartao
            numero={1}
            tipo="RECEPCAO"
            artigo="art. 6º I; art. 18 III; Anexo III 14.a"
            veiculo={veiculo}
            podeEscrever={podeEscrever}
            evidencias={[
              { rotulo: "Documento de entrada (nota fiscal ou auto de arrematação)", ok: tem("DOCUMENTO_ENTRADA"), anexo: "DOCUMENTO_ENTRADA" },
              { rotulo: "Certidão de baixa", ok: tem("CERTIDAO_BAIXA"), anexo: "CERTIDAO_BAIXA" },
              foto("RECEPCAO", "Foto da recepção"),
            ]}
          />

          <EtapaCartao
            numero={2}
            tipo="DESCONTAMINACAO"
            artigo="art. 18 IV"
            veiculo={veiculo}
            podeEscrever={podeEscrever}
            evidencias={[foto("DESCONTAMINACAO", "Foto da descontaminação")]}
          />

          <EtapaCartao
            numero={3}
            tipo="DESMONTAGEM"
            artigo="art. 18 V"
            veiculo={veiculo}
            podeEscrever={podeEscrever}
            evidencias={evidenciasDesmontagem}
            dispensada={
              veiculo.sem_viabilidade_desmontagem
                ? "Veículo sem viabilidade de desmontagem: segue direto à trituração. A etapa não é exigida para o certificado (Anexo III, item 11)."
                : undefined
            }
          >
            <Pecas veiculo={veiculo} podeEscrever={podeEscrever} />
          </EtapaCartao>

          <EtapaCartao
            numero={4}
            tipo="DESTRUICAO"
            artigo="art. 6º III c; Anexo III 15.c"
            veiculo={veiculo}
            podeEscrever={podeEscrever}
            evidencias={[
              foto("DESTRUICAO", "Foto da destruição e separação dos materiais"),
              { rotulo: "Ao menos uma pesagem de material", ok: nPesagens > 0, detalhe: `(${nPesagens})` },
            ]}
          >
            <Pesagens veiculo={veiculo} podeEscrever={podeEscrever} />
          </EtapaCartao>

          <EtapaCartao
            numero={5}
            tipo="DESTINACAO"
            artigo="art. 6º III d; Anexo III 14.d"
            veiculo={veiculo}
            podeEscrever={podeEscrever}
            evidencias={[{ rotulo: "Ao menos uma DMR emitida", ok: nDmrs > 0, detalhe: `(${nDmrs})` }]}
          >
            <Dmrs veiculo={veiculo} podeEscrever={podeEscrever} />
            <p className="sutil">
              A destinação não bloqueia o certificado. O veículo é encerrado quando esta etapa é concluída com ao menos uma
              DMR.
            </p>
          </EtapaCartao>

          <LaudoCertificado veiculo={veiculo} podeEscrever={podeEscrever} />
        </div>

        <aside className="coluna lateral">
          <PainelPendencias veiculo={veiculo} />
          <DadosDoVeiculo veiculo={veiculo} />
        </aside>
      </div>
    </>
  );
}

/** A tela mais importante: em que etapa o veículo está, o que já tem evidência e o que falta. */
export function VeiculoPage() {
  const { id = "" } = useParams();
  const veiculo = useQuery({ queryKey: ["veiculo", id], queryFn: () => obterVeiculo(id) });
  return <Consulta consulta={veiculo}>{(v) => <Conteudo veiculo={v} />}</Consulta>;
}
