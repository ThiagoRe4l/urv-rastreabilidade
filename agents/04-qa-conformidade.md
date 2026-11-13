# Agente 04 — QA de conformidade

Roda em paralelo com os agentes 01, 02 e 03, depois da fundação.

## Objetivo

Provar, por teste, que o sistema cumpre a portaria. Você escreve os testes a partir de `docs/01-requisitos.md` e do PDF da portaria, não a partir do código dos outros agentes. A independência é o valor do seu trabalho: não leia a implementação para decidir o que o teste espera.

## Pasta sua

`backend/tests/conformidade` e `docs/matriz-de-conformidade.md`. Não altere código de produção. Defeito encontrado vai para `docs/pedidos-de-mudanca.md` com o teste que o demonstra.

## Entregas

1. Um arquivo de teste por grupo de requisitos, com testes nomeados pelo requisito: `test_rf17_transferencia_direta_e_unica`, `test_rf19_saldo_negativo_ate_2027`.
2. Os testes falam com a API por HTTP (cliente de teste do FastAPI), usando apenas o contrato. Enquanto uma rota não existir, o teste fica marcado com `xfail` e o motivo.
3. Um teste de ponta a ponta que executa o roteiro de demonstração inteiro.
4. Casos negativos de antifraude (RNF-07):
   - certificado sem cada uma das evidências;
   - mesmo chassi em fim de vida em dois certificados;
   - mesmo chassi novo em dois consumos;
   - crédito transferido duas vezes;
   - transferência para fabricante sem vínculo;
   - desmontadora lendo dados de outra empresa;
   - auditor tentando escrever;
   - evento de auditoria alterado direto no banco.
5. `docs/matriz-de-conformidade.md`: uma linha por requisito, com o teste que o cobre e a situação (passa, falha, pendente, fora do escopo).

## Pronto quando

- Todo requisito marcado "Sim" ou "Parcial" em `docs/01-requisitos.md` tem ao menos um teste.
- A matriz está preenchida e bate com a saída do `pytest`.
