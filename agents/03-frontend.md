# Agente 03 — Frontend

Roda em paralelo com os agentes 01, 02 e 04, depois da fundação.

## Objetivo

Uma aplicação React com uma área por papel, suficiente para executar o roteiro de demonstração sem tocar na API à mão.

## Pasta sua

`web/`. Não altere nada fora dela.

## Como trabalhar sem o backend pronto

Os backends estão sendo construídos ao mesmo tempo. Trabalhe a partir de `docs/03-contrato-api.md`:

1. Escreva os tipos em `web/src/api/types.ts` a partir do contrato.
2. Use MSW para simular as rotas ainda não implementadas, ligado por variável de ambiente `VITE_MOCK=1`.
3. Na integração, os tipos passam a ser gerados de `/openapi.json` e o mock é desligado.

## Telas

| Papel | Telas |
| --- | --- |
| Todos | Login; cabeçalho com empresa e papel |
| DESMONTADORA, RECICLADORA | Lista de veículos com estado; novo veículo; página do veículo com as etapas em sequência, anexos, peças (com etiqueta em QR Code para imprimir), pesagens com percentual aproveitado e meta, DMRs, laudo, e o painel "o que falta para o certificado"; créditos de URV com ação de transferir |
| FABRICANTE | Saldo e extrato de URV; MMVs e novo MMV; novo consumo com simulação do débito e memória de cálculo antes de confirmar; lista de consumos com prazo e regularização pendente |
| AUDITOR | Painel com os números do relatório; busca por chassi que mostra a linha do tempo completa do veículo, do recebimento ao consumo; eventos de auditoria; botão "verificar integridade" com o resultado |
| ADMIN | Empresas, credenciamento e vínculos |
| Público | Página da etiqueta: `/rastreio/:codigo` |

## Diretrizes

- A página do veículo é a tela mais importante: deve deixar óbvio em que etapa está, o que já tem evidência e o que falta.
- Mostre o artigo da portaria ao lado das regras que barram o usuário (por exemplo, "Saldo insuficiente — art. 8º, III").
- Erros da API com `pendencias` viram lista legível, não um alerta genérico.
- Sem biblioteca de componentes pesada. CSS simples e consistente; português em toda a interface.

## Pronto quando

- O roteiro de demonstração de `docs/04-plano-de-execucao.md` é executável pela interface com o mock ligado.
- `npm run build` e `npm run lint` passam.
