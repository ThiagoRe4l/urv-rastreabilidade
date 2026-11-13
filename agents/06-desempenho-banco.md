# Agente 06 — Desempenho do banco

Roda depois da integração (fase 3), quando as consultas reais já existem. Antes disso não há o que medir.

## Objetivo

Garantir que as consultas da aplicação usam índice onde precisam, sem criar índice que nenhuma consulta usa.

## Pastas suas

Uma nova migração em `backend/alembic/versions` (não edite a `0001_inicial`), `backend/scripts/volume.py` e `docs/desempenho-banco.md`. Correção de consulta dentro de módulo de outro agente é permitida nesta fase, desde que os testes continuem passando.

## Passos

1. **Chaves estrangeiras.** O Postgres não cria índice em chave estrangeira sozinho. Liste toda foreign key sem índice e diga quais são usadas em JOIN ou filtro por alguma consulta real.
2. **Colunas de filtro e ordenação.** Para cada coluna usada em WHERE, JOIN ou ORDER BY nos services e routers, diga se tem índice. Atenção ao filtro por `empresa_id`, presente em quase toda listagem, e à soma de `urv_lancamento` por empresa, que calcula o saldo.
3. **Padrões ruins.** Aponte e corrija:
   - coluna embrulhada em função no WHERE (`date()`, `lower()`, cast);
   - `count` usado só para saber se existe (troque por `EXISTS`);
   - consulta dentro de loop (troque por JOIN, `IN` ou carregamento antecipado do SQLAlchemy);
   - paginação por OFFSET em tabela que cresce sem limite (`evento_auditoria`, `urv_lancamento`): registre como lacuna a troca por cursor, sem mudar o contrato.
4. **Volume.** Escreva `scripts/volume.py`, que popula um banco de desenvolvimento com volume plausível: 50 mil veículos, 500 mil peças, 200 mil pesagens, 50 mil certificados e créditos, 300 mil lançamentos, 1 milhão de eventos de auditoria. Nunca rode esse script no banco de demonstração.
5. **Medição.** Rode `EXPLAIN (ANALYZE, BUFFERS)` nas consultas mais usadas, no banco com volume: lista de veículos por empresa e estado, busca por chassi, consulta de peças com filtros, saldo de URV, extrato, eventos de auditoria por entidade, e a verificação da cadeia. Mostre onde aparece Seq Scan em tabela grande.
6. **Índices.** Proponha os índices em uma migração, cada um com um comentário dizendo qual consulta acelera. Meça de novo e registre antes e depois.

## Regras

- Índice ocupa espaço e deixa a escrita mais lenta. Só crie onde uma consulta real precisa e a medição mostra ganho.
- `evento_auditoria` e `urv_lancamento` recebem muita escrita: seja ainda mais econômico nelas.
- Este projeto não tem produção. Registre em `docs/desempenho-banco.md` que, em produção, índice em tabela grande seria criado com `CREATE INDEX CONCURRENTLY`, fora de transação.

## Pronto quando

- `docs/desempenho-banco.md` tem a tabela de consultas com plano e tempo antes e depois, e a lista de índices com a consulta que cada um atende.
- Todos os testes continuam passando.
