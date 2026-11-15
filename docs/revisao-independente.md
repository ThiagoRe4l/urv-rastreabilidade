# Revisão independente

Revisor: agente 05, sessão nova, sem participação na construção. Data: 2026-11-14. Base: `main` em `1c8248b`.

Método: li primeiro a portaria (`docs/portaria-325-2026.pdf`, inclusive as fórmulas do art. 3º, que só existem como imagem no PDF) e montei minha própria lista do que ela exige de uma solução tecnológica. Só depois li `01-requisitos.md`, o código e os testes. Parti da hipótese de que os 404 testes de conformidade passando escondem ao menos um descumprimento real: teste e código escritos a partir da mesma leitura errada passam juntos. Para cada suspeita escrevi um teste que **passa quando o problema existe** (`test_zz_revisor.py`, rodado numa cópia do backend fora do repositório; o código está no anexo A). Nada no repositório foi alterado além deste arquivo.

## Resumo

A hipótese se confirmou. Há quatro achados em que o código e os testes de conformidade compartilham a mesma leitura, e por isso a suíte passa sem acusar nada:

| # | Achado | Efeito | Evidência |
| --- | --- | --- | --- |
| A1 | RM por nível está invertido em relação ao texto da própria portaria | O débito de URV de todo MMV sai pela metade (nível 1) ou em dobro (nível 2) | `urv/calculo.py:15`; art. 3º §3º + art. 33; teste `a` |
| A2 | A meta de aproveitamento é calculada sobre o peso pesado, não sobre o peso do veículo | Pesar 10 kg de um carro de 1.200 kg dá "100 %, atende a meta" | `residuos/service.py:27-40`; art. 18 §5º; teste `c` |
| A3 | O débito é arredondado por lote que o próprio fabricante escolhe | Registrar um chassi por consumo reduz o débito em até 4,8 % (nível 1) | `urv/service.py:383`; art. 3º §§1º e 3º; teste `b` |
| A4 | A "imutabilidade verificável" cobre só a trilha; as tabelas de negócio são editáveis sem que a verificação perceba | Editar `urv_credito.quantidade` antes da transferência entrega 1,00 URV por um veículo de 0,38, e `/auditoria/verificar` responde "íntegra" | `auditoria/service.py:144-167`; art. 20 V; art. 24 I; teste `f` |

E quatro achados que a documentação não registra como lacuna: a importação de portabilidade cria URV sem nenhuma das pré-condições do certificado e para empresa com credenciamento cancelado (A5, teste `h`); a importação de consumo aceita Pb arbitrário (A6, teste `i`); a evidência de classificação é qualquer arquivo, reutilizável entre veículos, e Renavam, placa e certidão de baixa podem se repetir em chassis diferentes (A7, testes `d` e `e`); o fabricante não consegue ler o dossiê dos créditos que detém, embora responda por ele (A8, teste `g`).

## 1. Requisitos da portaria ausentes de `01-requisitos.md`

Lista feita antes de abrir `01-requisitos.md` e depois comparada com ela. Ficam aqui só os que não aparecem como RF, RNF, premissa ou lacuna.

| # | O que a portaria exige | Artigo | Situação no projeto |
| --- | --- | --- | --- |
| R1 | **Qv é a quantidade comercializada de um MMV**, não o tamanho de um lote escolhido pelo fabricante. O débito é uma conta por MMV (e, pelo art. 7º, por mês de comercialização), arredondada uma vez. | Art. 3º §§1º e 3º; art. 7º, parágrafo único | Ausente. Cada `POST /urv/consumos` é uma conta separada, arredondada por si (achado A3). |
| R2 | **Pm é um só por MMV no período**: média das notas fiscais de saída dos três meses anteriores ao consumo, ou preço público sugerido para modelo novo. | Art. 3º §4º | Lacuna L-URV-02 registra que Pm não é conferido com notas. Não registra que o fabricante pode declarar um Pm diferente a cada consumo do mesmo MMV e mês (teste `b`). |
| R3 | **A meta de aproveitamento é "sobre o peso total do veículo ou lote de veículos".** | Art. 18 §5º | RF-12 existe, mas a premissa "soma dos pesos por destino sobre o peso total destinado" troca o denominador. A portaria não é omissa aqui; a premissa contraria o texto (achado A2). |
| R4 | **Cadeia de custódia entre desmontadora e recicladora.** A desmontagem e triagem é feita pela desmontadora (art. 18 V); a destruição e trituração, pela recicladora (art. 18 VI); o trituramento exige equipamento que o Anexo II, item 28, atribui à recicladora. | Art. 18 V e VI; Anexo II 28; Anexo III 11 | Ausente. O veículo pertence a uma única empresa (`veiculo.empresa_id`, chassi único). Uma recicladora não consegue continuar um veículo que a desmontadora recebeu, e uma desmontadora registra ela mesma a etapa `DESTRUICAO` e emite o certificado: é o caminho padrão de `apoio.processar_veiculo`, usado por todos os testes de certificado. |
| R5 | **Enquadramento da sucata por laudo prévio ao leilão do órgão de trânsito, constando da nota fiscal de entrada ou do auto de arrematação**; dano do sinistrado enquadrado pela autoridade de trânsito. | Art. 2º §§2º e 4º | RF-07 reduz isso a "um anexo `EVIDENCIA_CLASSIFICACAO`". Nada liga o tipo declarado ao documento de entrada nem ao laudo do órgão (achado A7). |
| R6 | **Fabricante e importador guardam e apresentam a documentação comprobatória**, e respondem por falta de documentos com a perda da redução de IPI e multa. | Art. 9º; art. 10 | Ausente como requisito. O fabricante não lê certificado, laudo, fotos nem DMR dos créditos que recebeu (achado A8). |
| R7 | **"Já comercializado" é um fato verificável** (saída do estabelecimento ou desembaraço aduaneiro anterior ao cadastro) que decide se o MMV produz efeitos hoje ou só em 1º de janeiro. | Art. 5º §3º | Ausente. `ja_comercializado` é autodeclarado (`mmv/schemas.py:20-22`); declarar `false` antecipa os efeitos em até um ano. Não há lacuna registrada. |
| R8 | **Registro posterior em contingência**: o que foi protocolado no SEI durante indisponibilidade da solução deve ser registrado depois, com as datas originais. | Art. 5º §6º; art. 31 | Ausente. O início de efeitos do MMV é calculado pela data do cadastro na plataforma (`mmv/service.py:47`); não há como registrar a data do protocolo no SEI. |
| R9 | **Fator de sucata inservível alterável a requerimento** de desmontadora ou recicladora, por despacho, por tecnologia comprovada. | Art. 4º | Ausente. A vigência de `config_fator` é global por tipo; um fator concedido a uma empresa ou tecnologia não tem onde ser registrado. |
| R10 | **Peças obrigatoriamente não reutilizáveis** (itens de segurança, freios e direção danificados, estruturas deformadas, peças sem rastreabilidade). | Anexo III 7 | Ausente. A classificação é livre; um "airbag" pode ser registrado como `REUTILIZAVEL` e ganhar etiqueta. |
| R11 | **Prensagem em pátio de leilão registrada na solução**, para sucata inservível prensada fora da empresa. | Anexo II 27; art. 2º §1º II | Ausente. |
| R12 | **Destinação dos materiais exclusivamente em território nacional**, salvo inviabilidade comprovada. | Art. 18 §2º | Ausente como requisito. A DMR exige CNPJ (o que implica destinatário brasileiro), mas o destino `EXPORTACAO` da peça e a exceção de inviabilidade não têm regra nem registro. |
| R13 | **Comprovação de licenciamento regular** do veículo de fator 1,00: Renavam ativo, IPVA e licenciamento quitados do ano corrente ou anterior à baixa. | Art. 2º I | Registrado só como lacuna de integração (L-06, L-08). Vale notar que é o tipo de maior fator e o que a evidência genérica do RF-07 mais facilmente "comprova". |

