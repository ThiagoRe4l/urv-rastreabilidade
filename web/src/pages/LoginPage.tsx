import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "../api/auth";
import { ErroHttp } from "../api/cliente";
import { gravarToken } from "../auth/sessao";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const navegar = useNavigate();
  const queryClient = useQueryClient();

  const entrar = useMutation({
    mutationFn: () => login(email, senha),
    onSuccess: (dados) => {
      gravarToken(dados.access_token);
      queryClient.setQueryData(["me"], dados.usuario);
      navegar("/");
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    entrar.mutate();
  }

  const erro = entrar.error instanceof ErroHttp ? entrar.error.corpo.detail : entrar.error?.message;

  return (
    <main className="cartao">
      <h1>URV Rastreabilidade</h1>
      <p className="sutil">Portaria GM/MDIC nº 325/2026</p>
      <form onSubmit={enviar}>
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
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" disabled={entrar.isPending}>
          {entrar.isPending ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
