# Matriz de conformidade

Uma linha por requisito de `01-requisitos.md`, com o arquivo de teste que o cobre e a situação. Os testes ficam em `backend/tests/conformidade` e foram escritos a partir dos requisitos, do contrato e da portaria, sem ler a implementação dos módulos de fluxo e de URV.

## Situação desta rodada

Rodada na branch `feat/qa`, só com a fundação (as rotas de fluxo e de URV ainda não existem aqui):

```
pytest tests/conformidade
87 passed, 317 xfailed
```

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
| RF-01 | Empresas por papel, credenciamento com situação e validade | `test_rf01_02_empresas_vinculos.py::test_rf01_*` | 11 | 4 | parcial: cadastro e credenciamento passam; o bloqueio do certificado sem credenciamento vigente depende de `POST /veiculos` |
| RF-02 | Vínculo entre geradora e fabricante | `test_rf01_02_empresas_vinculos.py::test_rf02_*` | 8 | 0 | passa |
| RF-03 | Cadastro de MMV | `test_rf03_04_mmv.py::test_rf03_*` | 0 | 17 | pendente (`POST /mmvs`) |
| RF-04 | Início dos efeitos do MMV | `test_rf03_04_mmv.py::test_rf04_*` | 0 | 4 | pendente (`POST /mmvs`) |
| RF-05 | Retirada de MMV | — | — | — | fora do escopo |
| RF-06 | Recepção do veículo | `test_rf06_08_recepcao_classificacao_etapas.py::test_rf06_*` | 0 | 19 | pendente (`POST /veiculos`) |
| RF-07 | Classificação com evidência; sem ela, sucata inservível | `test_rf06_08_recepcao_classificacao_etapas.py::test_rf07_*` | 0 | 13 | pendente (`POST /veiculos`) |
| RF-08 | Etapas com fotos | `test_rf06_08_recepcao_classificacao_etapas.py::test_rf08_*` | 0 | 7 | pendente (`POST /veiculos`) |
| RF-09 | Peças classificadas e etiqueta de rastreio | `test_rf09_10_pecas.py::test_rf09_*` | 0 | 9 | pendente (`POST /veiculos`, `GET /pecas/rastreio/{codigo}`) |
| RF-10 | Consulta de peças por origem, tipo, condição e destino | `test_rf09_10_pecas.py::test_rf10_*` | 0 | 15 | pendente (`POST /veiculos`) |
| RF-11 | Peso por fração e por veículo (sem rateio de lote) | `test_rf11_13_pesagens_dmr.py::test_rf11_*` | 0 | 12 | pendente (`POST /veiculos`) |
| RF-12 | Percentual aproveitado e meta do ano, como alerta | `test_rf11_13_pesagens_dmr.py::test_rf12_*` | 0 | 4 | pendente (`POST /veiculos`) |
| RF-13 | DMR com destinatário por material | `test_rf11_13_pesagens_dmr.py::test_rf13_*` | 0 | 9 | pendente (`POST /veiculos`) |
| RF-14 | Laudo assinado pelo responsável técnico | `test_rf14_16_laudo_certificado_credito.py::test_rf14_*` | 0 | 8 | pendente (`POST /veiculos`) |
| RF-15 | Certificado só com etapas e evidências completas | `test_rf14_16_laudo_certificado_credito.py::test_rf15_*`; `test_rnf07_antifraude.py::test_rnf07_certificado_sem_evidencia` | 0 | 9 (+13) | pendente (`POST /veiculos`) |
| RF-16 | Crédito no valor do fator | `test_rf14_16_laudo_certificado_credito.py::test_rf16_*` | 1 | 9 | parcial: a tabela de fatores e o preço base passam; a geração do crédito depende de `POST /veiculos` |
| RF-17 | Transferência direta e única, a fabricante com vínculo | `test_rf17_transferencia.py` | 0 | 10 | pendente (`POST /veiculos`) |
| RF-18 | Consumo por chassi e cálculo do débito | `test_rf18_20_consumo.py::test_rf18_*` | 0 | 24 | pendente (`POST /mmvs`) |
| RF-19 | Saldo negativo: bloqueio e exceção até 31/12/2027 | `test_rf18_20_consumo.py::test_rf19_*` | 1 | 6 | pendente: o que passa é só a conferência da régua de datas do próprio teste |
| RF-20 | Prazo de reporte no décimo dia útil | `test_rf18_20_consumo.py::test_rf20_*` | 5 | 2 | pendente: o que passa é só a conferência da régua de datas do próprio teste |
| RF-21 | Unicidade de chassi em fim de vida e de chassi novo | `test_rf21_unicidade.py` | 0 | 9 | pendente (`POST /veiculos`, `POST /mmvs`) |
| RF-22 | Trilha de auditoria imutável e verificável | `test_rf22_23_auditoria.py::test_rf22_*` | 12 | 1 | parcial: cadeia, gatilho e verificação passam; os eventos do fluxo dependem de `POST /veiculos` |
| RF-23 | Visão de auditoria com leitura de tudo | `test_rf22_23_auditoria.py::test_rf23_*` | 1 | 2 | parcial: cadastros e trilha passam; os registros do fluxo dependem de `POST /veiculos` |
| RF-24 | Relatórios ao MDIC (registros, certificados, materiais) | `test_rf24_25_relatorios_portabilidade.py::test_rf24_*` | 0 | 6 | pendente (`GET /relatorios/mdic`). Incidentes (art. 27 III) e plano de atualização (IV): fora do escopo |
| RF-25 | Exportação padronizada | `test_rf24_25_relatorios_portabilidade.py::test_rf25_*` | 0 | 3 | pendente (`GET /portabilidade/exportar`) |
| RF-26 | Guarda de documentos por cinco anos | — | — | — | fora do escopo |

