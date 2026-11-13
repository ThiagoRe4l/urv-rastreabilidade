# URV Rastreabilidade

Plataforma de rastreabilidade da desmontagem e reciclagem de veículos em fim de vida, com livro de créditos e débitos de URV (Unidade de Reciclagem Veicular), conforme a Portaria GM/MDIC nº 325/2026 (Programa Mover).

Este é um MVP de avaliação: roda localmente, cobre um fluxo de ponta a ponta e deixa lacunas documentadas. Não é um produto pronto para credenciamento.

## Leia antes de escrever código

1. `docs/01-requisitos.md` — requisitos numerados (RF e RNF) com o artigo de origem.
2. `docs/02-arquitetura.md` — modelo de dados, regras de negócio, trilha de auditoria.
3. `docs/03-contrato-api.md` — contrato da API. É a fonte de verdade entre backend e frontend.
4. O seu arquivo em `agents/` — escopo, pastas que você pode tocar e critério de pronto.

A portaria está em `docs/portaria-325-2026.pdf`. Em caso de dúvida, o texto da portaria vence qualquer documento daqui; registre a divergência em `docs/lacunas.md`.

## Stack

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (síncrono), Alembic, pytest.
- Banco: PostgreSQL 16.
- Frontend: React 18, Vite, TypeScript, TanStack Query, React Router.
- Execução: Docker Compose. `docker compose up` deve subir banco, API (porta 8000) e web (porta 5173) com dados de demonstração.

## Estrutura

```
backend/
  app/
    core/        # config, db, segurança, dependências (fundação)
    models/      # todos os modelos SQLAlchemy (fundação; ninguém mais altera)
    modules/
      auth/ empresas/ auditoria/          # fundação
      veiculos/ pecas/ residuos/ documentos/   # backend-fluxo
      mmv/ urv/ relatorios/ portabilidade/     # backend-urv
  alembic/
  tests/
    unit/          # de cada agente, ao lado do seu módulo
    conformidade/  # qa-conformidade
  scripts/         # seed e demonstrações
web/               # frontend
docs/
agents/
```

## Regras para todos os agentes

- Toque apenas nas pastas do seu arquivo em `agents/`. Se precisar de mudança fora delas (um campo no modelo, um endpoint novo), não faça: registre o pedido em `docs/pedidos-de-mudanca.md` e siga com um contorno.
- Não altere o contrato da API por conta própria. Divergência entre contrato e necessidade vai para `docs/pedidos-de-mudanca.md`.
- Toda escrita relevante de negócio chama `auditoria.registrar_evento(...)` na mesma transação.
- Valores de URV, preços e pesos usam `Decimal`, nunca `float`. Arredondamento sempre `ROUND_HALF_UP`.
- Integrações externas (Renavam, nota fiscal, SINIR, assinatura digital) ficam atrás de uma interface em `app/core/integracoes.py` com implementação falsa. Não chame serviço externo.
- Cada regra de negócio implementada cita o requisito em comentário curto, por exemplo `# RF-19, art. 8º §1º`.
- Lacuna encontrada e não resolvida vai para `docs/lacunas.md` com uma linha: o que falta, por quê, e o artigo.
- Commits pequenos, mensagem no formato `tipo(modulo): descrição [RF-xx]`.

## Convenções de nome

- Termos do domínio em português, sem acento, como estão na portaria: `veiculo`, `peca`, `laudo`, `certificado`, `urv`, `mmv`, `dmr`.
- Termos técnicos em inglês: `service`, `router`, `schema`, `repository`.
- Rotas em português, plural, kebab-case. JSON em snake_case.

## Papéis de usuário

`ADMIN`, `DESMONTADORA`, `RECICLADORA`, `FABRICANTE` (inclui importador), `AUDITOR` (somente leitura, representa o MDIC).
