# Plano de execução

## Fases

| Fase | Agente | Depende de | Modo |
| --- | --- | --- | --- |
| 1 | 00 Fundação | Documentos desta pasta | Sozinho, na `main` |
| 2 | 01 Backend fluxo | Fundação | Paralelo, worktree própria |
| 2 | 02 Backend URV | Fundação | Paralelo, worktree própria |
| 2 | 03 Frontend | Fundação | Paralelo, worktree própria |
| 2 | 04 QA de conformidade | Fundação | Paralelo, worktree própria |
| 3 | Integração | Fase 2 | Sozinho, na `main` |
| 4 | 05 Revisor | Integração | Sessão nova |

A paralelização funciona porque cada agente é dono de pastas diferentes e todos obedecem ao mesmo contrato. Os modelos e a migração são da fundação, então não há conflito de banco.

## Passo a passo

### Preparação

1. Abra um terminal na pasta do projeto.
2. Rode `git init` e depois `git add . && git commit -m "docs: requisitos, arquitetura, contrato e agentes"`.

### Fase 1 — Fundação

3. Rode `claude` na pasta do projeto.
4. Envie: `Leia CLAUDE.md e agents/00-fundacao.md e execute o que o arquivo do agente pede. Ao terminar, rode os testes e faça commit.`
5. Quando terminar, confira: `docker compose up` sobe e `http://localhost:8000/docs` abre. Deixe tudo commitado na `main`.

### Fase 2 — Quatro agentes em paralelo

6. Crie uma worktree por agente:
   ```
   git worktree add ../urv-fluxo -b feat/fluxo
   git worktree add ../urv-livro -b feat/urv
   git worktree add ../urv-web -b feat/web
   git worktree add ../urv-qa -b feat/qa
   ```
7. Abra quatro terminais, um em cada pasta criada, e rode `claude` em cada um.
8. Em cada um, envie a mesma frase trocando o arquivo: `Leia CLAUDE.md e agents/01-backend-fluxo.md e execute. Toque apenas nas pastas que o arquivo lista. Ao terminar, rode os testes e faça commit.`
   - `urv-fluxo` → `agents/01-backend-fluxo.md`
   - `urv-livro` → `agents/02-backend-urv.md`
   - `urv-web` → `agents/03-frontend.md`
   - `urv-qa` → `agents/04-qa-conformidade.md`

### Fase 3 — Integração

9. Volte à pasta principal e faça os merges nesta ordem: `git merge feat/urv`, `git merge feat/fluxo`, `git merge feat/web`, `git merge feat/qa`.
10. Rode `claude` na pasta principal e envie: `Integre: resolva o que está em docs/pedidos-de-mudanca.md, remova os xfail dos testes de conformidade cujas rotas já existem, desligue o mock do frontend e gere os tipos a partir do /openapi.json. Rode tudo e relate o que falhou.`

### Fase 3b — Desempenho do banco

10b. Com tudo integrado e os testes passando, rode `claude` na pasta principal e envie: `Leia CLAUDE.md e agents/06-desempenho-banco.md e execute.`

### Fase 4 — Revisão

11. Abra uma sessão nova do `claude` e envie: `Leia agents/05-revisor.md e execute.`
12. Leia `docs/revisao-independente.md`. O que não for corrigido entra em `docs/lacunas.md`.

## Roteiro de demonstração

1. O administrador mostra a desmontadora credenciada, o fabricante e o vínculo entre eles.
2. O fabricante cadastra um MMV com nível e percentual de reciclabilidade.
3. A desmontadora recebe um veículo, anexa nota fiscal, certidão de baixa e fotos, e classifica o tipo.
4. Ela registra descontaminação, desmontagem com peças etiquetadas, pesos por material e a DMR.
5. O responsável técnico assina o laudo; o certificado é emitido e o crédito entra no saldo.
6. A desmontadora transfere o crédito ao fabricante.
7. O fabricante indica os chassis vendidos; o sistema calcula o débito e baixa o saldo.
8. O auditor busca o chassi, vê a linha do tempo inteira e verifica a cadeia de hashes.
9. Duas tentativas barradas: registrar o mesmo chassi de novo, e adulterar um evento com `scripts/adulterar.py`.
