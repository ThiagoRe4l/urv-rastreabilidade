# Arquitetura

## Visão geral

Monólito modular: uma API FastAPI, um PostgreSQL, uma aplicação React. Três decisões sustentam o desenho:

1. **O crédito de URV é um livro-razão só de inserção.** Saldo nunca é um campo editável; é a soma dos lançamentos. Isso atende à integridade exigida pelo art. 20 V e torna a reconciliação do art. 28 possível.
2. **Todo evento de negócio entra em uma cadeia de hashes.** Cada evento guarda o hash do anterior. Alterar um registro quebra a cadeia e a verificação acusa. É a resposta de menor custo à "imutabilidade verificável"; uma blockchain entregaria o mesmo com mais operação.
3. **Integrações externas ficam atrás de interfaces.** Renavam, nota fiscal, SINIR e assinatura digital têm implementação falsa no MVP e ponto de troca definido.

## Módulos e donos

| Módulo | Dono | Responsabilidade |
| --- | --- | --- |
| `core`, `models`, `auth`, `empresas`, `auditoria` | fundação | Infraestrutura, todos os modelos, migração inicial, login, empresas, vínculos, trilha |
| `veiculos`, `pecas`, `residuos`, `documentos` | backend-fluxo | Etapas III a IX do art. 18, laudo e certificado |
| `mmv`, `urv`, `relatorios`, `portabilidade` | backend-urv | MMV, livro de URV, relatórios ao MDIC, exportação e importação |
| `web/` | frontend | Portais por papel |
| `tests/conformidade` | qa-conformidade | Testes por requisito |

Ponto de contato entre fluxo e URV: `app/modules/urv/service.py::gerar_credito(session, certificado, *, usuario=None) -> UrvCredito`. A fundação criou a assinatura; backend-urv implementou; backend-fluxo só chama, sempre com `usuario=` para o evento `CREDITO_GERADO` ter autor (PM-URV-02).

## Modelo de dados

Todas as tabelas têm `id` (UUID) e `criado_em`. Tipos monetários e de URV: `NUMERIC(14,2)`. Pesos: `NUMERIC(12,3)` em kg.

