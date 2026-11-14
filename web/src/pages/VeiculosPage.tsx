import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listarVeiculos } from "../api";
import type { EstadoVeiculo } from "../api/types";
import { useSessao } from "../auth/useSessao";
import { Consulta, Selecao, SeloEstado, Titulo } from "../components/ui";
import { ehGeradora, ROTULO_ESTADO, ROTULO_TIPO_VEICULO } from "../lib/dominio";
import { fmtData } from "../lib/formato";

export function VeiculosPage() {
  const { papel } = useSessao();
  const [estado, setEstado] = useState<EstadoVeiculo | "">("");
  const [chassi, setChassi] = useState("");
  const veiculos = useQuery({
    queryKey: ["veiculos", estado, chassi],
    queryFn: () => listarVeiculos({ estado, chassi: chassi.trim() }),
  });

  return (
    <>
      <Titulo
        titulo="Veículos em fim de vida"
        sub="Cada veículo percorre recepção, descontaminação, desmontagem, destruição e destinação até o certificado."
        acoes={
          ehGeradora(papel) && (
            <Link className="botao" to="/veiculos/novo">
              Receber veículo
            </Link>
          )
        }
      />
      <div className="painel filtros">
        <label>
          Estado
          <Selecao valor={estado} aoMudar={setEstado} opcoes={ROTULO_ESTADO} vazio="Todos" />
        </label>
        <label>
          Chassi
          <input value={chassi} onChange={(e) => setChassi(e.target.value)} placeholder="Parte do chassi" />
        </label>
      </div>
      <div className="painel">
        <Consulta consulta={veiculos} vazio={(d) => d.itens.length === 0 && "Nenhum veículo encontrado."}>
          {(d) => (
            <table className="tabela">
              <thead>
                <tr>
                  <th>Chassi</th>
                  <th>Placa</th>
                  <th>Tipo efetivo</th>
                  <th>Entrada</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {d.itens.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <Link className="mono" to={`/veiculos/${v.id}`}>
                        {v.chassi}
                      </Link>
                    </td>
                    <td>{v.placa}</td>
                    <td>
                      {ROTULO_TIPO_VEICULO[v.tipo]}
                      {v.tipo !== v.tipo_declarado && <span className="sutil"> (aguarda evidência)</span>}
                    </td>
                    <td>{fmtData(v.data_entrada)}</td>
                    <td>
                      <SeloEstado estado={v.estado} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Consulta>
      </div>
    </>
  );
}