## 2. Requisitos dados como atendidos que o código não atende

A matriz de conformidade marca todos os itens abaixo como "passa".

### A1. RF-18: RM invertido em relação ao texto da portaria

- **Código:** `backend/app/modules/urv/calculo.py:13-15`: `RM_POR_NIVEL = {1: 10, 2: 5}`, com o comentário "nível 1 (item 18 do Anexo III do Decreto 12.435/2025) usa RM 10".
- **Portaria:** o art. 3º §3º diz "RM: número de veículos que cumpram o requisito, conforme item 17 ou 18 do Anexo III ao Decreto nº 12.435, de 2025 (5 ou 10, respectivamente)". O art. 33, que altera a Portaria 213, diz "atendimento aos níveis 1 e 2 do requisito de reciclabilidade veicular, previstos nos itens 17 e 18 do referido Anexo". Lidos juntos, na ordem em que a própria portaria os põe: nível 1 = item 17 = RM 5; nível 2 = item 18 = RM 10. O projeto adota o oposto.
- **De onde veio:** a premissa está no primeiro commit de documentação (`b12201c`) e a lacuna L-01 diz que "o item 18 (nível 1) foi conferido", mas o decreto não está no repositório e a própria L-01 cita o art. 33 como origem, que diz o contrário. Não encontrei evidência dessa conferência.
- **Por que os testes não pegam:** `tests/conformidade/test_rf18_20_consumo.py:47-60` (`CASOS_DE_DEBITO`) e `tests/unit/urv/test_calculo.py` usam a mesma tabela. `agents/02-backend-urv.md:22-25` também. Código, testes e agentes partiram da mesma premissa.
- **Efeito:** 100 veículos de um MMV nível 1 no preço base debitam 10,00 URV; pela leitura literal seriam 20,00. Para nível 2 o erro inverte de sinal. Todo débito registrado está errado por um fator de 2, para mais ou para menos (teste `a`).
- **Ressalva honesta:** é possível que o Decreto 12.435/2025 numere os níveis de outro jeito e o art. 33 use "itens 17 e 18" sem correspondência de ordem. Mas então o projeto precisa juntar o texto do decreto e citar o trecho. Hoje a premissa contraria o único texto que está na pasta, e o CLAUDE.md manda que o texto da portaria vença.
- **Desfecho (2026-11-14): não confirmado.** O Decreto 12.435/2025 (`docs/decreto-12435-2025.pdf`, Anexo III, seção C, p. 16) define no item 17 o nível 2 como "para cada cinco veículos produzidos" e no item 18 o nível 1 como "para cada dez veículos produzidos": nível 1 = RM 10, nível 2 = RM 5. A leitura combinada dos arts. 33 e 3º §3º da portaria supôs que as duas listas ("níveis 1 e 2" e "itens 17 e 18") seguiam a mesma ordem, e não seguem. O código estava correto; faltava a fonte no repositório, o que foi corrigido: o decreto está em `docs/`, os itens 16 a 18 estão transcritos em `01-requisitos.md`, a lacuna L-01 foi resolvida com a citação e o teste `tests/revisao/test_revisao.py::test_a_rm_conforme_o_decreto` afirma os valores do decreto.

### A2. RF-12: meta de aproveitamento calculada sobre o que foi pesado, não sobre o veículo