| Tabela | Campos principais | Regras |
| --- | --- | --- |
| `empresa` | `cnpj` único, `razao_social`, `tipo` (FABRICANTE, DESMONTADORA, RECICLADORA), `credenciamento_status` (PENDENTE, ATIVO, SUSPENSO, CANCELADO), `credenciamento_validade` | Fabricante não tem credenciamento; usa `registro_compromissos` (bool) |
| `usuario` | `email` único, `senha_hash`, `nome`, `papel`, `empresa_id` (nulo para ADMIN e AUDITOR) | |
| `vinculo` | `geradora_id`, `fabricante_id`, `ativo` | Par único |
| `mmv` | `fabricante_id`, `codigo`, `ncm`, `nivel` (1 ou 2), `percentual_reciclabilidade`, `ja_comercializado`, `efeitos_a_partir_de`, `status` (ATIVO, RETIRADO) | `(fabricante_id, codigo)` único |
| `veiculo` | `empresa_id`, `chassi` único, `placa`, `renavam`, `data_entrada`, `tipo_declarado`, `tipo` (o efetivo, usado no fator), `origem_aquisicao`, `documento_entrada_tipo` (NF_ENTRADA, AUTO_ARREMATACAO), `documento_entrada_numero`, `certidao_baixa_numero`, `peso_entrada_kg`, `sem_viabilidade_desmontagem`, `estado` | Veículo em fim de vida |
| `etapa` | `veiculo_id`, `tipo` (RECEPCAO, DESCONTAMINACAO, DESMONTAGEM, DESTRUICAO, DESTINACAO), `iniciada_em`, `concluida_em`, `observacoes` | `(veiculo_id, tipo)` único |
| `anexo` | `veiculo_id`, `etapa_tipo`, `tipo` (FOTO, DOCUMENTO_ENTRADA, CERTIDAO_BAIXA, EVIDENCIA_CLASSIFICACAO), `caminho`, `sha256`, `enviado_por` | Arquivo em volume local |
| `peca` | `veiculo_id`, `nome`, `descricao`, `classificacao` (REUTILIZAVEL, NAO_REUTILIZAVEL), `codigo_rastreio` único, `condicao` (USADA, REMANUFATURADA), `destino` (ESTOQUE, REVENDA, EXPORTACAO, REMANUFATURA, RECONDICIONAMENTO, RECICLAGEM, DESCARTE), `descaracterizada` | Reutilizável exige `codigo_rastreio`; não reutilizável exige `descaracterizada` |
| `pesagem` | `veiculo_id`, `fracao` (FERROSO, NAO_FERROSO, NAO_METALICO, FLUIDOS, BATERIAS, PNEUS), `destino` (REAPROVEITAMENTO, RECICLAGEM, RECUPERACAO_ENERGETICA, REJEITO), `peso_kg` | |
| `dmr` | `veiculo_id`, `numero`, `mtr_numero`, `destinatario_nome`, `destinatario_cnpj`, `tipo_material`, `peso_kg`, `emitida_em` | |
| `laudo` | `veiculo_id` único, `responsavel_nome`, `responsavel_registro`, `assinado_em`, `hash_conteudo` | |
| `certificado` | `veiculo_id` único, `numero` único, `empresa_id`, `tipo_veiculo`, `fator`, `percentual_aproveitado`, `meta_ano`, `atende_meta`, `emitido_em`, `hash_conteudo` | |
| `urv_credito` | `certificado_id` único, `geradora_id`, `titular_id`, `quantidade`, `status` (DISPONIVEL, TRANSFERIDO) | Indivisível |
| `urv_lancamento` | `empresa_id`, `tipo` (CREDITO, TRANSFERENCIA_SAIDA, TRANSFERENCIA_ENTRADA, DEBITO), `quantidade` (com sinal), `credito_id`, `consumo_id`, `contraparte_id` | Só inserção. `(credito_id, tipo)` único: um crédito tem no máximo um lançamento de cada tipo (DEBITO tem `credito_id` nulo) |
| `consumo` | `fabricante_id`, `mmv_id`, `periodo` (AAAA-MM), `qv`, `rm`, `pm`, `pb`, `urv_debito`, `saldo_apos`, `regularizar_ate`, `prazo_reporte`, `registrado_em` | Só inserção |
| `consumo_chassi` | `consumo_id`, `chassi` único | Chassi de veículo novo. Só inserção |
| `config_fator` | `tipo_veiculo`, `fator`, `vigente_desde` | Semeada com a tabela do art. 3º §2º |
| `config_parametro` | `chave` (PRECO_BASE, FIM_SALDO_NEGATIVO, RM_NIVEL_1, RM_NIVEL_2), `valor`, `vigente_desde` | Semeada com 150000.00, 2027-12-31, 10 e 5. O RM por nível é parâmetro porque a correspondência com os itens 17 e 18 do Anexo III do Decreto 12.435/2025 não foi conferida (L-01) |
| `evento_auditoria` | `sequencia` (bigserial), `ocorrido_em`, `usuario_id`, `empresa_id`, `tipo`, `entidade`, `entidade_id`, `payload` (JSONB), `hash_anterior`, `hash` | Só inserção |

`urv_lancamento`, `evento_auditoria`, `consumo` e `consumo_chassi` têm gatilho no banco que rejeita `UPDATE`, `DELETE` e `TRUNCATE`. Os dois primeiros vêm da migração `0001`; `consumo`, `consumo_chassi` e o índice único `uq_urv_lancamento_credito_id_tipo` vêm da `0002` (PM-URV-05). É defesa em profundidade: a transferência única e o consumo único continuam garantidos primeiro pelo service, com `SELECT ... FOR UPDATE`, e o banco barra o que escapar.

### Data das operações

