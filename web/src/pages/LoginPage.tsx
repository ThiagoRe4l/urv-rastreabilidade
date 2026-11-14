import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "../api/auth";
import { gravarToken } from "../auth/sessao";
import { Erro } from "../components/Erro";
import { MOCK_LIGADO } from "../lib/ambiente";
import { inicioDoPapel } from "../lib/dominio";

// Usuários do seed (docs/03-contrato-api.md). Atalho só no modo demonstração.
const DEMO = [
  ["admin@urv.local", "Administrador"],
  ["operador@desmonte.local", "Desmontadora"],
  ["fiscal@montadora.local", "Fabricante"],
  ["auditor@mdic.local", "Auditor (MDIC)"],
];

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const navegar = useNavigate();
  const queryClient = useQueryClient();

  const entrar = useMutation({
    mutationFn: () => login(email, senha),
    onSuccess: (dados) => {
      gravarToken(dados.access_token);
      queryClient.clear();
      queryClient.setQueryData(["me"], dados.usuario);
      navegar(inicioDoPapel(dados.usuario.papel));
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    entrar.mutate();
  }

  return (
    <main className="cartao">
      <h1>URV Rastreabilidade</h1>
      <p className="sutil">Portaria GM/MDIC nº 325/2026</p>
      <form className="pilha" onSubmit={enviar}>
        <label>
          E-mail
          <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Senha
          <input
            type="password"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
          />
        </label>
        <Erro erro={entrar.error} />
        <button type="submit" disabled={entrar.isPending}>
          {entrar.isPending ? "Entrando…" : "Entrar"}
        </button>
      </form>
      {MOCK_LIGADO && (
        <div className="demo">
          <p className="sutil">Modo demonstração — preencher como:</p>
          <div className="linha">
            {DEMO.map(([endereco, rotulo]) => (
              <button
                key={endereco}
                type="button"
                className="botao-secundario botao-pequeno"
                onClick={() => {
                  setEmail(endereco);
                  setSenha("demo1234");
                }}
              >
                {rotulo}
              </button>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