- **Código:** `backend/app/modules/residuos/service.py:27-40`: `soma(peso com destino ≠ REJEITO) / soma(peso)`. `peso_entrada_kg`, que o veículo tem desde a recepção, não entra na conta. `documentos/service.py:299-325` grava esse percentual e `atende_meta` no certificado.
- **Portaria:** art. 18 §5º, metas "sobre o peso total do veículo ou lote de veículos"; §6º, peso destinado a reaproveitamento, reciclagem ou recuperação energética **e** dos rejeitos.
- **Efeito:** o rejeito que não é pesado some do denominador. Veículo de 1.200 kg com uma única pesagem de 10 kg de ferroso para reciclagem: certificado com `percentual_aproveitado = 100`, `meta_ano = 80`, `atende_meta = true` (teste `c`, com a data simulada em 15/01/2027). Os 1.190 kg restantes não aparecem em lugar nenhum. É exatamente o descumprimento que o art. 17 §2º diz que o MDIC vai apurar, e a plataforma mostra o contrário.
- **Por que os testes não pegam:** `test_rf11_13_pesagens_dmr.py:83-118` confere a mesma fórmula; `PESAGENS_PADRAO` soma 1.000 kg contra um `peso_entrada_kg` de 1.200 kg e ninguém compara os dois.

### A3. RF-18: o fabricante escolhe o lote, e o arredondamento por lote reduz o débito

- **Código:** `backend/app/modules/urv/service.py:383`: `calcular_debito(len(chassis), ...)` por requisição; `calculo.py:56-57` quantiza cada resultado em duas casas.
- **Portaria:** art. 3º §3º, Qv = "quantidade de veículos comercializados de uma mesma marca/modelo/versão"; art. 7º, reporte por mês.
- **Efeito:** MMV nível 1, Pm = 157.400,00. Um consumo com 10 chassis debita 1,05 URV. Dez consumos de um chassi debitam 10 × 0,10 = 1,00 URV (teste `b`). Com RM 10, qualquer Pm até 157.499,99 dá 0,10 por chassi isolado; a perda chega a 4,8 % do débito. O mesmo teste mostra dois consumos do mesmo MMV e do mesmo mês com Pm de 300.000,00 e 100.000,00, ambos aceitos.
- **Por que os testes não pegam:** os testes conferem a fórmula para uma lista de chassis; nenhum soma consumos do mesmo MMV no mês.

### A4. RF-22 e RNF-01: a trilha é íntegra, os dados que ela descreve não

- **Código:** só quatro tabelas têm gatilho de só inserção (`evento_auditoria`, `urv_lancamento`, `consumo`, `consumo_chassi`; `alembic/versions/0001_inicial.py:357`, `0002_defesa_livro_urv.py:36`). `veiculo`, `certificado`, `laudo`, `peca`, `pesagem`, `dmr`, `urv_credito`, `mmv` e `config_fator` aceitam `UPDATE` sem gatilho. `verificar_cadeia` (`auditoria/service.py:144-167`) só recalcula a cadeia contra ela mesma; não compara nenhum evento com o estado atual das tabelas.
- **Agravante:** a transferência escreve os lançamentos com `credito.quantidade` (`urv/service.py:265` e `273`), lido de uma tabela editável, e o consumo usa `mmv.nivel`, também editável.
- **Efeito (teste `f`):** crédito de sucata inservível (0,38). `UPDATE urv_credito SET quantidade = 1.00` e `UPDATE certificado SET fator = 1.00, tipo_veiculo = 'LICENCIADO_RODAGEM'`, sem desligar gatilho nenhum. Transferência: o fabricante recebe 1,00 URV. `UPDATE mmv SET nivel = 1` num MMV nível 2: o consumo de 10 chassis debita 1,00 em vez de 2,00. Depois de tudo, `GET /auditoria/verificar` responde `integra: true`. O relatório ao MDIC (`relatorios/service.py`, `urv_gerada`) soma `urv_credito.quantidade` e também passa a mostrar o valor adulterado.
- **Agravante 2 (teste `j`):** quem desliga o gatilho da trilha (o mesmo acesso que `scripts/adulterar.py` usa) pode reescrever um evento e recalcular os hashes seguintes: a verificação volta a dizer "íntegra". A arquitetura reconhece isso na seção "O que fica para a arquitetura-alvo", mas a lacuna L-03 registra só o truncamento da cauda, e `01-requisitos.md` dá RF-22 como "Sim, cadeia de hashes".
- **Por que os testes não pegam:** os testes de adulteração (`test_rnf07_antifraude.py`, caso 8 da matriz) adulteram só `evento_auditoria`, que é justamente a tabela protegida.

### A5. RF-25 e RNF-04: a importação cria URV sem nenhuma pré-condição do certificado

- **Código:** `backend/app/modules/portabilidade/service.py:404-632` (`_Importacao.veiculo`). Confere unicidade de chassi, número do certificado, fator vigente e coerência interna do arquivo. Não confere: credenciamento da geradora, etapas, fotos, documento de entrada, certidão de baixa, evidência de classificação, pesagens, peças descaracterizadas. As pré-condições 1 a 6 do RF-15 simplesmente não existem nesse caminho.
- **Hash opcional:** `portabilidade/schemas.py:235` declara `hash_conteudo: str | None`, e `service.py:815` só confere quando ele vem preenchido. Mesmo preenchido, é SHA-256 sem segredo: qualquer um recalcula (L-URV-09 reconhece que não prova a origem).
- **Efeito (teste `h`):** exportei o arquivo de uma desmontadora, troquei chassi e número do certificado, apaguei anexos, etapas, pesagens e peças, removi o hash, **cancelei o credenciamento da empresa** e importei como ADMIN. Resultado: veículo, certificado e 1,00 URV novos, sem uma foto sequer. O art. 8º I diz que o crédito é gerado "exclusivamente pelas empresas de desmontagem ou reciclagem credenciadas". A importação é restrita ao ADMIN, mas o ADMIN é o operador da plataforma, e os arts. 20 XII, 21 §3º e 25 VI existem para que o operador não possa fazer isso.
- **Documentação:** L-URV-06 a L-URV-09 descrevem limitações da importação, nenhuma diz que ela dispensa credenciamento e evidências.

### A6. RF-18 na importação: Pb vem do arquivo

