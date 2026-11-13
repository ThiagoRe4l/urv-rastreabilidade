import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";

import { me } from "../api/auth";
import { apagarToken, lerToken } from "../auth/sessao";

// Placeholder: o agente 03 substitui pelas áreas de cada papel.
export function InicioPage() {
  const navegar = useNavigate();
  const queryClient = useQueryClient();
  const usuario = useQuery({ queryKey: ["me"], queryFn: me, enabled: !!lerToken(), retry: false });

  if (!lerToken() || usuario.isError) return <Navigate to="/login" replace />;
  if (!usuario.data) return <p className="cartao">Carregando…</p>;

  function sair() {
    apagarToken();
    queryClient.clear();
    navegar("/login");
  }

  const { nome, papel, empresa } = usuario.data;
  return (
    <main className="cartao">
      <h1>Olá, {nome}</h1>
      <p>
        Papel: <strong>{papel}</strong>
      </p>
      <p>Empresa: {empresa ? empresa.razao_social : "—"}</p>
      <button type="button" onClick={sair}>
        Sair
      </button>
    </main>
  );
}
