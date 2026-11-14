# Requisitos

Origem: Portaria GM/MDIC nº 325, de 6 de novembro de 2026 (`portaria-325-2026.pdf`). Cada requisito aponta o artigo de onde saiu. A coluna MVP diz se entra na entrega local.

## Funcionais

| ID | Requisito | Origem | MVP |
| --- | --- | --- | --- |
| RF-01 | Cadastro de empresas por papel (fabricante ou importador, desmontadora, recicladora) com situação e validade do credenciamento (2 anos) | Arts. 11 e 16 | Sim, credenciamento lançado pelo admin |
| RF-02 | Vínculo comercial entre desmontadora ou recicladora e cada fabricante | Art. 13 §1º VI e §2º | Sim |
| RF-03 | Cadastro de MMV com código, NCM, nível 1 ou 2 e percentual de reciclabilidade | Art. 5º | Sim |
| RF-04 | Data de início de efeitos do MMV: 1º de janeiro seguinte se já comercializado; data do cadastro se novo | Art. 5º §§2º e 3º | Sim |
| RF-05 | Retirada de MMV a pedido até 31 de dezembro | Art. 5º §§4º e 5º | Não |
| RF-06 | Recepção do veículo com chassi, placa, Renavam, data, nota fiscal de entrada ou auto de arrematação e certidão de baixa | Art. 6º I; art. 18 III; Anexo III 14.a | Sim |
| RF-07 | Classificação do tipo com evidência; sem evidência de classificação (todo tipo diferente de sucata inservível), o veículo é sucata inservível | Art. 2º §§2º a 5º; art. 6º I c | Sim |
| RF-08 | Registro de cada etapa com fotos (recepção, descontaminação, desmontagem, separação) | Art. 6º III c; art. 18 §1º | Sim, arquivos locais |
| RF-09 | Peças classificadas como reutilizáveis ou não; reutilizáveis etiquetadas com QR Code contendo nome, chassi, data e CNPJ | Art. 18 V; Anexo III 6 a 8 | Sim |
| RF-10 | Consulta de peças por origem, tipo, condição e destino | Anexo III 16 | Sim |
| RF-11 | Peso por fração de material e por veículo, com rateio em lotes | Art. 18 §6º; Anexo III 14.c | Sim, sem rateio de lote |
| RF-12 | Percentual aproveitado comparado à meta do ano | Art. 18 §5º | Sim, como alerta |
| RF-13 | DMR com nome e CNPJ do destinatário por tipo de material | Art. 6º III d; Anexo III 14.d | Sim, MTR do SINIR simulado |
| RF-14 | Laudo de Reciclagem assinado pelo responsável técnico | Art. 18 VII; Anexo III 15.b | Sim, assinatura simulada |
| RF-15 | Certificado de Reciclagem Veicular emitido só com etapas e evidências completas | Art. 18 VIII; art. 8º I | Sim |
| RF-16 | Crédito de URV gerado pelo certificado, no valor do fator do veículo | Art. 3º §§1º e 2º; art. 18 §3º | Sim |
| RF-17 | Transferência direta e única da geradora ao fabricante com vínculo; intermediação vedada | Art. 8º II e §3º | Sim |
| RF-18 | Consumo por chassi de veículo novo, com cálculo do débito por MMV | Art. 3º §3º; art. 6º II; art. 8º III | Sim |
| RF-19 | Bloqueio de saldo negativo; exceção até 31/12/2027 com regularização até o último dia do terceiro mês seguinte | Art. 8º III e §1º | Sim |
| RF-20 | Prazo de reporte do consumo: décimo dia útil do mês seguinte | Art. 7º, parágrafo único | Sim, como alerta |
| RF-21 | Unicidade: um chassi em fim de vida gera crédito uma vez; um chassi novo consome uma vez | Arts. 28 e 29 | Sim |
| RF-22 | Trilha de auditoria imutável e verificável de todos os eventos | Art. 20 V; art. 24 I | Sim, cadeia de hashes |
| RF-23 | Visão de auditoria com leitura de todos os registros | Art. 9º; art. 24 V | Sim |
| RF-24 | Relatórios ao MDIC: registros e certificados emitidos, volume de materiais, incidentes | Art. 27 | Parcial: os dois primeiros |
| RF-25 | Exportação padronizada para portabilidade e reconciliação entre plataformas | Art. 22 | Sim, JSON |
| RF-26 | Guarda de documentos por cinco anos | Art. 9º, parágrafo único | Não, só documentado |

## Não funcionais

