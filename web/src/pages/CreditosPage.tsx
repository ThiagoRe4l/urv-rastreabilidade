import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listarCreditos, listarEmpresas, obterSaldo, transferirCredito } from "../api";
import type { Credito, Empresa } from "../api/types";
import { Erro } from "../components/Erro";
import { Extrato } from "../components/Extrato";
import { Artigo, Consulta, Selo, Titulo } from "../components/ui";
import { formatarDecimal } from "../lib/decimal";
import { ROTULO_CREDITO } from "../lib/dominio";
import { fmtDataHora } from "../lib/formato";
import { useRecarregar } from "../lib/useRecarregar";

function Transferir({ credito, fabricantes }: { credito: Credito; fabricantes: Empresa[] }) {
  const recarregar = useRecarregar();
  const [fabricante, setFabricante] = useState(fabricantes[0]?.id ?? "");
  const [confirmando, setConfirmando] = useState(false);
  const transferir = useMutation({
    mutationFn: () => transferirCredito(credito.id, fabricante),
    onSuccess: recarregar,
    onSettled: () => setConfirmando(false),
  });

  if (fabricantes.length === 0) {
    return (
      <span className="sutil">
        Sem fabricante com vínculo ativo. <Artigo>art. 13 §1º VI</Artigo>
      </span>
    );
  }
  const nome = fabricantes.find((f) => f.id === fabricante)?.razao_social;
  return (
    <div className="transferir">
      {confirmando ? (
        <>
          <span>
            Transferir {formatarDecimal(credito.quantidade)} URV para <strong>{nome}</strong>? A transferência é única e
            não pode ser desfeita. <Artigo>art. 8º, II e §3º</Artigo>
          </span>
          <span className="linha">
            <button type="button" disabled={transferir.isPending} onClick={() => transferir.mutate()}>
              Confirmar transferência
            </button>
            <button type="button" className="botao-secundario" onClick={() => setConfirmando(false)}>
              Cancelar
            </button>
          </span>
        </>
      ) : (
        <span className="linha">
          <select value={fabricante} onChange={(e) => setFabricante(e.target.value)} aria-label="Fabricante de destino">
            {fabricantes.map((f) => (
              <option key={f.id} value={f.id}>
                {f.razao_social}
              </option>
            ))}
          </select>
          <button type="button" className="botao-pequeno" onClick={() => setConfirmando(true)}>
            Transferir
          </button>
        </span>
      )}
      <Erro erro={transferir.error} titulo="O crédito não foi transferido" />
    </div>
  );
}

/** Créditos de URV da geradora, com a transferência direta e única ao fabricante (RF-16, RF-17). */
export function CreditosPage() {
  const saldo = useQuery({ queryKey: ["saldo"], queryFn: obterSaldo });
  const creditos = useQuery({ queryKey: ["creditos"], queryFn: () => listarCreditos() });
  // A geradora só enxerga as contrapartes com vínculo.
  const fabricantes = useQuery({ queryKey: ["empresas", "FABRICANTE"], queryFn: () => listarEmpresas("FABRICANTE") });

  return (
    <>
      <Titulo
        titulo="Créditos de URV"
        sub="Cada certificado gera um crédito no valor do fator do veículo. O crédito é indivisível e vai inteiro a um único fabricante."
      />
      <div className="cartoes">
        <div className="cartao-numero">
          <span>Saldo disponível</span>
          <strong>{saldo.data ? `${formatarDecimal(saldo.data.saldo)} URV` : "…"}</strong>
        </div>
      </div>
      <Erro erro={saldo.error ?? fabricantes.error} />
      <section className="painel">
        <h2>Créditos gerados</h2>
        <Consulta consulta={creditos} vazio={(d) => d.itens.length === 0 && "Nenhum crédito ainda. O crédito nasce na emissão do certificado."}>
          {(d) => (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Certificado</th>
                  <th>Chassi</th>
                  <th className="num">URV</th>
                  <th>Gerado em</th>
                  <th>Situação</th>
                  <th>Transferência</th>
                </tr>
              </thead>
              <tbody>
                {d.itens.map((c) => (
                  <tr key={c.id}>
                    <td className="mono">{c.certificado?.numero ?? "—"}</td>
                    <td className="mono">{c.chassi ?? "—"}</td>
                    <td className="num">{formatarDecimal(c.quantidade)}</td>
                    <td>{fmtDataHora(c.criado_em)}</td>
                    <td>
                      <Selo tom={c.status === "DISPONIVEL" ? "ok" : "neutro"}>{ROTULO_CREDITO[c.status]}</Selo>
                    </td>
                    <td>
                      {c.status === "DISPONIVEL" ? (
                        <Transferir credito={c} fabricantes={fabricantes.data?.itens ?? []} />
                      ) : (
                        <span className="sutil">
                          Já transferido; não pode ser transferido de novo. <Artigo>art. 8º §3º</Artigo>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Consulta>
      </section>
      <section className="painel">
        <h2>Extrato</h2>
        <Extrato />
      </section>
    </>
  );
}
