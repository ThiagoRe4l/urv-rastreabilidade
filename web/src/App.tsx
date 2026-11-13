import { Navigate, Route, Routes } from "react-router-dom";

import { InicioPage } from "./pages/InicioPage";
import { LoginPage } from "./pages/LoginPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<InicioPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
