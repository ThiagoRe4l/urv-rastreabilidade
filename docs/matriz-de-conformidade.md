# Matriz de conformidade

Uma linha por requisito de `01-requisitos.md`, com o arquivo de teste que o cobre e a situação. Os testes ficam em `backend/tests/conformidade` e foram escritos a partir dos requisitos, do contrato e da portaria, sem ler a implementação dos módulos de fluxo e de URV.

## Situação desta rodada

Rodada de integração na `main` (2026-11-14), com fundação, fluxo, URV e frontend juntos e todas as rotas do contrato no ar:

```
pytest tests/conformidade
404 passed, 0 xfailed, 0 failed

pytest   (suíte inteira: unitários e conformidade)
741 passed
```

Rodada anterior, na branch `feat/qa`, só com a fundação: 87 passed, 317 xfailed. Logo depois dos merges, antes de qualquer ajuste: 4 testes de conformidade falhavam. Os quatro eram do caso a, e há outros seis apertados aos códigos que o contrato passou a fixar; estão em "Testes alterados na integração", abaixo.

| Situação | Significado |
| --- | --- |
| passa | Todos os testes do requisito passam. |
| parcial | Parte passa; o resto está pendente porque depende de rota que ainda não existe. |
| pendente | Todos os testes estão em `xfail`, com o motivo `rota ainda não existe: MÉTODO /caminho`. |
| falha | Há teste falhando com a rota no ar. Nenhum nesta rodada. |
| fora do escopo | Requisito marcado "Não" ou sem resposta de software no MVP. Sem teste. |

**Como o `xfail` funciona.** O cliente de teste (`apoio.Api`) confere cada chamada contra o OpenAPI da aplicação. Se a rota não existe, o teste vira `xfail` com o motivo. Quando a rota passa a existir, o `xfail` some sozinho e o teste passa a valer. Na integração não há marcação a remover: basta rodar `pytest tests/conformidade` de novo e atualizar a coluna "Situação" abaixo.

## Requisitos funcionais

| ID | Requisito (resumo) | Testes | Passam | Pendentes | Situação |
| --- | --- | --- | --- | --- | --- |
| RF-01 | Empresas por papel, credenciamento com situação e validade | `test_rf01_02_empresas_vinculos.py::test_rf01_*` | 15 | 0 | passa |
| RF-02 | Vínculo entre geradora e fabricante | `test_rf01_02_empresas_vinculos.py::test_rf02_*` | 8 | 0 | passa |
| RF-03 | Cadastro de MMV | `test_rf03_04_mmv.py::test_rf03_*` | 17 | 0 | passa |
| RF-04 | Início dos efeitos do MMV | `test_rf03_04_mmv.py::test_rf04_*` | 4 | 0 | passa |
| RF-05 | Retirada de MMV | — | — | — | fora do escopo |
| RF-06 | Recepção do veículo | `test_rf06_08_recepcao_classificacao_etapas.py::test_rf06_*` | 19 | 0 | passa |
| RF-07 | Classificação com evidência; sem ela, sucata inservível | `test_rf06_08_recepcao_classificacao_etapas.py::test_rf07_*` | 13 | 0 | passa |
| RF-08 | Etapas com fotos | `test_rf06_08_recepcao_classificacao_etapas.py::test_rf08_*` | 7 | 0 | passa |
| RF-09 | Peças classificadas e etiqueta de rastreio | `test_rf09_10_pecas.py::test_rf09_*` | 9 | 0 | passa |
| RF-10 | Consulta de peças por origem, tipo, condição e destino | `test_rf09_10_pecas.py::test_rf10_*` | 15 | 0 | passa |
| RF-11 | Peso por fração e por veículo (sem rateio de lote) | `test_rf11_13_pesagens_dmr.py::test_rf11_*` | 12 | 0 | passa |
| RF-12 | Percentual aproveitado e meta do ano, como alerta | `test_rf11_13_pesagens_dmr.py::test_rf12_*` | 4 | 0 | passa |
| RF-13 | DMR com destinatário por material | `test_rf11_13_pesagens_dmr.py::test_rf13_*` | 9 | 0 | passa |
| RF-14 | Laudo assinado pelo responsável técnico | `test_rf14_16_laudo_certificado_credito.py::test_rf14_*` | 8 | 0 | passa |
| RF-15 | Certificado só com etapas e evidências completas | `test_rf14_16_laudo_certificado_credito.py::test_rf15_*`; `test_rnf07_antifraude.py::test_rnf07_certificado_sem_evidencia` | 9 (+13) | 0 | passa |
| RF-16 | Crédito no valor do fator | `test_rf14_16_laudo_certificado_credito.py::test_rf16_*` | 10 | 0 | passa |
| RF-17 | Transferência direta e única, a fabricante com vínculo | `test_rf17_transferencia.py` | 10 | 0 | passa |
| RF-18 | Consumo por chassi e cálculo do débito | `test_rf18_20_consumo.py::test_rf18_*` | 24 | 0 | passa |
| RF-19 | Saldo negativo: bloqueio e exceção até 31/12/2027 | `test_rf18_20_consumo.py::test_rf19_*` | 7 | 0 | passa |
| RF-20 | Prazo de reporte no décimo dia útil | `test_rf18_20_consumo.py::test_rf20_*` | 7 | 0 | passa |
| RF-21 | Unicidade de chassi em fim de vida e de chassi novo | `test_rf21_unicidade.py` | 9 | 0 | passa |
| RF-22 | Trilha de auditoria imutável e verificável | `test_rf22_23_auditoria.py::test_rf22_*` | 13 | 0 | passa |
| RF-23 | Visão de auditoria com leitura de tudo | `test_rf22_23_auditoria.py::test_rf23_*` | 3 | 0 | passa |
| RF-24 | Relatórios ao MDIC (registros, certificados, materiais) | `test_rf24_25_relatorios_portabilidade.py::test_rf24_*` | 6 | 0 | passa. Incidentes (art. 27 III) e plano de atualização (IV): fora do escopo |
| RF-25 | Exportação padronizada | `test_rf24_25_relatorios_portabilidade.py::test_rf25_*` | 3 | 0 | passa |
| RF-26 | Guarda de documentos por cinco anos | — | — | — | fora do escopo |

