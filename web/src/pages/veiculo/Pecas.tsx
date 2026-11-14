import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { atualizarPeca, criarPeca } from "../../api";
import type { Etiqueta as DadosEtiqueta, Peca, PecaClassificacao, PecaCondicao, PecaDestino, Veiculo } from "../../api/types";
import { Erro } from "../../components/Erro";
import { Etiqueta } from "../../components/Etiqueta";
import { Artigo, Consulta, Selecao, Selo } from "../../components/ui";
import { ROTULO_CLASSIFICACAO, ROTULO_CONDICAO, ROTULO_DESTINO_PECA } from "../../lib/dominio";
import { useRecarregar } from "../../lib/useRecarregar";
import { usePecasDoVeiculo } from "./apoio";

function LinhaPeca({ peca, podeEscrever, aoEtiquetar }: { peca: Peca; podeEscrever: boolean; aoEtiquetar: (e: DadosEtiqueta) => void }) {
  const recarregar = useRecarregar();
  const alterar = useMutation({
    mutationFn: (dados: { destino?: PecaDestino; descaracterizada?: boolean }) => atualizarPeca(peca.id, dados),
    onSuccess: recarregar,
  });
  return (
    <tr>
      <td>
        <strong>{peca.nome}</strong>
        {peca.descricao && <div className="sutil">{peca.descricao}</div>}
        <Erro erro={alterar.error} />
      </td>
      <td>
        {ROTULO_CLASSIFICACAO[peca.classificacao]}
        <div className="sutil">{ROTULO_CONDICAO[peca.condicao]}</div>
      </td>
      <td>
        {podeEscrever ? (
          <Selecao
            valor={peca.destino}
            aoMudar={(destino) => alterar.mutate({ destino })}
            opcoes={ROTULO_DESTINO_PECA}
            disabled={alterar.isPending}
          />
        ) : (
          ROTULO_DESTINO_PECA[peca.destino]
        )}
      </td>
      <td>
        {peca.classificacao === "REUTILIZAVEL" ? (
          peca.etiqueta ? (
            <span className="linha">
              <span className="mono">{peca.codigo_rastreio}</span>
              <button type="button" className="botao-secundario botao-pequeno" onClick={() => aoEtiquetar(peca.etiqueta!)}>
                Etiqueta
              </button>
            </span>
          ) : (
            <Selo tom="erro">Sem código de rastreio</Selo>
          )
        ) : peca.descaracterizada ? (
          <Selo tom="ok">Descaracterizada</Selo>
        ) : podeEscrever ? (
          <button
            type="button"
            className="botao-secundario botao-pequeno"
            disabled={alterar.isPending}
            onClick={() => alterar.mutate({ descaracterizada: true })}
          >
            Marcar como descaracterizada
          </button>
        ) : (
          <Selo tom="aviso">Falta descaracterizar</Selo>
        )}
      </td>
    </tr>
  );
}

/** Peças retiradas na desmontagem: reutilizáveis recebem etiqueta com QR Code; as demais são descaracterizadas. */
export function Pecas({ veiculo, podeEscrever }: { veiculo: Veiculo; podeEscrever: boolean }) {
  const pecas = usePecasDoVeiculo(veiculo);
  const recarregar = useRecarregar();
  const [etiqueta, setEtiqueta] = useState<DadosEtiqueta | null>(null);
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [classificacao, setClassificacao] = useState<PecaClassificacao>("REUTILIZAVEL");
  const [condicao, setCondicao] = useState<PecaCondicao>("USADA");
  const [destino, setDestino] = useState<PecaDestino>("ESTOQUE");

  const criar = useMutation({
    mutationFn: () => criarPeca(veiculo.id, { nome: nome.trim(), descricao: descricao.trim(), classificacao, condicao, destino }),
    onSuccess: (peca) => {
      setNome("");
      setDescricao("");
      recarregar();
      if (peca.etiqueta) setEtiqueta(peca.etiqueta);
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    criar.mutate();
  }

  return (
    <div className="bloco">
      <h3>
        Peças <Artigo>art. 18 V; Anexo III 6 a 8</Artigo>
      </h3>
      <Consulta consulta={pecas} vazio={(d) => d.length === 0 && "Nenhuma peça registrada."}>
        {(d) => (
          <table className="tabela">
            <thead>
              <tr>
                <th>Peça</th>
                <th>Classificação</th>
                <th>Destino</th>
                <th>Rastreio</th>
              </tr>
            </thead>
            <tbody>
              {d.map((p) => (
                <LinhaPeca key={p.id} peca={p} podeEscrever={podeEscrever} aoEtiquetar={setEtiqueta} />
              ))}
            </tbody>
          </table>
        )}
      </Consulta>
      {podeEscrever && (
        <form className="grade grade-compacta" onSubmit={enviar}>
          <label>
            Nome da peça
            <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Alternador" required />
          </label>
          <label>
            Descrição
            <input value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="Opcional" />
          </label>
          <label>
            Classificação
            <Selecao
              valor={classificacao}
              aoMudar={(v) => {
                setClassificacao(v);
                setDestino(v === "REUTILIZAVEL" ? "ESTOQUE" : "RECICLAGEM");
              }}
              opcoes={ROTULO_CLASSIFICACAO}
            />
          </label>
          <label>
            Condição
            <Selecao valor={condicao} aoMudar={setCondicao} opcoes={ROTULO_CONDICAO} />
          </label>
          <label>
            Destino
            <Selecao valor={destino} aoMudar={setDestino} opcoes={ROTULO_DESTINO_PECA} />
          </label>
          <button type="submit" disabled={criar.isPending}>
            Registrar peça
          </button>
        </form>
      )}
      <Erro erro={criar.error} titulo="A peça não foi registrada" />
      {etiqueta && <Etiqueta etiqueta={etiqueta} aoFechar={() => setEtiqueta(null)} />}
    </div>
  );
}
