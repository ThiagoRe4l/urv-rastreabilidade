import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";

import { exportarHistorico } from "../api";
import { post } from "../api/cliente";
import type { Papel } from "../api/types";
import { apagarToken, lerToken } from "../auth/sessao";
import { useUsuario } from "../auth/useUsuario";
import { MOCK_LIGADO } from "../lib/ambiente";
import { ehGeradora, inicioDoPapel, ROTULO_PAPEL } from "../lib/dominio";
import { fmtCnpj } from "../lib/formato";
import { Erro } from "./Erro";

function menu(papel: Papel): [string, string][] {
  if (ehGeradora(papel)) {
    return [
      ["/veiculos", "Veículos"],
      ["/pecas", "Peças"],
      ["/creditos", "Créditos de URV"],
    ];
  }
  if (papel === "FABRICANTE") {
    return [
      ["/urv", "Saldo e extrato"],
      ["/mmvs", "MMVs"],
      ["/consumos", "Consumos"],
    ];
  }
  const leitura: [string, string][] = [
    ["/painel", "Painel"],
    ["/busca", "Busca por chassi"],
    ["/auditoria", "Trilha de auditoria"],
  ];
  return papel === "ADMIN" ? [["/empresas", "Empresas e vínculos"], ...leitura] : leitura;
}

function FaixaMock() {
  const queryClient = useQueryClient();
  const acao = useMutation({
    mutationFn: (caminho: string) => post<unknown>(caminho),
    onSuccess: (_, caminho) => {
      if (caminho.endsWith("reiniciar")) {
        apagarToken();
        window.location.assign("/login");
      } else {
        void queryClient.invalidateQueries();
      }
    },
  });
  return (
    <div className="faixa-mock nao-imprimir">
      <span>
        <strong>Modo demonstração.</strong> Os dados são simulados no navegador (VITE_MOCK=1); nenhuma API real é
        chamada.
      </span>
      <span className="linha">
        <button
          type="button"
          className="botao-link"
          title="Faz o papel de scripts/adulterar.py: altera um evento sem recalcular o hash"
          onClick={() => acao.mutate("/__mock/adulterar")}
        >
          Adulterar um evento
        </button>
        <button type="button" className="botao-link" onClick={() => acao.mutate("/__mock/reiniciar")}>
          Reiniciar dados
        </button>
      </span>
      {acao.isSuccess && acao.variables.endsWith("adulterar") && (
        <span>Evento adulterado. Como auditor, use “Verificar integridade”.</span>
      )}
      <Erro erro={acao.error} />
    </div>
  );
}

/** Moldura das áreas autenticadas: cabeçalho com empresa e papel, menu do papel e conteúdo. */
export function Layout() {
  const navegar = useNavigate();
  const queryClient = useQueryClient();
  const usuario = useUsuario();
  const exportar = useMutation({
    mutationFn: exportarHistorico,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "historico-urv.json";
      link.click();
      URL.revokeObjectURL(url);
    },
  });

  if (!lerToken() || usuario.isError) return <Navigate to="/login" replace />;
  if (!usuario.data) return <p className="pagina sutil">Carregando…</p>;

  function sair() {
    apagarToken();
    queryClient.clear();
    navegar("/login");
  }

  const { nome, papel, empresa } = usuario.data;
  return (
    <>
      {MOCK_LIGADO && <FaixaMock />}
      <header className="cabecalho nao-imprimir">
        <div className="cabecalho-linha">
          <NavLink to={inicioDoPapel(papel)} className="marca">
            URV Rastreabilidade
          </NavLink>
          <nav>
            {menu(papel).map(([para, rotulo]) => (
              <NavLink key={para} to={para}>
                {rotulo}
              </NavLink>
            ))}
          </nav>
          <div className="sessao">
            <div>
              <strong>{empresa ? empresa.razao_social : nome}</strong>
              <span>
                {ROTULO_PAPEL[papel]}
                {empresa && ` · CNPJ ${fmtCnpj(empresa.cnpj)}`}
              </span>
            </div>
            {empresa && (
              <button
                type="button"
                className="botao-secundario"
                title="Exporta todo o histórico da empresa em JSON (art. 22; art. 19 §2º)"
                onClick={() => exportar.mutate()}
                disabled={exportar.isPending}
              >
                Exportar histórico
              </button>
            )}
            <button type="button" className="botao-secundario" onClick={sair}>
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="pagina">
        <Erro erro={exportar.error} titulo="Não foi possível exportar" />
        <Outlet context={usuario.data} />
      </main>
    </>
  );
}