## Requisitos não funcionais

| ID | Requisito (resumo) | Testes | Passam | Pendentes | Situação |
| --- | --- | --- | --- | --- | --- |
| RNF-01 | Confidencialidade, integridade e imutabilidade | `test_rnf_seguranca_e_contrato.py::test_rnf01_*`; `test_rf22_23_auditoria.py`; `test_rnf07_antifraude.py::test_rnf07_desmontadora_nao_le_dados_de_outra_empresa` | 4 | 0 | passa |
| RNF-02 | Segurança e LGPD | `test_rnf_seguranca_e_contrato.py::test_rnf02_*` | 5 | 0 | passa, no que é testável: senha não exposta, dados pessoais mínimos. A política documentada não é testada |
| RNF-03 | APIs seguras e padrões abertos | `test_rnf_seguranca_e_contrato.py::test_rnf03_*` | 87 | 0 | passa |
| RNF-04 | Interoperabilidade; rejeição de chassi já creditado | `test_rf24_25_relatorios_portabilidade.py::test_rnf04_*` | 4 | 0 | passa |
| RNF-05 | Sem aprisionamento: histórico exportável pela empresa | `test_rf24_25_relatorios_portabilidade.py::test_rnf05_*` | 2 | 0 | passa |
| RNF-06 | Acesso do MDIC: AUDITOR, somente leitura | `test_rnf_seguranca_e_contrato.py::test_rnf06_*`; `test_rnf07_antifraude.py::test_rnf07_auditor_tentando_escrever` | 31 (+1) | 0 | passa |
| RNF-07 | Antifraude | `test_rnf07_antifraude.py` | 29 | 0 | passa |
| RNF-08 | SAST e DAST por terceiro | — | — | — | fora do escopo |
| RNF-09 | Disponibilidade de 99,5% | — | — | — | fora do escopo |
| RNF-10 | Incidente comunicado em 24 horas | — | — | — | fora do escopo |
| RNF-11 | Dados pertencem ao MDIC | — | — | — | fora do escopo: é regra de uso, não verificável por teste |
| RNF-12 | Requisitos societários | — | — | — | fora do escopo: não é requisito de software |

## Casos negativos de antifraude (RNF-07)

| # | Caso | Teste em `test_rnf07_antifraude.py` | Situação |
| --- | --- | --- | --- |
| 1 | Certificado sem cada uma das evidências (13 variações) | `test_rnf07_certificado_sem_evidencia`, mais três casos de borda | passa |
| 2 | Mesmo chassi em fim de vida em dois certificados | `test_rnf07_mesmo_chassi_em_fim_de_vida_em_dois_certificados` | passa (409 `CERTIFICADO_JA_EMITIDO`) |
| 3 | Mesmo chassi novo em dois consumos | `test_rnf07_mesmo_chassi_novo_em_dois_consumos` | passa |
| 4 | Crédito transferido duas vezes | `test_rnf07_credito_transferido_duas_vezes` | passa |
| 5 | Transferência para fabricante sem vínculo | `test_rnf07_transferencia_para_fabricante_sem_vinculo` | passa |
| 6 | Desmontadora lendo dados de outra empresa | `test_rnf07_desmontadora_nao_le_dados_de_outra_empresa`, mais dois casos | passa |
| 7 | Auditor tentando escrever | `test_rnf07_auditor_tentando_escrever`; `test_rnf06_auditor_e_somente_leitura` (uma por rota de escrita) | passa em todas as rotas de escrita do contrato |
| 8 | Evento de auditoria alterado direto no banco | `test_rnf07_evento_de_auditoria_alterado_direto_no_banco_e_barrado`, `..._com_o_gatilho_desligado_e_acusado`, `..._do_fluxo_adulterado_e_acusado` | passa (5), inclusive o evento do fluxo |

