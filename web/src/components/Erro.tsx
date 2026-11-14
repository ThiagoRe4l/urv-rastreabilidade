import { ErroHttp } from "../api/cliente";
import { ARTIGO_DO_ERRO } from "../lib/dominio";

/**
 * Erro da API em formato legível: a mensagem, o artigo da portaria que sustenta a regra
 * e, quando houver, a lista de pendências (422 de pré-condição).
 */
export function Erro({ erro, titulo }: { erro: unknown; titulo?: string }) {
  if (!erro) return null;
  const corpo = erro instanceof ErroHttp ? erro.corpo : null;
  const mensagem = corpo?.detail ?? (erro instanceof Error ? erro.message : "Erro inesperado");
  const artigo = corpo ? ARTIGO_DO_ERRO[corpo.codigo] : undefined;
  return (
    <div className="alerta alerta-erro" role="alert">
      {titulo && <strong>{titulo}</strong>}
      <p>
        {mensagem}
        {artigo && (
          <>
            {" — "}
            <span className="artigo">{artigo}</span>
          </>
        )}
      </p>
      {corpo?.pendencias && corpo.pendencias.length > 0 && (
        <ul>
          {corpo.pendencias.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
