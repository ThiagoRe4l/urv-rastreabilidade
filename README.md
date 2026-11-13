# URV Rastreabilidade

Plataforma de rastreabilidade da desmontagem e reciclagem de veículos em fim de vida, com livro de créditos e débitos de URV (Unidade de Reciclagem Veicular), conforme a Portaria GM/MDIC nº 325/2026 (Programa Mover).

**É um MVP de avaliação.** Roda localmente, cobre um fluxo de ponta a ponta e deixa lacunas documentadas em [`docs/lacunas.md`](docs/lacunas.md). Não é um produto pronto para credenciamento.

## Como subir

Requisito: Docker com Compose.

```bash
docker compose up --build
```

| Serviço | Endereço |
| --- | --- |
| Web (React) | http://localhost:5173 |
| API e documentação interativa | http://localhost:8000/docs |
| OpenAPI | http://localhost:8000/openapi.json |
| PostgreSQL 16 | `localhost:5432`, usuário, senha e banco `urv` |

Na subida, a API aplica as migrações (`alembic upgrade head`) e roda o seed, que é idempotente. Para começar do zero: `docker compose down -v`.

Se a porta 5432 estiver ocupada, use `URV_DB_PORTA=5433 docker compose up`.

## Usuários de demonstração

Senha de todos: `demo1234`.

| E-mail | Papel | Empresa |
| --- | --- | --- |
| `admin@urv.local` | ADMIN | |
| `auditor@mdic.local` | AUDITOR (MDIC, somente leitura) | |
| `operador@desmonte.local` | DESMONTADORA | Desmonte Paraná S.A. (credenciada por 2 anos) |
| `fiscal@montadora.local` | FABRICANTE | Montadora Exemplo S.A. (com registro de compromissos) |

O seed também cria o vínculo entre as duas empresas, os seis fatores de equivalência do art. 3º §2º e os parâmetros `PRECO_BASE = 150000.00` e `FIM_SALDO_NEGATIVO = 2027-12-31`, todos vigentes desde 09/11/2026.

Não há rota para criar usuários: eles vêm do seed (lacuna L-02).

## Trilha de auditoria e demonstração de adulteração

Cada escrita de negócio grava um evento encadeado por hash SHA-256 na mesma transação. O banco rejeita `UPDATE`, `DELETE` e `TRUNCATE` em `evento_auditoria` e `urv_lancamento`.

```bash
docker compose exec api python -m scripts.adulterar              # adultera o último evento e mostra a quebra
docker compose exec api python -m scripts.adulterar --sequencia 5
docker compose exec api python -m scripts.adulterar --restaurar  # desfaz
```

Depois de adulterar, `GET /api/v1/auditoria/verificar` (AUDITOR ou ADMIN) devolve `{"integra": false, "primeira_quebra": N}`.

## Testes

Os testes usam PostgreSQL de verdade, porque gatilhos, JSONB e bloqueios consultivos não existem no SQLite.

Dentro do container:

```bash
docker compose exec api pytest
```

Na máquina, com Python 3.12 e o banco do compose no ar:

```bash
docker compose up -d db
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash); Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
```

Frontend: `cd web && npm install && npm run lint && npm run build`.

## Estrutura

```
backend/
  app/
    core/        config, db, segurança, dependências, erros, paginação, integrações, configuração
    models/      todos os modelos SQLAlchemy (só a fundação altera)
    modules/
      auth/ empresas/ auditoria/                    fundação
      veiculos/ pecas/ residuos/ documentos/        backend-fluxo (agente 01)
      mmv/ urv/ relatorios/ portabilidade/          backend-urv (agente 02)
  alembic/       migração única 0001_inicial
  scripts/       seed.py, adulterar.py
  tests/         conftest.py e banco.py compartilhados; unit/<agente>/; conformidade/
web/             Vite + React 18 + TypeScript + TanStack Query + React Router
docs/            requisitos, arquitetura, contrato, plano, lacunas, pedidos de mudança
agents/          instruções de cada agente
```

## Guia rápido para os agentes

- **Rotas.** Cada módulo já tem `router.py` com um `APIRouter` registrado em `app/main.py` sob `/api/v1`. Declare as rotas com o caminho completo do contrato (`@router.post("/veiculos")`). Não edite `main.py`.
- **Transação.** Os services não fazem commit; a rota chama `session.commit()` depois de todas as escritas. `registrar_evento` entra na mesma transação.
- **Auditoria.** Use `from app.modules.auditoria.service import registrar_evento` e chame `registrar_evento(session, usuario, "VEICULO_RECEBIDO", "veiculo", veiculo.id, {...})`. Quando quem age é ADMIN, passe `empresa_id=` com a empresa afetada.
- **Acesso.**
  - `Depends(usuario_atual)` autentica.
  - `Depends(exige_papel(Papel.X, ...))` restringe por papel.
  - `filtrar_por_empresa(stmt, Modelo.empresa_id, usuario)` aplica o escopo da empresa.
  - `garantir_acesso_empresa(usuario, empresa_id)` devolve 404 para registro de outra empresa.
  - AUDITOR já é barrado em toda escrita.
- **Erros.** Levante `ErroNegocio(status, "CODIGO_ESTAVEL", "mensagem", pendencias=[...])`, de `app.core.erros`.
- **Paginação.** Use `pag: Paginacao = Depends(paginacao)`, depois `paginar(session, stmt, pag)` e devolva `Pagina[Schema]`.
- **Decimal.** Arredonde com `app.core.decimais.quantizar` (`ROUND_HALF_UP`). No JSON, o valor sai como string.
- **Configuração.** Use `fator_vigente`, `preco_base_vigente` e `fim_saldo_negativo` de `app.core.configuracao`, sempre com a data da operação.
- **Empresas.** `credenciamento_vigente(empresa, data)` e `vinculo_ativo(session, geradora_id, fabricante_id)` ficam em `app.modules.empresas.service`.
- **Integrações.** Receba por dependência (`Depends(obter_emissor_mtr)` etc., de `app.core.integracoes`), para os testes poderem trocar a implementação.
- **Testes.** Fixtures `client`, `db_session`, `dados_demo` e `auth(email)` em `tests/conftest.py`. Cada teste roda numa transação desfeita no fim. Para testar concorrência com commits reais, crie um banco próprio com `tests.banco.recriar_banco(url_banco_teste("_meu_sufixo"))`, como em `tests/unit/fundacao/test_auditoria.py`.
- **Worktrees.** Use o banco do compose da pasta principal (`docker compose up -d db`). O nome do banco de teste leva um sufixo por pasta, então worktrees diferentes não apagam o banco uma da outra.

## Limitações conhecidas da fundação

- O bloqueio consultivo que serializa a cadeia de hashes também serializa todas as escritas de negócio. Isso basta para o MVP, mas é um gargalo em produção.
- Integrações (Renavam, nota fiscal, MTR/SINIR, assinatura) são falsas e determinísticas; ver `app/core/integracoes.py`.
- Demais lacunas: [`docs/lacunas.md`](docs/lacunas.md).