- **Código:** `portabilidade/service.py:735`: `calcular_debito(c.qv, c.rm, c.pm, c.pb)` com `c.pb` do arquivo, sem comparar com `preco_base_vigente`. O MMV importado também traz `efeitos_a_partir_de` pronto do arquivo (`service.py:655`), sem recálculo pelo art. 5º §2º.
- **Efeito (teste `i`):** consumo de 100 chassis, nível 1, Pm 1.500.000,00, importado com Pb 1.500.000,00: débito de 10,00 URV, aceito. Com o Pb do art. 3º §5º seriam 100,00.

### A7. RF-07, RF-21 e RNF-07: evidência e identidade do veículo sem conferência

- **Evidência:** `veiculos/service.py:267-268`: qualquer imagem ou PDF enviado como `EVIDENCIA_CLASSIFICACAO` promove o veículo do tipo efetivo (0,38) ao tipo declarado (até 1,00). Nada confere o conteúdo, o `sha256` não é único entre veículos, e o mesmo arquivo serve para quantos veículos se quiser. Teste `d`: dois veículos `LICENCIADO_RODAGEM` com o mesmo arquivo de evidência e as mesmas fotos (o PNG 1×1 de `apoio.py`) em todas as etapas recebem fator 1,00 cada.
- **Identidade:** só o chassi é único (`models/veiculo.py:41`). Renavam, placa e número da certidão de baixa não (`models/veiculo.py:43` e `55`). Teste `d`: os dois veículos têm o mesmo Renavam, a mesma placa e a mesma certidão de baixa, e cada um gera um crédito. A certidão de baixa é um documento por veículo (art. 18 II); duas URV com a mesma certidão é o padrão de fraude que o art. 21 III ("mecanismos antifraude") pede para barrar.
- **Chassi:** `veiculos/schemas.py:46-52` aceita de 6 a 30 caracteres, sem validar VIN (o consumo valida VIN de 17; `urv/schemas.py:85-92`). Teste `e`: um chassi e o mesmo chassi com um "0" no fim são dois veículos. Como a reconciliação entre plataformas (arts. 28 e 29) compara a string do chassi, um caractere a mais derruba a detecção de duplicidade.

### A8. RF-23 e art. 9º: o fabricante não vê o dossiê do que comprou

- **Código:** `documentos/service.py:364-369` filtra o certificado pela empresa emitente; o laudo segue o veículo (`veiculos/service.py:49-64`).
- **Efeito (teste `g`):** depois da transferência, o fabricante titular do crédito recebe 404 em `GET /certificados/{id}` e em `GET /veiculos/{id}/laudo`. O art. 9º obriga o fabricante a manter a documentação comprobatória, e o art. 10 o pune pela falta dela. A plataforma não a entrega a ele.

### Fragilidades menores, sem teste próprio

- **Laudo antes da desmontagem.** `documentos/service.py:99-107` exige só descontaminação e destruição concluídas para o laudo, mas o laudo "atesta a execução das etapas de descontaminação, desmontagem, destruição" (art. 18 VII). Dá para assinar o laudo e só depois registrar a desmontagem. É parente da L-09, que trata de mudanças depois do laudo, mas não deste caso.
- **Certificado e URV sem DMR.** A DMR é exigida para comprovação (art. 6º III d), mas o certificado e o crédito saem sem ela, e nada sinaliza o veículo certificado que nunca foi destinado. O fluxo padrão dos testes (`apoio.gerar_credito`) nunca emite DMR.
- **Renovação do credenciamento sem nova comprovação.** `empresas/service.py:135-171` aceita um PATCH que empurra a validade para hoje + 2 anos quantas vezes se quiser; o art. 16 diz "renovável mediante nova comprovação dos requisitos".
- **Prazo de reporte sem feriados** (premissa documentada). Concreto: para o período 2026-12 o sistema fixa 14/01/2027; com o feriado nacional de 1º de janeiro, o décimo dia útil é 15/01/2027. O erro é para o lado conservador (marca como atrasado o que está no prazo), não esconde atraso.
- **Relatório ao MDIC soma importações como URV gerada no ano**, o que, numa consolidação entre plataformas (arts. 26 e 28), conta o mesmo crédito duas vezes.

## 3. Regras de cálculo conferidas à mão

### Fatores de equivalência (art. 3º §2º; Anexo I, itens 2 a 5)

Fator = 0,4·A + 0,3·C + 0,2·R + 0,1·D, com os índices normalizados do item 3. Conferido em `Decimal`, independentemente do código:

| Tipo | A | C | R | D | Bruto | HALF_UP | HALF_EVEN | Seed (`scripts/seed.py:46-52`) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Licenciado e rodando | 1,00 | 1,00 | 1,00 | 1,00 | 1,000 | 1,00 | 1,00 | 1.00 ✔ |
| Sucata aproveitável | 0,90 | 0,80 | 0,80 | 0,90 | 0,850 | 0,85 | 0,85 | 0.85 ✔ |
| Sucata aproveitável, motor inservível | 0,70 | 0,60 | 0,70 | 0,80 | 0,680 | 0,68 | 0,68 | 0.68 ✔ |
| Sucata inservível | 0,40 | 0,30 | 0,40 | 0,50 | 0,380 | 0,38 | 0,38 | 0.38 ✔ |
| Sinistrado, pequena ou média monta | 0,95 | 0,90 | 0,95 | 0,95 | 0,935 | 0,94 | 0,94 | 0.94 ✔ |
| Sinistrado, grande monta | 0,80 | 0,70 | 0,85 | 0,85 | 0,785 | **0,79** | **0,78** | 0.79 ✔ |

Os seis valores conferem com a tabela do art. 3º §2º. O caso de grande monta é o único sensível à regra: só o arredondamento do item 5 do Anexo I (meio para cima) dá 0,79. O código não calcula fatores, só os lê de `config_fator`; a metodologia do Anexo I não está implementada, então uma revisão do art. 3º §6º terá de ser calculada fora e digitada.

### Crédito (art. 3º §1º)

