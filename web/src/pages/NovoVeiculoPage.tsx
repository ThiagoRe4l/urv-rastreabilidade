import { useMutation, useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { criarVeiculo, obterFatores } from "../api";
import type { DocumentoEntradaTipo, OrigemAquisicao, TipoVeiculo } from "../api/types";
import { Erro } from "../components/Erro";
import { Artigo, Selecao, Titulo } from "../components/ui";
import { formatarDecimal, normalizarEntrada } from "../lib/decimal";
import { ROTULO_DOC_ENTRADA, ROTULO_ORIGEM, ROTULO_TIPO_VEICULO } from "../lib/dominio";
import { hojeIso } from "../lib/formato";

export function NovoVeiculoPage() {
  const navegar = useNavigate();
  const fatores = useQuery({ queryKey: ["fatores"], queryFn: obterFatores });
  const [f, setF] = useState({
    chassi: "",
    placa: "",
    renavam: "",
    data_entrada: hojeIso(),
    tipo: "SUCATA_APROVEITAVEL" as TipoVeiculo,
    origem_aquisicao: "COMPRA_DIRETA" as OrigemAquisicao,
    documento_entrada_tipo: "NF_ENTRADA" as DocumentoEntradaTipo,
    documento_entrada_numero: "",
    certidao_baixa_numero: "",
    peso_entrada_kg: "",
    sem_viabilidade_desmontagem: false,
  });
  const campo = <K extends keyof typeof f>(chave: K, valor: (typeof f)[K]) => setF((a) => ({ ...a, [chave]: valor }));

  const criar = useMutation({
    mutationFn: () =>
      criarVeiculo({
        ...f,
        chassi: f.chassi.trim().toUpperCase(),
        placa: f.placa.trim().toUpperCase(),
        peso_entrada_kg: normalizarEntrada(f.peso_entrada_kg, 3),
      }),
    onSuccess: (v) => navegar(`/veiculos/${v.id}`),
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    criar.mutate();
  }

  // Rótulo do tipo com o fator vigente (art. 3º §2º).
  const tipos = Object.fromEntries(
    (Object.keys(ROTULO_TIPO_VEICULO) as TipoVeiculo[]).map((t) => {
      const fator = fatores.data?.itens.find((x) => x.tipo === t)?.fator;
      return [t, fator ? `${ROTULO_TIPO_VEICULO[t]} — fator ${formatarDecimal(fator)}` : ROTULO_TIPO_VEICULO[t]];
    }),
  ) as Record<TipoVeiculo, string>;

  return (
    <>
      <Titulo titulo="Receber veículo" sub="Registro de entrada do veículo em fim de vida (art. 6º I; art. 18 III)." />
      <form className="painel" onSubmit={enviar}>
        <div className="grade">
          <label>
            Chassi
            <input
              className="mono"
              value={f.chassi}
              onChange={(e) => campo("chassi", e.target.value)}
              minLength={17}
              maxLength={17}
              placeholder="17 caracteres"
              required
            />
          </label>
          <label>
            Placa
            <input value={f.placa} onChange={(e) => campo("placa", e.target.value)} maxLength={8} required />
          </label>
          <label>
            Renavam
            <input value={f.renavam} onChange={(e) => campo("renavam", e.target.value)} inputMode="numeric" required />
          </label>
          <label>
            Data de entrada
            <input
              type="date"
              value={f.data_entrada}
              max={hojeIso()}
              onChange={(e) => campo("data_entrada", e.target.value)}
              required
            />
          </label>
          <label>
            Peso de entrada (kg)
            <input
              value={f.peso_entrada_kg}
              onChange={(e) => campo("peso_entrada_kg", e.target.value)}
              inputMode="decimal"
              pattern="\d+([.,]\d{1,3})?"
              title="Número em kg, com até três casas decimais"
              placeholder="1180,5"
              required
            />
          </label>
          <label>
            Origem da aquisição <Artigo>art. 18 I</Artigo>
            <Selecao valor={f.origem_aquisicao} aoMudar={(v) => campo("origem_aquisicao", v)} opcoes={ROTULO_ORIGEM} />
          </label>
          <label>
            Documento de entrada
            <Selecao
              valor={f.documento_entrada_tipo}
              aoMudar={(v) => campo("documento_entrada_tipo", v)}
              opcoes={ROTULO_DOC_ENTRADA}
            />
          </label>
          <label>
            Número do documento de entrada
            <input
              value={f.documento_entrada_numero}
              onChange={(e) => campo("documento_entrada_numero", e.target.value)}
              required
            />
          </label>
          <label>
            Número da certidão de baixa
            <input
              value={f.certidao_baixa_numero}
              onChange={(e) => campo("certidao_baixa_numero", e.target.value)}
              required
            />
          </label>
          <label className="largo">
            Tipo declarado do veículo <Artigo>art. 3º §2º</Artigo>
            <Selecao valor={f.tipo} aoMudar={(v) => campo("tipo", v)} opcoes={tipos} />
          </label>
        </div>
        {f.tipo !== "SUCATA_INSERVIVEL" && (
          <p className="alerta alerta-aviso">
            Enquanto não houver evidência de classificação anexada, o veículo é tratado como sucata inservível (fator
            0,38). O tipo declarado fica guardado e passa a valer quando a evidência for anexada, na página do veículo.{" "}
            <Artigo>art. 2º §5º; art. 6º I c</Artigo>
          </p>
        )}
        <label className="marcacao">
          <input
            type="checkbox"
            checked={f.sem_viabilidade_desmontagem}
            onChange={(e) => campo("sem_viabilidade_desmontagem", e.target.checked)}
          />
          Sem viabilidade de desmontagem: segue direto à trituração <Artigo>Anexo III, item 11</Artigo>
        </label>
        <Erro erro={criar.error} titulo="O veículo não foi registrado" />
        <div className="linha">
          <button type="submit" disabled={criar.isPending}>
            {criar.isPending ? "Registrando…" : "Registrar entrada"}
          </button>
          <Link to="/veiculos">Cancelar</Link>
        </div>
      </form>
    </>
  );
}
