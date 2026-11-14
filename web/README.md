# URV Rastreabilidade — web

Aplicação React com uma área por papel. Fala com a API em `/api/v1` (o Vite repassa para `API_PROXY_TARGET`, por padrão `http://localhost:8000`).

## Rodar

| Comando | O que faz |
| --- | --- |
| `npm run dev` | Sobe em `http://localhost:5173` contra a API real. |
| `npm run dev:mock` | O mesmo, com `VITE_MOCK=1`: todas as rotas são simuladas no navegador por MSW. Não precisa de backend. |
| `npm run tipos` | Regenera `src/api/schema.d.ts` a partir de `http://localhost:8000/openapi.json` (a API precisa estar no ar). |
| `npm test` | Testes (vitest): o roteiro de demonstração inteiro contra o backend simulado, e as contas em decimal. |
| `npm run build` | Checagem de tipos e build de produção. O mock não entra no pacote. |
| `npm run lint` | ESLint. |

No `docker compose up` o mock fica desligado. Para demonstrar sem os backends, use `npm run dev:mock` nesta pasta.

Usuários de demonstração (senha `demo1234`): `admin@urv.local`, `operador@desmonte.local`, `fiscal@montadora.local`, `auditor@mdic.local`.

## Modo demonstração (mock)

- `src/mocks/servidor.ts` é um backend em memória, escrito a partir de `docs/03-contrato-api.md` e das regras de `docs/02-arquitetura.md`. É uma função pura (requisição → resposta); `src/mocks/browser.ts` só a liga ao MSW.
- O estado fica no `localStorage`, para que a página pública da etiqueta (`/rastreio/:codigo`), aberta em outra aba pelo QR Code, veja as mesmas peças. Os arquivos anexados ficam só em memória e somem ao recarregar.
- A faixa amarela no topo tem dois botões: **Reiniciar dados** e **Adulterar um evento**, que faz o papel de `scripts/adulterar.py` para o passo 9 do roteiro.
- Hashes do mock não são SHA-256; servem só para a cadeia quebrar quando um evento muda.

## Tipos da API

`src/api/schema.d.ts` é gerado por `openapi-typescript` a partir do `/openapi.json` da API e fica no repositório, para o build não depender do backend no ar. `src/api/types.ts` só dá nomes curtos aos schemas (`Veiculo = VeiculoSaida`, `Credito = CreditoSaida` etc.). Mudou um schema no backend: rode `npm run tipos` com a API no ar e corrija o que o `tsc` apontar, inclusive no mock, que usa os mesmos tipos.

O mock continua disponível (`npm run dev:mock`) e responde com a forma dos schemas reais. As regras dele são uma cópia simplificada: quem decide é o backend.

## Organização

```
src/
  api/         cliente HTTP, tipos e uma função por rota do contrato
  auth/        token e usuário da sessão
  components/  moldura, erro da API, etiqueta com QR Code, extrato
  lib/         decimal sem float, formatação, rótulos e artigos da portaria
  mocks/       backend simulado (só com VITE_MOCK=1)
  pages/       telas: veiculo/ (a principal), fabricante/, auditor/, admin/
```

Decimais (URV, fator, preço, peso, percentual) trafegam e ficam como string. `src/lib/decimal.ts` compara, soma e formata com `BigInt` em escala fixa e `ROUND_HALF_UP`; nada passa por `float`.