Toda data de regra de negócio é a data civil de Brasília (UTC-3 fixo), dada por `app/core/relogio.py`: validade do credenciamento, meta do ano, vigência de fatores e parâmetros, início de efeitos do MMV, prazo de reporte, prazo de regularização e data da etiqueta. Nenhuma regra usa `date.today()`, porque o container roda em UTC e, entre 21h e 0h de Brasília, ele já devolveria o dia seguinte. As rotas recebem o momento por `Depends(agora)`, que os testes trocam para simular datas (PM-URV-06).

## Regras de negócio

### Tipos de veículo e fatores (art. 3º §2º)

| `tipo` | Fator |
| --- | --- |
| `LICENCIADO_RODAGEM` | 1.00 |
| `SINISTRADO_PEQUENA_MEDIA` | 0.94 |
| `SUCATA_APROVEITAVEL` | 0.85 |
| `SINISTRADO_GRANDE` | 0.79 |
| `SUCATA_MOTOR_INSERVIVEL` | 0.68 |
| `SUCATA_INSERVIVEL` | 0.38 |

Todo tipo diferente de `SUCATA_INSERVIVEL`, inclusive `LICENCIADO_RODAGEM`, exige anexo `EVIDENCIA_CLASSIFICACAO` (art. 6º I c). Sem ele, o veículo é gravado como `SUCATA_INSERVIVEL`, com `tipo_declarado` preservado; ao anexar a evidência, o `tipo_declarado` é aplicado. É o art. 2º §5º estendido ao veículo licenciado (premissa em `01-requisitos.md`). Os fatores ficam em uma tabela de configuração com vigência, porque podem ser revistos (art. 3º §6º).

### Estados do veículo

`RECEBIDO → EM_PROCESSO → LAUDO_EMITIDO → CERTIFICADO → ENCERRADO`

As etapas são registros independentes, não uma fila rígida, porque a portaria admite duas variações: a descontaminação pode ser anterior à recepção (art. 18 IV), e veículo sem viabilidade de desmontagem vai direto à trituração (Anexo III, item 11).

### Pré-condições do certificado (RF-15)

1. Empresa com credenciamento `ATIVO` e dentro da validade.
2. Etapa RECEPCAO concluída, com documento de entrada, certidão de baixa e ao menos uma foto.
3. Etapa DESCONTAMINACAO concluída, com ao menos uma foto.
4. Etapa DESMONTAGEM concluída com ao menos uma foto, ou `sem_viabilidade_desmontagem` verdadeiro.
5. Toda peça reutilizável com código de rastreio; toda não reutilizável descaracterizada.
6. Etapa DESTRUICAO concluída, com ao menos uma pesagem e ao menos uma foto (é a separação dos materiais; art. 6º III c, Anexo III 15.c).
7. Laudo assinado.
8. Chassi sem certificado anterior (RF-21).

A falha das pré-condições 1 a 7 devolve 422 `PENDENCIAS_CERTIFICADO` com a lista do que falta. A pré-condição 8 não entra na lista: é conflito com um registro que já existe e devolve 409 `CERTIFICADO_JA_EMITIDO`, como `CHASSI_DUPLICADO` e `CHASSI_JA_CONSUMIDO` (PM-04). A emissão calcula o percentual aproveitado, grava se atende a meta do ano e chama `gerar_credito`. O veículo passa a `ENCERRADO` quando a etapa DESTINACAO é concluída com ao menos uma DMR.

### Meta de aproveitamento (RF-12)

`percentual = soma(peso onde destino != REJEITO) / peso_entrada_kg` (art. 18 §5º: "sobre o peso total do veículo"). O peso de entrada sem pesagem conta como não aproveitado; a soma das pesagens não passa do peso de entrada (422 `PESO_ACIMA_DA_ENTRADA`). Metas: 80% (2027–2028), 85% (2029–2030), 90% (2031–2032), 95% (2033 em diante). Em 2026 não há meta: só registro (art. 18 §7º).

### Crédito e transferência (RF-16, RF-17)

