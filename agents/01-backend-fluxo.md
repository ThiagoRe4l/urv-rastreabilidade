# Agente 01 — Backend do fluxo do veículo

Roda em paralelo com os agentes 02, 03 e 04, depois da fundação.

## Objetivo

Implementar o caminho do veículo em fim de vida da recepção ao certificado: etapas III a IX do art. 18 da portaria.

## Pastas suas

`backend/app/modules/{veiculos,pecas,residuos,documentos}` e `backend/tests/unit/fluxo`.

Não altere `models/`, `core/` nem os módulos de outros agentes.

## Entregas

Todas as rotas da seção "Fluxo do veículo" de `docs/03-contrato-api.md`, com as regras de `docs/02-arquitetura.md`. Atenção especial a:

1. **Classificação (RF-07).** Todo tipo diferente de `SUCATA_INSERVIVEL` (inclusive `LICENCIADO_RODAGEM`) sem anexo `EVIDENCIA_CLASSIFICACAO` é gravado como `SUCATA_INSERVIVEL`; ao anexar a evidência, aplica o `tipo_declarado`. Depois do certificado, o tipo não muda.
2. **Etapas flexíveis.** Descontaminação pode ter data anterior à recepção. `sem_viabilidade_desmontagem` dispensa a etapa de desmontagem.
3. **Peças (RF-09, RF-10).** Código de rastreio único; a etiqueta devolve nome, chassi, data e CNPJ da desmontadora. A consulta pública por código não expõe nada além da etiqueta e do destino.
4. **Pesagens e meta (RF-11, RF-12).** Percentual aproveitado e comparação com a meta do ano; abaixo da meta é alerta, não bloqueio.
5. **DMR (RF-13).** Número de MTR vem de `EmissorMTR` (implementação falsa).
6. **Certificado (RF-15).** As oito pré-condições da arquitetura; a resposta 422 lista todas as pendências de uma vez. Na emissão, chame `urv.service.gerar_credito` na mesma transação.
7. **Auditoria.** Cada escrita registra evento.

## Dependência do agente 02

`gerar_credito` é implementado pelo agente 02. Enquanto não chegar, seus testes usam um substituto. Não implemente a lógica de crédito.

## Pronto quando

- Testes unitários cobrem: chassi duplicado, rebaixamento por falta de laudo, cada pendência do certificado, cálculo do percentual aproveitado, isolamento entre empresas (uma desmontadora não lê veículo de outra).
- O fluxo completo de um veículo passa por chamadas HTTP no teste, até o certificado.
