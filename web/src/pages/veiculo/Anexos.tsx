import { useMutation } from "@tanstack/react-query";
import { useRef } from "react";

import { baixarAnexo, enviarAnexo } from "../../api";
import type { Anexo, AnexoTipo, EtapaTipo } from "../../api/types";
import { Erro } from "../../components/Erro";
import { ROTULO_ANEXO } from "../../lib/dominio";
import { fmtDataHora, hashCurto } from "../../lib/formato";
import { useRecarregar } from "../../lib/useRecarregar";

/** Botão que abre o seletor de arquivo e envia o anexo do tipo indicado. */
export function BotaoAnexar({
  veiculoId,
  tipo,
  etapa,
  rotulo,
}: {
  veiculoId: string;
  tipo: AnexoTipo;
  etapa: EtapaTipo;
  rotulo: string;
}) {
  const entrada = useRef<HTMLInputElement>(null);
  const recarregar = useRecarregar();
  const enviar = useMutation({
    mutationFn: (arquivo: File) => enviarAnexo(veiculoId, arquivo, tipo, etapa),
    onSuccess: recarregar,
  });
  return (
    <>
      <input
        ref={entrada}
        type="file"
        hidden
        // Fotos: só imagem. Documentos: imagem ou PDF. Limite de 10 MB no servidor.
        accept={tipo === "FOTO" ? "image/*" : "image/*,application/pdf"}
        onChange={(e) => {
          const arquivo = e.target.files?.[0];
          if (arquivo) enviar.mutate(arquivo);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        className="botao-secundario botao-pequeno"
        disabled={enviar.isPending}
        onClick={() => entrada.current?.click()}
      >
        {enviar.isPending ? "Enviando…" : rotulo}
      </button>
      <Erro erro={enviar.error} titulo="O arquivo não foi anexado" />
    </>
  );
}

/** Lista dos anexos de uma etapa. O arquivo exige token, então é baixado e aberto em outra aba. */
export function ListaAnexos({ anexos }: { anexos: Anexo[] }) {
  const abrir = useMutation({
    mutationFn: async (id: string) => {
      // A aba é aberta antes do download para não ser barrada pelo bloqueador de pop-up.
      const aba = window.open("", "_blank");
      try {
        const url = URL.createObjectURL(await baixarAnexo(id));
        if (aba) aba.location.href = url;
        else window.location.assign(url);
      } catch (erro) {
        aba?.close();
        throw erro;
      }
    },
  });
  if (anexos.length === 0) return null;
  return (
    <>
      <ul className="anexos">
        {anexos.map((a) => (
          <li key={a.id}>
            <button type="button" className="botao-link" onClick={() => abrir.mutate(a.id)}>
              {ROTULO_ANEXO[a.tipo]}
              {a.nome_original ? `: ${a.nome_original}` : ""}
            </button>
            <span className="sutil">
              {fmtDataHora(a.criado_em)} · sha256 <span className="mono">{hashCurto(a.sha256)}</span>
            </span>
          </li>
        ))}
      </ul>
      <Erro erro={abrir.error} titulo="Não foi possível abrir o arquivo" />
    </>
  );
}