- Emissão do certificado cria um `urv_credito` de quantidade igual ao fator e um lançamento `CREDITO` para a geradora.
- Transferência exige: crédito `DISPONIVEL`, solicitante igual à geradora e titular, vínculo ativo com o fabricante, fabricante com `registro_compromissos`. Gera dois lançamentos e muda o status para `TRANSFERIDO`. Um crédito transferido não pode ser transferido de novo.

### Consumo (RF-18, RF-19, RF-20)

```
debito_periodo(qv) = (qv / rm) * max(1, pm / pb)       # quantizado em 0.01, ROUND_HALF_UP
urv_debito = debito_periodo(qv_periodo) - ja_debitado  # qv_periodo inclui este consumo
```

- `qv_periodo` = soma dos chassis do fabricante no MMV e no período, contando este consumo; `ja_debitado` = soma dos `urv_debito` anteriores do mesmo MMV e período (art. 3º §3º; achado A3 da revisão). `consumo.qv` continua sendo o número de chassis do próprio consumo. O cálculo trava a linha do fabricante antes de ler os consumos anteriores. Pm diferente do primeiro consumo do período é 422 `PM_DIVERGENTE_NO_PERIODO` (art. 3º §4º); RM e Pb são os do primeiro consumo do período. `rm` = parâmetro `RM_NIVEL_1` ou `RM_NIVEL_2` vigente na data (5 ou 10, art. 3º §3º; L-01). `pb` = 150000.00 (configuração com vigência). `pm` é informado pelo fabricante no MVP.
- Rejeita se o MMV não está `ATIVO`, se a data é anterior a `efeitos_a_partir_de`, ou se algum chassi já foi consumido.
- Saldo: se `saldo < urv_debito` e a data é posterior a 31/12/2027, rejeita com 409. Até 31/12/2027, aceita e grava `regularizar_ate` = último dia do terceiro mês seguinte ao do registro.
- `prazo_reporte` = décimo dia útil do mês seguinte ao `periodo`. Registro posterior é aceito e marcado como fora do prazo.

### MMV (RF-04)

`efeitos_a_partir_de` = 1º de janeiro do ano seguinte ao cadastro se `ja_comercializado`; senão, a data do cadastro.

## Trilha de auditoria (RF-22)

`auditoria.registrar_evento(session, usuario, tipo, entidade, entidade_id, payload)`:

1. Obtém `pg_advisory_xact_lock` para serializar a cadeia.
2. Lê o `hash` do último evento (ou 64 zeros).
3. Calcula `hash = sha256(hash_anterior + json_canonico(ocorrido_em, usuario_id, empresa_id, tipo, entidade, entidade_id, payload))`, com chaves ordenadas e sem espaços. `empresa_id` entra no hash para que trocar a empresa de um evento também quebre a cadeia.
4. Insere na mesma transação da operação de negócio.

`GET /auditoria/verificar` percorre a cadeia e devolve `{integra, total, primeira_quebra}`. O script `scripts/adulterar.py` desliga o gatilho, altera um evento e mostra a verificação acusando a quebra.

## Segurança

- JWT com papel e `empresa_id`. Toda consulta de empresa filtra por `empresa_id` do token; AUDITOR e ADMIN leem tudo; AUDITOR nunca escreve: `usuario_atual` devolve 403 `AUDITOR_SOMENTE_LEITURA` para AUDITOR em qualquer método diferente de GET, HEAD e OPTIONS, em todas as rotas.
- Upload: tipos permitidos (imagem, PDF), limite de 10 MB, nome de arquivo gerado, `sha256` gravado.
- Dados pessoais: nome e e-mail de usuários, nome e registro do responsável técnico. Nada além disso.

## O que fica para a arquitetura-alvo

Alta disponibilidade, armazenamento de objetos com retenção de cinco anos, assinatura ICP-Brasil, integrações reais, comunicação de incidentes, e ancoragem periódica do hash da cadeia em um registro externo (um carimbo de tempo ou uma rede pública) para que nem o operador consiga reescrever a história.
