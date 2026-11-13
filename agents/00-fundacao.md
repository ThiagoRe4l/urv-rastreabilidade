# Agente 00 — Fundação

Roda sozinho, antes de todos. Os outros agentes só começam depois do seu commit na `main`.

## Objetivo

Deixar o projeto em pé: `docker compose up` sobe banco, API e web vazia; login funciona; todos os modelos e a migração inicial existem; a trilha de auditoria está pronta para uso.

## Pastas suas

`backend/app/core`, `backend/app/models`, `backend/app/modules/{auth,empresas,auditoria}`, `backend/alembic`, `backend/scripts`, `docker-compose.yml`, `README.md`, e o esqueleto vazio de `web/` (Vite + React + TypeScript, só a página de login chamando a API).

## Entregas

1. Estrutura de pastas de `CLAUDE.md`, `pyproject.toml`, Dockerfiles e `docker-compose.yml` com volume para uploads.
2. Todos os modelos SQLAlchemy de `docs/02-arquitetura.md`, com enums, e uma única migração Alembic inicial. Inclua os gatilhos que rejeitam `UPDATE` e `DELETE` em `urv_lancamento` e `evento_auditoria`.
3. `auditoria.registrar_evento` e `GET /auditoria/eventos` e `/auditoria/verificar`, como descrito na arquitetura.
4. Autenticação JWT, dependências `usuario_atual` e `exige_papel(...)`, e o filtro por `empresa_id`.
5. Rotas da seção "Fundação" do contrato.
6. `app/core/integracoes.py` com as interfaces e implementações falsas: `ConsultaRenavam`, `ValidadorNotaFiscal`, `EmissorMTR`, `AssinadorDigital`.
7. Stubs com a assinatura final e `NotImplementedError`: `app/modules/urv/service.py::gerar_credito`. Crie também os pacotes vazios dos módulos dos outros agentes com um `router` vazio já registrado na aplicação, para que ninguém precise editar `main.py`.
8. `scripts/seed.py` com os usuários, empresas, vínculo, fatores e parâmetros do contrato.
9. `scripts/adulterar.py`, descrito na arquitetura.
10. Arquivos vazios `docs/lacunas.md` e `docs/pedidos-de-mudanca.md`.

## Pronto quando

- `docker compose up` sobe sem erro e `/docs` abre.
- Login com os quatro usuários de demonstração funciona.
- Teste unitário prova: evento registrado, cadeia íntegra, cadeia quebrada após adulteração, `UPDATE` em `evento_auditoria` rejeitado pelo banco.
- `README.md` explica como subir e quais usuários existem.