As 13 evidências do caso 1: documento de entrada, certidão de baixa, foto da recepção, etapa de recepção, etapa de descontaminação, foto da descontaminação, etapa de desmontagem, foto da desmontagem, peça não reutilizável descaracterizada, etapa de destruição, pesagem, foto da destruição e laudo.

## Ponta a ponta

`test_e2e_roteiro_demonstracao.py::test_e2e_roteiro_de_demonstracao` executa os nove passos do roteiro de `04-plano-de-execucao.md` em um único teste. Situação: passa. O mesmo roteiro também foi executado por HTTP contra a API real do `docker compose`, do cadastro do MMV à verificação da cadeia, com `scripts/adulterar.py` e `--restaurar` no fim.

## Defeitos encontrados

Nenhum teste mostrou o código descumprindo a portaria ou um requisito (caso b): nenhuma correção de código saiu desta matriz. As mudanças de código da integração vieram dos pedidos de mudança (`pedidos-de-mudanca.md`).

## Testes alterados na integração

Nenhuma asserção foi enfraquecida. Onde um teste passou a aceitar um status a mais, ganhou uma asserção mais forte sobre o que importa.

### Caso a: o teste supôs o que o contrato não fixava

| Teste | O que falhava | O que mudou |
| --- | --- | --- |
| `test_rf01_02_empresas_vinculos.py::test_rf01_credenciamento_vencido_nao_emite_certificado` | Simulava o vencimento gravando credenciamento ATIVO com validade já passada; a API recusa (422 `VALIDADE_VENCIDA`, art. 16), e o contrato nunca disse que isso era possível. | O teste exige a recusa e prepara o vencimento pelo banco (`vencer_credenciamento`), como já fazia com as datas de saldo negativo e de efeitos do MMV. A asserção do certificado bloqueado ficou igual. |
| `test_rf22_23_auditoria.py::test_rf23_auditor_le_todos_os_registros_do_fluxo` | Lia o download do anexo como JSON; o contrato diz "Arquivo" e a API devolve o PDF. | Exige 200 e confere o `sha256` do conteúdo baixado contra o gravado. É mais forte que o original, que só exigia 200. |
| `test_rf24_25_relatorios_portabilidade.py::test_rnf04_importacao_rejeita_chassi_ja_creditado` (e o auxiliar `_importar`) | Mandava o arquivo como multipart e só caía para corpo JSON se o 422 viesse sem `codigo`. | O contrato fixou o corpo `application/json` (PM-URV-03 b); `_importar` manda só assim. As asserções do resultado ficaram iguais. |
| `test_rnf07_antifraude.py::test_rnf07_desmontadora_nao_le_dados_de_outra_empresa` | `GET /urv/extrato?empresa_id=<outra>` responde 404 `NAO_ENCONTRADO` ("não revela que existe"), e o teste só aceitava 200 ou 403. | O contrato registra o 404 (PM-URV-03 a), e o teste passa a aceitá-lo, como já aceitava nas rotas de detalhe. Ganhou uma asserção: nem o chassi nem o número do certificado aparecem no corpo de nenhuma das cinco respostas. |

### Apertados aos códigos que o contrato passou a fixar

Passavam aceitando "409 ou 422". Os pedidos aceitos fixaram o código, e o teste agora exige exatamente ele.

| Teste | Agora exige |
| --- | --- |
| `test_rnf07_antifraude.py::test_rnf07_mesmo_chassi_em_fim_de_vida_em_dois_certificados` | 409 `CERTIFICADO_JA_EMITIDO` (PM-04) |
| `test_rf21_unicidade.py::test_rf21_um_certificado_e_um_credito_por_chassi` | 409 `CERTIFICADO_JA_EMITIDO` (PM-04) |
| `test_rf21_unicidade.py::test_rf21_chassi_repetido_no_mesmo_consumo` | 422 `CHASSI_REPETIDO_NA_LISTA` (PM-URV-04) |
| `test_rf14_16_laudo_certificado_credito.py::test_rf14_laudo_atesta_etapas_ja_executadas` (2 variações) | 422 `PENDENCIAS_LAUDO` (PM-03 e) |
| `test_rf14_16_laudo_certificado_credito.py::test_rf14_um_laudo_por_veiculo` | 409 `LAUDO_JA_EMITIDO` (PM-03 e) |
| `test_rf17_transferencia.py::test_rf17_fabricante_sem_registro_de_compromissos_nao_recebe` | 422 `FABRICANTE_SEM_REGISTRO_COMPROMISSOS` (PM-URV-04) |