## Requisitos não funcionais

| ID | Requisito (resumo) | Testes | Passam | Pendentes | Situação |
| --- | --- | --- | --- | --- | --- |
| RNF-01 | Confidencialidade, integridade e imutabilidade | `test_rnf_seguranca_e_contrato.py::test_rnf01_*`; `test_rf22_23_auditoria.py`; `test_rnf07_antifraude.py::test_rnf07_desmontadora_nao_le_dados_de_outra_empresa` | 1 | 3 | parcial: a trilha passa (RF-22); o livro de URV e o isolamento entre empresas dependem de `POST /veiculos` |
| RNF-02 | Segurança e LGPD | `test_rnf_seguranca_e_contrato.py::test_rnf02_*` | 5 | 0 | passa, no que é testável: senha não exposta, dados pessoais mínimos. A política documentada não é testada |
| RNF-03 | APIs seguras e padrões abertos | `test_rnf_seguranca_e_contrato.py::test_rnf03_*` | 28 | 59 | parcial: OpenAPI, JWT, formato de erro e paginação passam; 30 das 42 rotas do contrato ainda não existem |
| RNF-04 | Interoperabilidade; rejeição de chassi já creditado | `test_rf24_25_relatorios_portabilidade.py::test_rnf04_*` | 0 | 4 | pendente (`POST /portabilidade/importar`) |
| RNF-05 | Sem aprisionamento: histórico exportável pela empresa | `test_rf24_25_relatorios_portabilidade.py::test_rnf05_*` | 0 | 2 | pendente (`GET /portabilidade/exportar`) |
| RNF-06 | Acesso do MDIC: AUDITOR, somente leitura | `test_rnf_seguranca_e_contrato.py::test_rnf06_*`; `test_rnf07_antifraude.py::test_rnf07_auditor_tentando_escrever` | 10 | 21 (+1) | parcial: leitura e bloqueio de escrita passam nas rotas da fundação |
| RNF-07 | Antifraude | `test_rnf07_antifraude.py` | 4 | 25 | parcial: ver a tabela abaixo |
| RNF-08 | SAST e DAST por terceiro | — | — | — | fora do escopo |
| RNF-09 | Disponibilidade de 99,5% | — | — | — | fora do escopo |
| RNF-10 | Incidente comunicado em 24 horas | — | — | — | fora do escopo |
| RNF-11 | Dados pertencem ao MDIC | — | — | — | fora do escopo: é regra de uso, não verificável por teste |
| RNF-12 | Requisitos societários | — | — | — | fora do escopo: não é requisito de software |

## Casos negativos de antifraude (RNF-07)

