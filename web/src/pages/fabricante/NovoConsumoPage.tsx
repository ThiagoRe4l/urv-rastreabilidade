import { useMutation, useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { criarConsumo, listarMmvs, simularConsumo } from "../../api";
import { Erro } from "../../components/Erro";
import { Artigo, Titulo } from "../../components/ui";
import { compararDecimal, formatarDecimal, normalizarEntrada } from "../../lib/decimal";
import { fmtData, hojeIso } from "../../lib/formato";
import { useRecarregar } from "../../lib/useRecarregar";

/** Chassis digitados um por linha (ou separados por vírgula), sem repetição. */
function lerChassis(texto: string): string[] {
  return [...new Set(texto.split(/[\s,;]+/).map((c) => c.trim().toUpperCase()).filter(Boolean))];
}

/** Novo consumo: primeiro a simulação com a memória de cálculo, depois a confirmação (RF-18, RF-19). */
export function NovoConsumoPage() {
  const navegar = useNavigate();
  const recarregar = useRecarregar();
  const mmvs = useQuery({ queryKey: ["mmvs"], queryFn: listarMmvs });
  const [mmvId, setMmvId] = useState("");
  const [periodo, setPeriodo] = useState(hojeIso().slice(0, 7));
  const [preco, setPreco] = useState("");
  const [textoChassis, setTextoChassis] = useState("");

  const hoje = hojeIso();
  const chassis = lerChassis(textoChassis);
  const mmv = mmvs.data?.itens.find((m) => m.id === (mmvId || mmvs.data?.itens[0]?.id));
  const semEfeitos = mmv ? mmv.status !== "ATIVO" || mmv.efeitos_a_partir_de > hoje : false;

  const simular = useMutation({
    mutationFn: () => simularConsumo({ mmv_id: mmv!.id, quantidade: chassis.length, preco_medio: normalizarEntrada(preco, 2) }),
  });
  const confirmar = useMutation({
    mutationFn: () => criarConsumo({ mmv_id: mmv!.id, periodo, preco_medio: normalizarEntrada(preco, 2), chassis }),
    onSuccess: () => {
      recarregar();
      navegar("/consumos");
    },
  });

  // Qualquer mudança nos dados invalida a simulação: só se confirma o que foi simulado.
  function mudar<V>(aplicar: (valor: V) => void) {
    return (valor: V) => {
      aplicar(valor);
      simular.reset();
      confirmar.reset();
    };
  }

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (mmv && chassis.length > 0) simular.mutate();
  }

  const s = simular.data;
  const ficaNegativo = s ? compararDecimal(s.saldo_apos, "0") < 0 : false;

  return (
    <>
      <Titulo
        titulo="Registrar consumo de URV"
        sub="Informe os chassis dos veículos novos comercializados no período. O débito é simulado antes de confirmar."
      />
      {mmvs.data && mmvs.data.itens.length === 0 ? (
        <p className="alerta alerta-aviso">
          Cadastre um MMV antes de registrar consumo. <Link to="/mmvs">Ir para MMVs</Link>
        </p>
      ) : (
        <form className="painel" onSubmit={enviar}>
          <div className="grade">
            <label>
              MMV
              <select value={mmv?.id ?? ""} onChange={(e) => mudar(setMmvId)(e.target.value)} required>
                {mmvs.data?.itens.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.codigo} — nível {m.nivel} (RM {m.rm})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Período de comercialização
              <input type="month" value={periodo} max={hoje.slice(0, 7)} onChange={(e) => mudar(setPeriodo)(e.target.value)} required />
            </label>
            <label>
              Preço médio de venda (R$)
              <input
                value={preco}
                onChange={(e) => mudar(setPreco)(e.target.value)}
                inputMode="decimal"
                pattern="\d+([.,]\d{1,2})?"
                title="Valor em reais, com até duas casas decimais, sem separador de milhar"
                placeholder="180000,00"
                required
              />
            </label>
            <label className="largo">
              Chassis dos veículos novos (um por linha)
              <textarea
                className="mono"
                rows={5}
                value={textoChassis}
                onChange={(e) => mudar(setTextoChassis)(e.target.value)}
                placeholder={"9BWZZZ377VT004251\n9BWZZZ377VT004252"}
                required
              />
              <span className="sutil">
                {chassis.length} {chassis.length === 1 ? "chassi" : "chassis"} · cada chassi novo consome uma única vez{" "}
                <Artigo>art. 29</Artigo>
              </span>
            </label>
          </div>
          {semEfeitos && mmv && (
            <p className="alerta alerta-aviso">
              Este MMV só produz efeitos a partir de {fmtData(mmv.efeitos_a_partir_de)}; o consumo será recusado até lá.{" "}
              <Artigo>art. 5º §§2º e 3º</Artigo>
            </p>
          )}
          <Erro erro={mmvs.error ?? simular.error} titulo="A simulação falhou" />
          {!s && (
            <div className="linha">
              <button type="submit" disabled={simular.isPending || !mmv || chassis.length === 0}>
                {simular.isPending ? "Simulando…" : "Simular débito"}
              </button>
              <Link to="/consumos">Cancelar</Link>
            </div>
          )}

          {s && (
            <div className="simulacao">
              <h2>Simulação do débito</h2>
              <div className="cartoes">
                <div className="cartao-numero">
                  <span>Débito</span>
                  <strong>{formatarDecimal(s.urv_debito)} URV</strong>
                </div>
                <div className="cartao-numero">
                  <span>Saldo atual</span>
                  <strong>{formatarDecimal(s.saldo_atual)} URV</strong>
                </div>
                <div className={`cartao-numero ${ficaNegativo ? "cartao-alerta" : ""}`}>
                  <span>Saldo após o consumo</span>
                  <strong>{formatarDecimal(s.saldo_apos)} URV</strong>
                </div>
              </div>
              <h3>
                Memória de cálculo <Artigo>art. 3º §3º</Artigo>
              </h3>
              <p className="mono formula">{s.memoria_calculo.formula}</p>
              <dl className="dados">
                <dt>qv — veículos comercializados</dt>
                <dd>{s.memoria_calculo.qv}</dd>
                <dt>rm — veículos novos por URV</dt>
                <dd>{s.memoria_calculo.rm}</dd>
                <dt>pm — preço médio</dt>
                <dd>R$ {formatarDecimal(s.memoria_calculo.pm)}</dd>
                <dt>pb — preço base</dt>
                <dd>R$ {formatarDecimal(s.memoria_calculo.pb)}</dd>
                <dt>pm / pb</dt>
                <dd>{formatarDecimal(s.memoria_calculo.razao_preco)}</dd>
                <dt>max(1, pm / pb)</dt>
                <dd>{formatarDecimal(s.memoria_calculo.multiplicador)}</dd>
                <dt>Débito (duas casas, arredondamento para cima na metade)</dt>
                <dd>
                  <strong>{formatarDecimal(s.urv_debito)} URV</strong>
                </dd>
              </dl>
              {ficaNegativo && (
                <p className="alerta alerta-aviso">
                  Saldo insuficiente — <Artigo>art. 8º, III</Artigo>. Até 31/12/2027 o consumo é aceito com saldo negativo,
                  desde que regularizado até o último dia do terceiro mês seguinte; depois dessa data ele é recusado.{" "}
                  <Artigo>art. 8º §1º</Artigo>
                </p>
              )}
              <Erro erro={confirmar.error} titulo="O consumo não foi registrado" />
              <div className="linha">
                <button type="button" disabled={confirmar.isPending || semEfeitos} onClick={() => confirmar.mutate()}>
                  {confirmar.isPending ? "Registrando…" : "Confirmar consumo"}
                </button>
                <button type="button" className="botao-secundario" onClick={() => simular.reset()}>
                  Alterar dados
                </button>
              </div>
            </div>
          )}
        </form>
      )}
    </>
  );
}