URV_crédito = Σ Qi·Feqi. O sistema gera um crédito por certificado, de valor igual ao fator (`urv/service.py:160`); a soma por tipo é a soma dos créditos. Conferido: sem arredondamento intermediário, porque cada parcela já tem duas casas. Correto, dado o fator.

### Débito (art. 3º §3º)

A fórmula da imagem no PDF é URV_débito = (Qv / RM) × max(1, Pm / Pb), com Pb = 150.000,00 (§5º). `calculo.py:56` calcula `qv·max(pm, pb) / (rm·pb)` com 50 dígitos e arredonda uma vez, em HALF_UP. Conferido à mão e pela função:

| Qv | RM | Pm | À mão | `calcular_debito` |
| --- | --- | --- | --- | --- |
| 7 | 5 | 187.500 | 1,4 × 1,25 = 1,75 | 1.75 ✔ |
| 7 | 5 | 100.000 | 1,4 × max(1; 0,667) = 1,40 | 1.40 ✔ |
| 3 | 10 | 165.000 | 0,3 × 1,1 = 0,33 | 0.33 ✔ |
| 250 | 10 | 189.990 | 25 × 1,2666 = 31,665 → 31,67 | 31.67 ✔ |
| 10 | 10 | 157.400 | 1 × 1,04933 = 1,0493 → 1,05 | 1.05 ✔ |
| 1 | 10 | 157.400 | 0,1 × 1,04933 = 0,10493 → 0,10 | 0.10 (ver A3) |

A aritmética está certa. O que está errado é o RM associado a cada nível (A1) e a unidade sobre a qual a fórmula é aplicada (A3).

### Prazos

| Regra | Entrada | À mão | Sistema |
| --- | --- | --- | --- |
| Décimo dia útil do mês seguinte (art. 7º) | período 2026-11 | 14/12/2026 | 2026-12-14 ✔ |
| idem | período 2026-12 | 15/01/2027 (1º/01 é feriado nacional) | 2027-01-14 ✘ (premissa sem feriados) |
| Regularização: último dia do 3º mês seguinte (art. 8º §1º) | registro 14/11/2026 | 28/02/2027 | 2027-02-28 ✔ |
| idem | registro 30/11/2027 | 29/02/2028 | 2028-02-29 ✔ |
| Fim da exceção de saldo negativo (art. 8º §1º) | operação em 31/12/2027 | permitida | permitida (`hoje <= limite`, `urv/service.py:389`) ✔ |
| Metas (art. 18 §5º) | 2026 / 2027 / 2029 / 2031 / 2033 | sem meta / 80 / 85 / 90 / 95 | `residuos/service.py:43-53` ✔ (o denominador é que está errado, A2) |

## 4. Segurança e isolamento entre empresas

Conferi rota por rota (`grep` de `exige_papel`, `filtrar_por_empresa`, `garantir_acesso_empresa` e `empresa_consultada` em todos os `router.py`).

**O que está bem feito.** Toda leitura de empresa filtra pelo `empresa_id` do token, e o registro de outra empresa responde 404 sem revelar que existe (`core/deps.py:83-93`). O AUDITOR é barrado em qualquer método de escrita numa dependência comum a todas as rotas (`core/deps.py:51-53`). A trilha e o relatório ao MDIC são só de AUDITOR e ADMIN. A transferência confere geradora, titular, vínculo e registro de compromissos, com `SELECT ... FOR UPDATE` e índice único `(credito_id, tipo)` como segunda barreira. O upload confere o tipo pelos primeiros bytes e grava com nome gerado, sem caminho do cliente. A consulta pública de etiqueta usa código aleatório de 64 bits, não enumerável. Não achei vazamento de dados entre empresas.

**O que não está.**

| # | Falha | Evidência |
| --- | --- | --- |
| S1 | O ADMIN cria URV por importação, sem evidência e para empresa com credenciamento cancelado. O operador da plataforma consegue fabricar crédito. | A5; teste `h` |
| S2 | Tabelas de negócio editáveis por quem tem acesso ao banco, sem que a verificação perceba; a transferência propaga o valor adulterado ao livro, que é só de inserção. | A4; teste `f` |
| S3 | Quem desliga um gatilho reescreve a trilha inteira e a recalcula; a cadeia não tem âncora externa nem segredo. | A4; teste `j`; arquitetura, "O que fica para a arquitetura-alvo" |
| S4 | A assinatura do laudo é HMAC com chave do servidor (L-07): prova que o servidor gerou, não que o responsável técnico assinou. Qualquer usuário DESMONTADORA digita qualquer nome e registro de responsável técnico. | `documentos/service.py:149`; L-07 |
| S5 | O segredo JWT tem valor padrão no `docker-compose.yml` ("segredo-local-de-demonstracao-nao-usar-em-producao"). Aceitável num MVP local, mas é o tipo de coisa que vai para produção sem querer. | `docker-compose.yml`, serviço `api` |
| S6 | O arquivo de portabilidade não tem assinatura de origem; o hash é opcional e recalculável. | `portabilidade/schemas.py:235`; `service.py:815`; L-URV-09 |
| S7 | O fabricante não lê o dossiê dos créditos que detém. Não é vazamento, é o oposto: falta de acesso a dado que é dele por obrigação legal. | A8; teste `g` |

## 5. Resultado de `pytest` e de `scripts/adulterar.py`

### Suíte do projeto

Rodada no container da API, com o código da `main` montado por volume (o banco de teste é separado do banco de demonstração):

```
docker compose run --rm --no-deps -v ./backend:/app api python -m pytest -q
741 passed in 386.43s (0:06:26)
```

Bate com o que a matriz de conformidade declara (741 na suíte inteira, 404 de conformidade). Nenhum teste falha, nenhum é `xfail`.

### Testes adversariais do revisor

Dez testes, cada um escrito para **passar quando o problema existe**. Rodados numa cópia do backend no diretório temporário da sessão, com os fixtures de `tests/conformidade` (o código está no anexo A):

