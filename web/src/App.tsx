import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import type { Papel } from "./api/types";
import { useSessao } from "./auth/useSessao";
import { Layout } from "./components/Layout";
import { inicioDoPapel } from "./lib/dominio";
import { EmpresasPage } from "./pages/admin/EmpresasPage";
import { AuditoriaPage } from "./pages/auditor/AuditoriaPage";
import { BuscaPage } from "./pages/auditor/BuscaPage";
import { PainelPage } from "./pages/auditor/PainelPage";
import { CreditosPage } from "./pages/CreditosPage";
import { ConsumosPage } from "./pages/fabricante/ConsumosPage";
import { DossiePage } from "./pages/fabricante/DossiePage";
import { MmvsPage } from "./pages/fabricante/MmvsPage";
import { NovoConsumoPage } from "./pages/fabricante/NovoConsumoPage";
import { UrvPage } from "./pages/fabricante/UrvPage";
import { LoginPage } from "./pages/LoginPage";
import { NovoVeiculoPage } from "./pages/NovoVeiculoPage";
import { PecasPage } from "./pages/PecasPage";
import { RastreioPage } from "./pages/RastreioPage";
import { VeiculoPage } from "./pages/veiculo/VeiculoPage";
import { VeiculosPage } from "./pages/VeiculosPage";

const GERADORAS: Papel[] = ["DESMONTADORA", "RECICLADORA"];
const LEITURA: Papel[] = ["AUDITOR", "ADMIN"];

/** Só deixa passar os papéis da área; os demais voltam para a própria tela inicial. A API é quem de fato barra. */
function Area({ papeis }: { papeis: Papel[] }) {
  const usuario = useSessao();
  if (!papeis.includes(usuario.papel)) return <Navigate to={inicioDoPapel(usuario.papel)} replace />;
  return <Outlet context={usuario} />;
}

function Inicio() {
  return <Navigate to={inicioDoPapel(useSessao().papel)} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/rastreio/:codigo" element={<RastreioPage />} />
      <Route element={<Layout />}>
        <Route index element={<Inicio />} />
        <Route element={<Area papeis={GERADORAS} />}>
          <Route path="/veiculos/novo" element={<NovoVeiculoPage />} />
          <Route path="/creditos" element={<CreditosPage />} />
        </Route>
        <Route element={<Area papeis={[...GERADORAS, ...LEITURA]} />}>
          <Route path="/veiculos" element={<VeiculosPage />} />
          <Route path="/veiculos/:id" element={<VeiculoPage />} />
          <Route path="/pecas" element={<PecasPage />} />
        </Route>
        <Route element={<Area papeis={["FABRICANTE"]} />}>
          <Route path="/urv" element={<UrvPage />} />
          <Route path="/consumos" element={<ConsumosPage />} />
          <Route path="/consumos/novo" element={<NovoConsumoPage />} />
          <Route path="/dossies/:certificadoId" element={<DossiePage />} />
        </Route>
        <Route element={<Area papeis={["FABRICANTE", ...LEITURA]} />}>
          <Route path="/mmvs" element={<MmvsPage />} />
        </Route>
        <Route element={<Area papeis={LEITURA} />}>
          <Route path="/painel" element={<PainelPage />} />
          <Route path="/busca" element={<BuscaPage />} />
          <Route path="/auditoria" element={<AuditoriaPage />} />
        </Route>
        <Route element={<Area papeis={["ADMIN"]} />}>
          <Route path="/empresas" element={<EmpresasPage />} />
        </Route>
        <Route path="*" element={<Inicio />} />
      </Route>
    </Routes>
  );
}
