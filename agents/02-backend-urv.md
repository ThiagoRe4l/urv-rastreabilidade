# Agente 02 — Backend do livro de URV

Roda em paralelo com os agentes 01, 03 e 04, depois da fundação.

## Objetivo

Implementar o cadastro de MMV, o livro de créditos e débitos de URV, os relatórios ao MDIC e a portabilidade.

## Pastas suas

`backend/app/modules/{mmv,urv,relatorios,portabilidade}` e `backend/tests/unit/urv`.

Não altere `models/`, `core/` nem os módulos de outros agentes.

## Entregas

Todas as rotas da seção "URV e MMV" de `docs/03-contrato-api.md`, com as regras de `docs/02-arquitetura.md`. Atenção especial a:

1. **`gerar_credito(session, certificado)`.** Cria o `urv_credito` com quantidade igual ao fator do certificado e o lançamento `CREDITO`. Rejeita certificado que já tem crédito.
2. **Transferência (RF-17).** Direta, única, só para fabricante com vínculo ativo. Trave a linha do crédito (`SELECT ... FOR UPDATE`) para que duas transferências simultâneas não passem.
3. **Cálculo do débito (RF-18).** Função pura `calcular_debito(qv, rm, pm, pb) -> Decimal`, com `Decimal` e `ROUND_HALF_UP`. Casos obrigatórios nos testes:
   - 1000 veículos, RM 10, Pm 180000, Pb 150000 → 120.00
   - 1000 veículos, RM 5, Pm 180000 → 240.00
   - 1000 veículos, RM 10, Pm 90000 → 100.00 (o multiplicador não fica abaixo de 1)
   - 7 veículos, RM 10, Pm 150000 → 0.70
4. **Saldo (RF-19).** O saldo é a soma dos lançamentos, calculada com a linha da empresa travada. Antes de 31/12/2027 aceita saldo negativo e grava `regularizar_ate`; depois, rejeita. A data limite vem de `config_parametro`.
5. **Prazo (RF-20).** Função pura `decimo_dia_util(periodo)`.
6. **Efeitos do MMV (RF-04).** Função pura, com os dois casos.
7. **Unicidade (RF-21).** Chassi de veículo novo consumido uma única vez.
8. **Relatório (RF-24).** Contagens e volumes por ano.
9. **Portabilidade (RF-25).** Exportação com `versao_formato`, empresa, veículos, certificados, créditos e lançamentos. Importação valida e rejeita chassi já creditado, devolvendo o motivo por item.
10. **Fatores do Anexo I.** Teste que recalcula os seis fatores por `0.4*A + 0.3*C + 0.2*R + 0.1*D` com os valores normalizados do Anexo I e compara com `config_fator`. Dois deles dependem de `ROUND_HALF_UP` (0.935 e 0.785).

## Pronto quando

- Todos os casos acima têm teste unitário.
- Teste de concorrência: duas transferências do mesmo crédito em paralelo, só uma passa.
- Teste: consumo sem saldo é aceito com data de 2027 e rejeitado com data de 2028.