```
test_zz_revisor.py::test_a_rm_invertido_em_relacao_ao_art_33 PASSED
test_zz_revisor.py::test_b_fracionar_consumo_reduz_debito PASSED
test_zz_revisor.py::test_c_meta_ignora_o_peso_do_veiculo PASSED
test_zz_revisor.py::test_d_mesma_evidencia_renavam_placa_e_certidao_em_dois_chassis PASSED
test_zz_revisor.py::test_e_chassi_de_veiculo_em_fim_de_vida_nao_e_vin PASSED
test_zz_revisor.py::test_f_adulterar_tabela_de_negocio_nao_quebra_a_trilha PASSED
test_zz_revisor.py::test_g_fabricante_nao_acessa_o_dossie_do_credito_que_detem PASSED
test_zz_revisor.py::test_h_importacao_cria_urv_sem_evidencias_para_empresa_cancelada PASSED
test_zz_revisor.py::test_i_importacao_de_consumo_aceita_pb_arbitrario PASSED
test_zz_revisor.py::test_j_reescrever_um_evento_e_recalcular_a_cadeia_passa_na_verificacao PASSED
10 passed in 11.09s
```

Os dois resultados juntos são o ponto deste relatório: 741 testes verdes e 10 descumprimentos confirmados ao mesmo tempo. O teste `a` não chama a API: confere só a tabela de RM contra a leitura literal, porque o achado está na premissa e não na aritmética.

### `scripts/adulterar.py`

Rodado contra a API no ar (`docker compose exec api python -m scripts.adulterar`) e desfeito com `--restaurar`:

```
1. Antes: 70 eventos, cadeia ÍNTEGRA
2. UPDATE direto no evento 70...
   Rejeitado pelo banco: Tabela evento_auditoria é só de inserção: UPDATE rejeitado (RF-22, art. 20 V)
3. Desligando o gatilho e alterando o payload do evento 70...
4. Depois: 70 eventos, cadeia QUEBRADA na sequência 70
   Desfazer: python -m scripts.adulterar --restaurar

Eventos restaurados: 1
Verificação: 70 eventos, cadeia ÍNTEGRA
```

O script faz o que promete: o gatilho barra o `UPDATE` comum e a verificação acusa a alteração feita com o gatilho desligado. Mas ele demonstra o ataque mais fácil de pegar. Os testes `f` e `j` mostram dois ataques que ele não cobre: alterar a tabela de negócio em vez da trilha (nenhum gatilho a desligar, verificação "íntegra") e alterar a trilha recalculando os hashes seguintes (verificação "íntegra").

## 6. As cinco perguntas mais difíceis de um avaliador

**1. "O débito de URV do seu sistema está certo?"**

A aritmética está certa: conferi a fórmula do art. 3º §3º à mão em seis casos, e o arredondamento HALF_UP sem passos intermediários. O que não posso garantir é o RM. O sistema usa RM 10 para o nível 1 e RM 5 para o nível 2, e a própria portaria, lida pelo art. 33 junto com o art. 3º §3º, aponta o contrário. A premissa nunca foi conferida contra o Decreto 12.435/2025, que não está no repositório, e os testes foram escritos com a mesma premissa. Até alguém juntar o texto do decreto, todo débito pode estar errado por um fator de 2. Além disso, o fabricante consegue reduzir o próprio débito em até 4,8 % só registrando um chassi por vez.

**2. "Como o sistema garante que um registro não foi alterado depois de feito?"**

Garante para quatro tabelas: a trilha de eventos, o livro de lançamentos e as duas de consumo, por gatilho de só inserção e pela cadeia de hashes. Não garante para o resto: certificado, crédito, veículo, laudo, MMV e fatores podem ser editados por quem tem acesso ao banco, e a verificação continua dizendo "íntegra", porque ela confere a cadeia contra si mesma e não contra os dados. Pior, a transferência lê a quantidade do crédito da tabela editável e a grava no livro protegido. E quem tem poder de desligar um gatilho também consegue reescrever a cadeia e recalcular os hashes. A resposta honesta é: o sistema detecta adulteração feita por quem não sabe como ele funciona. Contra o operador, falta ancorar a cadeia fora do banco (carimbo de tempo ou registro público) e conferir as tabelas de negócio contra os eventos.

**3. "O que impede uma desmontadora de gerar URV de 1,00 para um veículo que valia 0,38?"**

Hoje, quase nada. Basta declarar o tipo e enviar um arquivo qualquer como evidência de classificação. O mesmo arquivo pode servir para cem veículos. Renavam, placa e certidão de baixa podem se repetir em chassis diferentes, e o chassi aceita qualquer sequência de 6 a 30 caracteres. A portaria diz que o enquadramento vem de laudo do órgão de trânsito, prévio ao leilão, constando da nota fiscal ou do auto de arrematação (art. 2º §2º), e o sistema não liga uma coisa à outra. As integrações com Renavam e nota fiscal existem como interface falsa, mas a recepção nem as chama (L-08). Para um MVP isso é aceitável se estiver escrito. O problema é que a matriz marca o antifraude (RNF-07) como "passa".

**4. "O operador da plataforma consegue criar crédito?"**

Consegue. O ADMIN importa um arquivo de portabilidade montado à mão, sem hash, sem nenhuma foto, etapa ou evidência, para uma empresa com credenciamento cancelado, e a plataforma cria certificado e crédito de URV (teste `h`). O ADMIN também consegue empurrar a validade do credenciamento indefinidamente. A portaria constrói toda a seção de credenciamento de soluções (arts. 20, 21 §3º, 25 VI) em torno da independência do operador. A correção mínima é a importação exigir as mesmas pré-condições do certificado e o credenciamento vigente na data da emissão de origem, e o arquivo vir assinado pela plataforma de origem.

**5. "A plataforma ajuda o MDIC a ver o descumprimento das metas de reciclagem?"**