| ID | Requisito | Origem | Resposta no MVP |
| --- | --- | --- | --- |
| RNF-01 | Confidencialidade, integridade, autenticidade e imutabilidade dos registros | Art. 20 V; art. 24 I | Tabelas só de inserção, eventos encadeados por hash, rota de verificação, acesso por papel |
| RNF-02 | Segurança cibernética e LGPD | Art. 20 VI | Dados pessoais mínimos; política documentada |
| RNF-03 | APIs seguras e padrões abertos | Art. 20 VII | REST, OpenAPI, token JWT |
| RNF-04 | Interoperabilidade entre plataformas | Art. 22; art. 21 §5º; art. 28 | Exportação e importação em JSON versionado; rejeição de chassi já creditado |
| RNF-05 | Sem aprisionamento do usuário | Art. 19 §2º; art. 24 X | Histórico completo exportável pela própria empresa |
| RNF-06 | Acesso supervisionado do MDIC | Art. 24 V | Papel AUDITOR, somente leitura |
| RNF-07 | Mecanismos antifraude | Art. 21 III; art. 25 VI | Unicidade de chassi, certificado bloqueado sem evidências, trilha verificável |
| RNF-08 | SAST e DAST por terceiro independente | Art. 23 VII | Análise estática local; laudo independente fora do escopo |
| RNF-09 | Disponibilidade de 99,5% e contingência | Art. 20 VIII | Fora do escopo |
| RNF-10 | Incidente crítico comunicado em 24 horas | Art. 24 III | Fora do escopo |
| RNF-11 | Dados do programa pertencem ao MDIC | Art. 19 §3º | Sem uso secundário |
| RNF-12 | Requisitos societários do operador | Art. 20 I, II e XII; art. 21 §3º | Não é requisito de software |

## Premissas adotadas onde a portaria é omissa

| Tema | Premissa |
| --- | --- |
| RM por nível | Parâmetro com vigência em `config_parametro` (`RM_NIVEL_1`, `RM_NIVEL_2`), não constante no código. O seed grava nível 1 = 10 e nível 2 = 5, a leitura anterior à revisão, **sem conferência contra o decreto**: o texto dos itens 16 a 18 do Anexo III do Decreto 12.435/2025 ainda não está em `docs/` (lacuna L-01, aberta). A portaria, lida pelo art. 33 junto com o art. 3º §3º, sugere o inverso (nível 1 = item 17 = RM 5). Trocar a leitura é gravar nova vigência dos dois parâmetros, sem mudar código |
| Débito de URV | Decimal com duas casas, `ROUND_HALF_UP`, sem arredondar para inteiro. Qv é a quantidade comercializada do MMV no mês (art. 3º §3º; art. 7º): o débito é calculado no acumulado por fabricante, MMV e período, arredondado uma vez, e cada consumo debita a diferença entre o débito do Qv acumulado e o já debitado no período. Registrar um chassi por vez não reduz o débito (achado A3 da revisão) |
| Pm, RM e Pb no período | Pm é um só por MMV e período (art. 3º §4º): consumo com Pm diferente do primeiro do período é rejeitado (422 `PM_DIVERGENTE_NO_PERIODO`). RM e Pb ficam os do primeiro consumo do período, para o acumulado ser uma conta só, mesmo que a vigência mude no meio do mês |
| Certificado | Um por chassi |
| Crédito | Indivisível; transferido inteiro a um único fabricante |
| Titular do crédito | A empresa que emite o certificado |
| Formato de troca entre plataformas | JSON próprio, versionado, isolado em um módulo |
| Peso aproveitado | Não é premissa: o art. 18 §5º fixa a meta "sobre o peso total do veículo ou lote de veículos". Percentual = soma das pesagens com destino diferente de `REJEITO` sobre o `peso_entrada_kg` do veículo. O peso de entrada que nenhuma pesagem contabilizou conta como não aproveitado, e pesagens que somariam mais que o peso de entrada são rejeitadas (422 `PESO_ACIMA_DA_ENTRADA`). A leitura anterior ("sobre o peso total destinado") trocava o denominador (achado A2 da revisão) |
| Meta de aproveitamento | Gera alerta, não bloqueia o certificado (o descumprimento é apurado pelo MDIC, art. 17 §2º) |
| Dia útil | Segunda a sexta, sem calendário de feriados |
| Evidência de classificação | Todo tipo diferente de `SUCATA_INSERVIVEL`, inclusive o veículo licenciado em condições de rodagem, exige evidência de classificação (art. 6º I c). Sem ela, o veículo é tratado como sucata inservível, com o tipo declarado preservado. Isso estende ao veículo licenciado a regra do art. 2º §5º, que a portaria aplica só a sucata e sinistrado |