| # | Caso | Teste em `test_rnf07_antifraude.py` | Situação |
| --- | --- | --- | --- |
| 1 | Certificado sem cada uma das evidências (13 variações) | `test_rnf07_certificado_sem_evidencia`, mais três casos de borda | pendente |
| 2 | Mesmo chassi em fim de vida em dois certificados | `test_rnf07_mesmo_chassi_em_fim_de_vida_em_dois_certificados` | pendente |
| 3 | Mesmo chassi novo em dois consumos | `test_rnf07_mesmo_chassi_novo_em_dois_consumos` | pendente |
| 4 | Crédito transferido duas vezes | `test_rnf07_credito_transferido_duas_vezes` | pendente |
| 5 | Transferência para fabricante sem vínculo | `test_rnf07_transferencia_para_fabricante_sem_vinculo` | pendente |
| 6 | Desmontadora lendo dados de outra empresa | `test_rnf07_desmontadora_nao_le_dados_de_outra_empresa`, mais dois casos | pendente |
| 7 | Auditor tentando escrever | `test_rnf07_auditor_tentando_escrever`; `test_rnf06_auditor_e_somente_leitura` (uma por rota de escrita) | parcial: passa nas 5 rotas de escrita da fundação |
| 8 | Evento de auditoria alterado direto no banco | `test_rnf07_evento_de_auditoria_alterado_direto_no_banco_e_barrado`, `..._com_o_gatilho_desligado_e_acusado`, `..._do_fluxo_adulterado_e_acusado` | passa (4); o caso sobre evento do fluxo está pendente |

As 13 evidências do caso 1: documento de entrada, certidão de baixa, foto da recepção, etapa de recepção, etapa de descontaminação, foto da descontaminação, etapa de desmontagem, foto da desmontagem, peça não reutilizável descaracterizada, etapa de destruição, pesagem, foto da destruição e laudo.

## Ponta a ponta

`test_e2e_roteiro_demonstracao.py::test_e2e_roteiro_de_demonstracao` executa os nove passos do roteiro de `04-plano-de-execucao.md` em um único teste. Situação: pendente (`POST /mmvs`).

## Defeitos encontrados

Nenhum. Tudo o que a fundação já expõe passou, então não há registro novo em `pedidos-de-mudanca.md`.

## Leituras do contrato que os testes assumem

O contrato não fixa estes pontos. Os testes adotam a leitura abaixo; se a implementação escolher outra, o teste vai falhar na integração e a decisão é entre ajustar o contrato ou o código.

| Ponto | O que o teste assume |
| --- | --- |
| Nomes dos campos nas respostas | Os mesmos nomes das colunas de `02-arquitetura.md` (`credenciamento_status`, `tipo_declarado`, `codigo_rastreio`, `urv_debito`, `saldo_apos`, `titular_id`, `hash_conteudo` e os demais). |
| Criação | Responde 200 ou 201; os dois são aceitos. |
| Papel sem permissão | 403. Registro de outra empresa: 403 ou 404. |
| Segunda emissão de certificado, segundo laudo, fabricante sem registro de compromissos | 409 ou 422, sem `codigo` fixado. |
| Etiqueta em `GET /pecas/rastreio/{codigo}` | Campos `nome`, `chassi`, `data`, `cnpj` no corpo ou dentro de `etiqueta`; `destino` no corpo. |
| `GET /veiculos/{id}/pesagens` | `{itens, total, percentual_aproveitado}`. |
| Peça não reutilizável | Sem `codigo_rastreio` e sem `etiqueta`. |
| DMR | CNPJ do destinatário com dígito verificador inválido é 422. |
| Chassi | `POST /veiculos` rejeita o mesmo chassi com caixa ou espaços diferentes (409 ou 422). |
| Saldo | `regularizar_ate` some quando o saldo volta a ser zero ou positivo. |
| Consumo | `consumo.id` e `certificado.id` aparecem como `entidade_id` em algum evento da trilha. |
| Relatório ao MDIC | `registros` é o número de veículos registrados; `materiais` traz `peso_kg` por linha ou os pesos como valores. |
| Exportação | O arquivo tem uma chave com "versao" no nome e traz chassis, números de certificado e de DMR, laudo, peças e lançamentos. |
| Importação | Aceita o arquivo como upload no campo `arquivo` ou como corpo JSON; o teste tenta os dois. |

## Preparação feita fora da API

A regra de que os testes falam só por HTTP tem três exceções, todas em `conftest.py`, porque o contrato não oferece outro caminho:

| O quê | Por quê |
| --- | --- |
| Usuário das empresas criadas no teste, gravado direto em `usuario` | Não há rota de usuários (lacuna L-02). |
| Nova vigência de `FIM_SALDO_NEGATIVO` com data já passada | A API não deixa escolher a data da operação; é o único jeito de exercitar o bloqueio de saldo negativo posterior a 31/12/2027 (RF-19). |
| `efeitos_a_partir_de` de um MMV recuado para 01/01/2026 | Para registrar consumo de período passado e conferir a marca de fora do prazo (RF-20). |

Os casos de adulteração (RF-22 e antifraude 8) também vão ao banco, de propósito: é o ataque que se quer demonstrar.