Hoje, atrapalha. A meta do art. 18 §5º é sobre o peso total do veículo, e o sistema calcula sobre o peso que alguém escolheu pesar. Um veículo de 1.200 kg com 10 kg pesados aparece no certificado como "100 %, atende a meta de 80 %". O MDIC, que pela premissa do projeto é quem apura o descumprimento (art. 17 §2º), recebe da plataforma um indicador verde para um caso que deveria ser o mais vermelho. A correção é simples: usar `peso_entrada_kg` como denominador e tratar a diferença entre o peso de entrada e a soma das pesagens como rejeito não declarado.

## Anexo A. Código dos testes adversariais

Arquivo `tests/conformidade/test_zz_revisor.py`, usado numa cópia do backend e não incluído no repositório. Usa os fixtures e auxiliares de `tests/conformidade` (`api`, `db_session`, `nova_empresa`, `apoio.*`). Para reproduzir: copiar para `backend/tests/conformidade/`, rodar `pytest tests/conformidade/test_zz_revisor.py` e apagar em seguida.

```python
"""Testes adversariais do revisor independente. Cada teste PASSA quando o problema EXISTE.

Rodam numa cópia do backend, fora do repositório.
"""

import secrets
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import text

from app.core.relogio import agora
from app.modules.portabilidade.service import hash_documento
from app.modules.urv.calculo import calcular_debito, rm_do_nivel
from tests.conformidade.apoio import (
    ADMIN,
    AUDITOR,
    FISCAL,
    OPERADOR,
    chassis,
    consumir,
    criar_mmv,
    dec,
    emitir_certificado,
    gerar_credito,
    novo_chassi,
    ok,
    processar_veiculo,
    receber_veiculo,
    saldo,
    transferir,
)


def _fab_id(api):
    return ok(api.get("/auth/me", FISCAL))["empresa"]["id"]


def test_a_rm_invertido_em_relacao_ao_art_33():
    assert rm_do_nivel(1) == 10 and rm_do_nivel(2) == 5
    pm = pb = Decimal("150000")
    assert calcular_debito(100, rm_do_nivel(1), pm, pb) == Decimal("10.00")  # o sistema
    assert calcular_debito(100, 5, pm, pb) == Decimal("20.00")  # leitura literal: nível 1 = item 17 = RM 5


def test_b_fracionar_consumo_reduz_debito(api):
    pm = "157400.00"
    mmv = criar_mmv(api, nivel=1)
    lote = ok(consumir(api, FISCAL, mmv["id"], chassis(10), preco_medio=pm))
    assert dec(lote["urv_debito"]) == dec("1.05")
    mmv2 = criar_mmv(api, nivel=1)
    total = Decimal(0)
    for c in chassis(10):
        total += dec(ok(consumir(api, FISCAL, mmv2["id"], [c], preco_medio=pm))["urv_debito"])
    assert total == dec("1.00")  # 10 consumos de 1 chassi: 0,05 URV a menos (4,8%)
    # Mesmo MMV, mesmo período, Pm diferente a cada consumo: aceito.
    a = ok(consumir(api, FISCAL, mmv["id"], chassis(5), preco_medio="300000.00"))
    b = ok(consumir(api, FISCAL, mmv["id"], chassis(5), preco_medio="100000.00"))
    assert a["periodo"] == b["periodo"] and dec(a["pm"]) != dec(b["pm"])


def test_c_meta_ignora_o_peso_do_veiculo(api, client):
    client.app.dependency_overrides[agora] = lambda: datetime(2027, 1, 15, 15, 0, tzinfo=UTC)
    try:
        v = processar_veiculo(
            api, OPERADOR, peso_entrada_kg="1200.000", pesagens=[("FERROSO", "RECICLAGEM", "10.000")]
        )
        cert = ok(emitir_certificado(api, OPERADOR, v["id"]))
    finally:
        client.app.dependency_overrides.pop(agora, None)
    # 10 kg pesados de um veículo de 1.200 kg: 0,83 % do peso, e o sistema diz 100 % e "atende".
    assert dec(cert["percentual_aproveitado"]) == dec("100")
    assert dec(cert["meta_ano"]) == dec("80")
    assert cert["atende_meta"] is True


def test_d_mesma_evidencia_renavam_placa_e_certidao_em_dois_chassis(api):
    comum = {
        "tipo": "LICENCIADO_RODAGEM",
        "placa": "ABC1D23",
        "renavam": "12345678901",
        "certidao_baixa_numero": "CB-0001",
        "documento_entrada_numero": "NF-0001",
    }
    _, c1 = gerar_credito(api, OPERADOR, **comum)
    _, c2 = gerar_credito(api, OPERADOR, **comum)
    # Os dois veículos usam o MESMO arquivo como evidência de classificação (apoio.PDF) e as
    # MESMAS fotos (apoio.PNG, 1x1 pixel) em todas as etapas: fator 1,00 para os dois.
    assert dec(c1["fator"]) == dec(c2["fator"]) == dec("1.00")
    assert c1["chassi"] != c2["chassi"]


def test_e_chassi_de_veiculo_em_fim_de_vida_nao_e_vin(api):
    base = novo_chassi()
    receber_veiculo(api, OPERADOR, chassi=base)
    receber_veiculo(api, OPERADOR, chassi=base + "0")
    receber_veiculo(api, OPERADOR, chassi="ABC123")  # 6 caracteres aceitos


def test_f_adulterar_tabela_de_negocio_nao_quebra_a_trilha(api, db_session):
    fab = _fab_id(api)
    _, cert = gerar_credito(api, OPERADOR)  # sucata inservível: 0,38
    assert dec(cert["fator"]) == dec("0.38")
    cid = cert["credito"]["id"]
    db_session.execute(text("UPDATE urv_credito SET quantidade = 1.00 WHERE id = :i"), {"i": cid})
    db_session.execute(
        text("UPDATE certificado SET fator = 1.00, tipo_veiculo = 'LICENCIADO_RODAGEM' WHERE id = :i"),
        {"i": cert["id"]},
    )
    db_session.flush()
    antes_fab, antes_ger = saldo(api, FISCAL), saldo(api, OPERADOR)
    ok(transferir(api, OPERADOR, cid, fab))
    assert saldo(api, FISCAL) - antes_fab == dec("1.00")  # recebeu 1,00 por um veículo de 0,38
    assert saldo(api, OPERADOR) - antes_ger == dec("-1.00")

    mmv = criar_mmv(api, nivel=2)
    db_session.execute(text("UPDATE mmv SET nivel = 1 WHERE id = :i"), {"i": mmv["id"]})
    db_session.flush()
    consumo = ok(consumir(api, FISCAL, mmv["id"], chassis(10)))
    assert consumo["rm"] == 10 and dec(consumo["urv_debito"]) == dec("1.00")  # deveria ser 2,00

    verif = ok(api.get("/auditoria/verificar", AUDITOR))
    assert verif["integra"] is True


def test_g_fabricante_nao_acessa_o_dossie_do_credito_que_detem(api):
    _, cert = gerar_credito(api, OPERADOR)
    ok(transferir(api, OPERADOR, cert["credito"]["id"], _fab_id(api)))
    assert api.get(f"/certificados/{cert['id']}", FISCAL).status_code in (403, 404)
    assert api.get(f"/veiculos/{cert['veiculo_id']}/laudo", FISCAL).status_code in (403, 404)


def test_h_importacao_cria_urv_sem_evidencias_para_empresa_cancelada(api, nova_empresa):
    g = nova_empresa("DESMONTADORA")
    _, cert = gerar_credito(api, g.email, tipo="LICENCIADO_RODAGEM")
    arq = ok(api.get("/portabilidade/exportar", g.email))

    chassi = novo_chassi()
    numero = f"CRV-2026-{secrets.token_hex(5).upper()}"
    v = arq["veiculos"][0]
    v["chassi"] = chassi
    v["anexos"] = []  # nenhuma foto, nenhum documento, nenhuma evidência de classificação
    v["etapas"] = []  # nenhuma etapa
    v["pesagens"] = []
    v["pecas"] = []
    arq["certificados"][0].update(chassi=chassi, numero=numero)
    arq["creditos"][0].update(chassi=chassi, certificado_numero=numero)
    arq["lancamentos"] = []
    arq["hash_conteudo"] = None  # o hash do arquivo é opcional: sem ele, nada é conferido

    ok(api.patch(f"/empresas/{g.id}/credenciamento", ADMIN, json={"status": "CANCELADO", "validade": "2028-11-14"}))
    antes = saldo(api, g.email)
    r = ok(api.post("/portabilidade/importar", ADMIN, json=arq))
    assert any(i["tipo"] == "veiculo" for i in r["importados"]), r
    assert saldo(api, g.email) - antes == dec("1.00")
    assert cert["numero"] != numero
    # E com hash: qualquer um recalcula, porque não há segredo nem assinatura.
    arq2 = ok(api.get("/portabilidade/exportar", g.email))
    assert arq2["hash_conteudo"] == hash_documento(arq2)


def test_i_importacao_de_consumo_aceita_pb_arbitrario(api, nova_empresa):
    f = nova_empresa("FABRICANTE")
    mmv = criar_mmv(api, f.email, nivel=1)
    arq = ok(api.get("/portabilidade/exportar", f.email))
    ch = chassis(100)
    pb = "1500000.00"  # dez vezes o Pb do art. 3º §5º
    arq["mmvs"] = []
    arq["consumos"] = [
        {
            "referencia": "X-1",
            "mmv_codigo": mmv["codigo"],
            "periodo": "2026-10",
            "qv": 100,
            "rm": 10,
            "pm": "1500000.00",
            "pb": pb,
            "urv_debito": str(calcular_debito(100, 10, Decimal("1500000.00"), Decimal(pb))),
            "saldo_apos": "-10.00",
            "prazo_reporte": "2026-11-14",
            "registrado_em": "2026-10-20T12:00:00+00:00",
            "chassis": ch,
        }
    ]
    arq["hash_conteudo"] = None
    r = ok(api.post("/portabilidade/importar", ADMIN, json=arq))
    assert any(i["tipo"] == "consumo" for i in r["importados"]), r
    # Com Pb = 150.000 o débito seria (100/10) x (1.500.000/150.000) = 100,00 URV.
    assert saldo(api, f.email) == dec("-10.00")


def test_j_reescrever_um_evento_e_recalcular_a_cadeia_passa_na_verificacao(api, db_session):
    from app.models import EventoAuditoria
    from app.modules.auditoria.service import calcular_hash

    _, cert = gerar_credito(api, OPERADOR)
    db_session.execute(text("ALTER TABLE evento_auditoria DISABLE TRIGGER trg_evento_auditoria_imutavel"))
    db_session.execute(
        text(
            "UPDATE evento_auditoria SET payload = jsonb_set(payload, '{quantidade}', '\"1.00\"') "
            "WHERE tipo = 'CREDITO_GERADO' AND entidade_id = :i"
        ),
        {"i": cert["credito"]["id"]},
    )
    anterior = None
    for ev in db_session.scalars(select_eventos(EventoAuditoria)):
        if anterior is not None:
            ev.hash_anterior = anterior
        ev.hash = calcular_hash(
            ev.hash_anterior, ev.ocorrido_em, ev.usuario_id, ev.empresa_id,
            ev.tipo, ev.entidade, ev.entidade_id, ev.payload,
        )
        db_session.flush()
        anterior = ev.hash
    db_session.execute(text("ALTER TABLE evento_auditoria ENABLE TRIGGER trg_evento_auditoria_imutavel"))
    db_session.expire_all()
    verif = ok(api.get("/auditoria/verificar", AUDITOR))
    assert verif["integra"] is True


def select_eventos(modelo):
    from sqlalchemy import select

    return select(modelo).order_by(modelo.sequencia)
```
