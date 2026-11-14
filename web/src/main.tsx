import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { MOCK_LIGADO } from "./lib/ambiente";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

async function iniciar() {
  // VITE_MOCK=1 (npm run dev:mock): rotas simuladas no navegador enquanto os backends não chegam.
  if (MOCK_LIGADO) {
    const { iniciarMock } = await import("./mocks/browser");
    await iniciarMock();
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}

void iniciar();
