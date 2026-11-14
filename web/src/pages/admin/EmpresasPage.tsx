import { useMutation, useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import {
  atualizarCredenciamento,
  atualizarEmpresa,
  atualizarVinculo,
  criarEmpresa,
  criarVinculo,
  listarEmpresas,
  listarVinculos,
} from "../../api";
import type { CredenciamentoStatus, Empresa, TipoEmpresa, Vinculo } from "../../api/types";
import { Erro } from "../../components/Erro";
import { Artigo, Consulta, Selecao, Selo, Titulo, type Tom } from "../../components/ui";
import { ROTULO_CREDENCIAMENTO, ROTULO_TIPO_EMPRESA } from "../../lib/dominio";
import { cnpjValido, fmtCnpj, fmtData, hojeIso } from "../../lib/formato";
import { useRecarregar } from "../../lib/useRecarregar";

const TOM_CREDENCIAMENTO: Record<CredenciamentoStatus, Tom> = {
  PENDENTE: "aviso",
  ATIVO: "ok",
  SUSPENSO: "erro",
  CANCELADO: "erro",
};

/** Validade padrão do credenciamento: dois anos (art. 16). */
function daquiADoisAnos(): string {
  const hoje = new Date();
  return hojeIso(new Date(hoje.getFullYear() + 2, hoje.getMonth(), hoje.getDate()));
}

function Credenciamento({ empresa }: { empresa: Empresa }) {
  const recarregar = useRecarregar();
  const [editando, setEditando] = useState(false);
  const [status, setStatus] = useState<CredenciamentoStatus>(empresa.credenciamento_status ?? "PENDENTE");
  const [validade, setValidade] = useState(empresa.credenciamento_validade ?? daquiADoisAnos());
  const salvar = useMutation({
    mutationFn: () => atualizarCredenciamento(empresa.id, status, status === "ATIVO" ? validade : validade || null),
    onSuccess: () => {
      setEditando(false);
      recarregar();
    },
  });
  const compromissos = useMutation({
    mutationFn: (valor: boolean) => atualizarEmpresa(empresa.id, valor),
    onSuccess: recarregar,
  });

  if (empresa.tipo === "FABRICANTE") {
    return (
      <>
        <label className="marcacao">
          <input
            type="checkbox"
            checked={empresa.registro_compromissos}
            disabled={compromissos.isPending}
            onChange={(e) => compromissos.mutate(e.target.checked)}
          />
          Registro de compromissos no MDIC <Artigo>art. 8º II</Artigo>
        </label>
        <Erro erro={compromissos.error} />
      </>
    );
  }
  const atual = empresa.credenciamento_status ?? "PENDENTE";
  if (!editando) {
    return (
      <span className="linha">
        <Selo tom={TOM_CREDENCIAMENTO[atual]}>{ROTULO_CREDENCIAMENTO[atual]}</Selo>
        {empresa.credenciamento_validade && <span>até {fmtData(empresa.credenciamento_validade)}</span>}
        {atual === "ATIVO" && !empresa.credenciamento_vigente && <Selo tom="erro">Vencido</Selo>}
        <button type="button" className="botao-secundario botao-pequeno" onClick={() => setEditando(true)}>
          Alterar
        </button>
      </span>
    );
  }
  return (
    <form
      className="linha"
      onSubmit={(e) => {
        e.preventDefault();
        salvar.mutate();
      }}
    >
      <Selecao valor={status} aoMudar={setStatus} opcoes={ROTULO_CREDENCIAMENTO} />
      <input
        type="date"
        value={validade}
        onChange={(e) => setValidade(e.target.value)}
        required={status === "ATIVO"}
        aria-label="Validade do credenciamento"
      />
      <button type="submit" className="botao-pequeno" disabled={salvar.isPending}>
        Salvar
      </button>
      <button type="button" className="botao-secundario botao-pequeno" onClick={() => setEditando(false)}>
        Cancelar
      </button>
      <Erro erro={salvar.error} />
    </form>
  );
}

function NovaEmpresa() {
  const recarregar = useRecarregar();
  const [cnpj, setCnpj] = useState("");
  const [razao, setRazao] = useState("");
  const [tipo, setTipo] = useState<TipoEmpresa>("DESMONTADORA");
  const [compromissos, setCompromissos] = useState(false);
  const cnpjOk = cnpjValido(cnpj);
  const criar = useMutation({
    mutationFn: () =>
      criarEmpresa({
        cnpj: cnpj.replace(/\D/g, ""),
        razao_social: razao.trim(),
        tipo,
        registro_compromissos: tipo === "FABRICANTE" ? compromissos : null,
      }),
    onSuccess: () => {
      setCnpj("");
      setRazao("");
      recarregar();
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (cnpjOk) criar.mutate();
  }

  return (
    <form className="painel" onSubmit={enviar}>
      <h2>Nova empresa</h2>
      <div className="grade">
        <label>
          CNPJ
          <input
            value={cnpj}
            onChange={(e) => setCnpj(e.target.value)}
            placeholder="00.000.000/0000-00"
            aria-invalid={cnpj !== "" && !cnpjOk}
            required
          />
          {cnpj !== "" && !cnpjOk && <span className="erro">CNPJ inválido</span>}
        </label>
        <label>
          Razão social
          <input value={razao} onChange={(e) => setRazao(e.target.value)} minLength={2} required />
        </label>
        <label>
          Tipo
          <Selecao valor={tipo} aoMudar={setTipo} opcoes={ROTULO_TIPO_EMPRESA} />
        </label>
      </div>
      {tipo === "FABRICANTE" ? (
        <label className="marcacao">
          <input type="checkbox" checked={compromissos} onChange={(e) => setCompromissos(e.target.checked)} />
          Tem registro de compromissos no MDIC <Artigo>art. 8º II</Artigo>
        </label>
      ) : (
        <p className="sutil">
          A empresa entra com credenciamento pendente; ative-o na tabela acima, com validade de dois anos.{" "}
          <Artigo>arts. 11 e 16</Artigo>
        </p>
      )}
      <Erro erro={criar.error} titulo="A empresa não foi criada" />
      <div className="linha">
        <button type="submit" disabled={criar.isPending}>
          Criar empresa
        </button>
      </div>
    </form>
  );
}

function LinhaVinculo({ vinculo }: { vinculo: Vinculo }) {
  const recarregar = useRecarregar();
  const alternar = useMutation({ mutationFn: () => atualizarVinculo(vinculo.id, !vinculo.ativo), onSuccess: recarregar });
  return (
    <tr>
      <td>
        {vinculo.geradora.razao_social}
        <div className="sutil">{ROTULO_TIPO_EMPRESA[vinculo.geradora.tipo]}</div>
      </td>
      <td>{vinculo.fabricante.razao_social}</td>
      <td>
        <Selo tom={vinculo.ativo ? "ok" : "neutro"}>{vinculo.ativo ? "Ativo" : "Inativo"}</Selo>
      </td>
      <td>
        <button type="button" className="botao-secundario botao-pequeno" disabled={alternar.isPending} onClick={() => alternar.mutate()}>
          {vinculo.ativo ? "Desativar" : "Reativar"}
        </button>
        <Erro erro={alternar.error} />
      </td>
    </tr>
  );
}

function NovoVinculo({ empresas }: { empresas: Empresa[] }) {
  const recarregar = useRecarregar();
  const geradoras = empresas.filter((e) => e.tipo !== "FABRICANTE");
  const fabricantes = empresas.filter((e) => e.tipo === "FABRICANTE");
  const [geradora, setGeradora] = useState("");
  const [fabricante, setFabricante] = useState("");
  const criar = useMutation({
    mutationFn: () => criarVinculo(geradora || geradoras[0].id, fabricante || fabricantes[0].id),
    onSuccess: recarregar,
  });
  if (geradoras.length === 0 || fabricantes.length === 0) return null;
  return (
    <form
      className="grade grade-compacta"
      onSubmit={(e) => {
        e.preventDefault();
        criar.mutate();
      }}
    >
      <label>
        Desmontadora ou recicladora
        <select value={geradora || geradoras[0].id} onChange={(e) => setGeradora(e.target.value)}>
          {geradoras.map((e) => (
            <option key={e.id} value={e.id}>
              {e.razao_social}
            </option>
          ))}
        </select>
      </label>
      <label>
        Fabricante
        <select value={fabricante || fabricantes[0].id} onChange={(e) => setFabricante(e.target.value)}>
          {fabricantes.map((e) => (
            <option key={e.id} value={e.id}>
              {e.razao_social}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={criar.isPending}>
        Criar vínculo
      </button>
      <Erro erro={criar.error} titulo="O vínculo não foi criado" />
    </form>
  );
}

/** Empresas, credenciamento e vínculos, lançados pelo administrador (RF-01, RF-02). */
export function EmpresasPage() {
  const empresas = useQuery({ queryKey: ["empresas", ""], queryFn: () => listarEmpresas() });
  const vinculos = useQuery({ queryKey: ["vinculos"], queryFn: listarVinculos });

  return (
    <>
      <Titulo titulo="Empresas e vínculos" sub="Cadastro das empresas, situação do credenciamento e vínculos comerciais." />
      <section className="painel">
        <h2>Empresas</h2>
        <Consulta consulta={empresas} vazio={(d) => d.itens.length === 0 && "Nenhuma empresa cadastrada."}>
          {(d) => (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Razão social</th>
                  <th>CNPJ</th>
                  <th>Tipo</th>
                  <th>
                    Credenciamento <Artigo>arts. 11 e 16</Artigo>
                  </th>
                </tr>
              </thead>
              <tbody>
                {d.itens.map((e) => (
                  <tr key={e.id}>
                    <td>{e.razao_social}</td>
                    <td>{fmtCnpj(e.cnpj)}</td>
                    <td>{ROTULO_TIPO_EMPRESA[e.tipo]}</td>
                    <td>
                      <Credenciamento empresa={e} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Consulta>
      </section>
      <NovaEmpresa />
      <section className="painel">
        <h2>
          Vínculos <Artigo>art. 13 §1º VI e §2º</Artigo>
        </h2>
        <p className="sutil">
          A desmontadora ou recicladora só transfere crédito a fabricante com vínculo ativo. A intermediação é vedada.
        </p>
        <Consulta consulta={vinculos} vazio={(d) => d.itens.length === 0 && "Nenhum vínculo."}>
          {(d) => (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Geradora</th>
                  <th>Fabricante</th>
                  <th>Situação</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {d.itens.map((v) => (
                  <LinhaVinculo key={v.id} vinculo={v} />
                ))}
              </tbody>
            </table>
          )}
        </Consulta>
        {empresas.data && <NovoVinculo empresas={empresas.data.itens} />}
      </section>
    </>
  );
}