## Leituras do contrato que os testes assumem

Na rodada da `feat/qa`, o contrato não fixava estes pontos e os testes adotaram a leitura abaixo. A última coluna diz como ficou depois da integração.

| Ponto | O que o teste assume | Depois da integração |
| --- | --- | --- |
| Nomes dos campos nas respostas | Os mesmos nomes das colunas de `02-arquitetura.md` (`credenciamento_status`, `tipo_declarado`, `codigo_rastreio`, `urv_debito`, `saldo_apos`, `titular_id`, `hash_conteudo` e os demais). | Confirmado. O contrato ganhou a seção "Formatos de resposta", tirada do `/openapi.json` (PM-WEB-05). |
| Criação | Responde 200 ou 201; os dois são aceitos. | Mantido: a API responde 201. |
| Papel sem permissão | 403. Registro de outra empresa: 403 ou 404. | Mantido. Nas rotas de URV, `?empresa_id=` de outra empresa responde 404 `NAO_ENCONTRADO` (PM-URV-03 a). |
| Segunda emissão de certificado, segundo laudo, fabricante sem registro de compromissos | 409 ou 422, sem `codigo` fixado. | Fixado: 409 `CERTIFICADO_JA_EMITIDO`, 409 `LAUDO_JA_EMITIDO`, 422 `FABRICANTE_SEM_REGISTRO_COMPROMISSOS`. Os testes exigem esses códigos. |
| Etiqueta em `GET /pecas/rastreio/{codigo}` | Campos `nome`, `chassi`, `data`, `cnpj` no corpo ou dentro de `etiqueta`; `destino` no corpo. | Fixado: os campos vêm no corpo, com `destino`; nada além disso. |
| `GET /veiculos/{id}/pesagens` | `{itens, total, percentual_aproveitado}`. | Fixado, com `peso_total_kg`, `meta_ano` e `atende_meta` a mais (PM-03 b). |
| Peça não reutilizável | Sem `codigo_rastreio` e sem `etiqueta`. | Confirmado. |
| DMR | CNPJ do destinatário com dígito verificador inválido é 422. | Confirmado. |
| Chassi | `POST /veiculos` rejeita o mesmo chassi com caixa ou espaços diferentes (409 ou 422). | Confirmado: 409 `CHASSI_DUPLICADO`. |
| Saldo | `regularizar_ate` some quando o saldo volta a ser zero ou positivo. | Confirmado. |
| Consumo | `consumo.id` e `certificado.id` aparecem como `entidade_id` em algum evento da trilha. | Confirmado. |
| Relatório ao MDIC | `registros` é o número de veículos registrados; `materiais` traz `peso_kg` por linha ou os pesos como valores. | Confirmado: `materiais` é lista de linhas com `peso_kg`, mais `peso_total_kg`. |
| Exportação | O arquivo tem uma chave com "versao" no nome e traz chassis, números de certificado e de DMR, laudo, peças e lançamentos. | Confirmado. |
| Importação | Aceita o arquivo como upload no campo `arquivo` ou como corpo JSON; o teste tenta os dois. | Fixado: só corpo `application/json` (PM-URV-03 b). O teste deixou de tentar o upload. |

## Preparação feita fora da API

A regra de que os testes falam só por HTTP tem quatro exceções, todas em `conftest.py`, porque o contrato não oferece outro caminho:

| O quê | Por quê |
| --- | --- |
| Usuário das empresas criadas no teste, gravado direto em `usuario` | Não há rota de usuários (lacuna L-02). |
| Nova vigência de `FIM_SALDO_NEGATIVO` com data já passada | A API não deixa escolher a data da operação; é o único jeito de exercitar o bloqueio de saldo negativo posterior a 31/12/2027 (RF-19). |
| `efeitos_a_partir_de` de um MMV recuado para 01/01/2026 | Para registrar consumo de período passado e conferir a marca de fora do prazo (RF-20). |
| `credenciamento_validade` recuada para dois dias atrás (`vencer_credenciamento`, desde a integração) | A API recusa credenciar com validade já passada, e vencer é a passagem do tempo; é o único jeito de exercitar o credenciamento vencido (RF-01, art. 16). |

Os casos de adulteração (RF-22 e antifraude 8) também vão ao banco, de propósito: é o ataque que se quer demonstrar.
