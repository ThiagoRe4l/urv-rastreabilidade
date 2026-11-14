# Contrato da API

Base: `/api/v1`. JSON em snake_case. Autenticação por `Authorization: Bearer <token>`, exceto login e consulta pública de etiqueta. O OpenAPI gerado pelo FastAPI em `/openapi.json` deve refletir este documento; o frontend gera os tipos a partir dele.

Erros seguem `{ "detail": "mensagem", "codigo": "CODIGO_ESTAVEL", "pendencias": ["..."] }`. `pendencias` só aparece em 422 de pré-condição (`PENDENCIAS_LAUDO`, `PENDENCIAS_CERTIFICADO`). Conflito com o estado de um registro que já existe (chassi, laudo, certificado ou crédito repetido) é 409; regra violada pelo que foi enviado é 422.

Convenções de valor: `percentual_aproveitado` vai em pontos, de 0 a 100. `origem_aquisicao` é um de `COMPRA_DIRETA`, `LEILAO_ORGAO_PUBLICO`, `LEILAO_SEGURADORA` (art. 18 I). `tipo_material` da DMR é texto livre. Fatores e parâmetros valem a partir de 2026-11-09, data de publicação da portaria.

Listas aceitam `?pagina=1&tamanho=20` e devolvem `{ "itens": [], "total": 0 }`.

Todo valor `Decimal` (URV, fator, preço, peso, percentual) trafega como string JSON, por exemplo `"0.94"` e `"150000.00"`, nas respostas e de preferência também nas entradas. Isso evita perda de precisão de ponto flutuante.

## Fundação

| Método e rota | Papel | Entrada | Saída |
| --- | --- | --- | --- |
| `POST /auth/login` | público | `email`, `senha` | `access_token`, `usuario` |
| `GET /auth/me` | todos | | `id`, `nome`, `email`, `papel`, `empresa` |
| `POST /empresas` | ADMIN | `cnpj`, `razao_social`, `tipo`, `registro_compromissos?` | Empresa |
| `GET /empresas` | ADMIN, AUDITOR; demais veem contrapartes com vínculo | `?tipo=` | Lista de Empresa |
| `PATCH /empresas/{id}` | ADMIN | `registro_compromissos` | Empresa. 422 se a empresa não é FABRICANTE |
| `PATCH /empresas/{id}/credenciamento` | ADMIN | `status`, `validade` | Empresa |
| `POST /vinculos` | ADMIN | `geradora_id`, `fabricante_id` | Vinculo |
| `GET /vinculos` | todos (filtrado pela empresa) | | Lista de Vinculo |
| `PATCH /vinculos/{id}` | ADMIN | `ativo` | Vinculo |
| `GET /auditoria/eventos` | AUDITOR, ADMIN | `?entidade=&entidade_id=&tipo=&veiculo_id=` | Lista de Evento, em ordem de sequência. `veiculo_id` traz os eventos do próprio veículo e os dos registros ligados a ele (etapas, anexos, peças, pesagens, DMR, laudo, certificado e crédito gerado), que levam o `veiculo_id` no payload (L-13) |
| `GET /auditoria/verificar` | AUDITOR, ADMIN | | `integra`, `total`, `primeira_quebra` |
| `GET /configuracao/fatores` | todos | | `{itens: [{tipo, fator, vigente_desde}], total, preco_base}` |

## Fluxo do veículo (backend-fluxo)

Papel: DESMONTADORA e RECICLADORA escrevem nos próprios veículos; AUDITOR e ADMIN leem tudo; FABRICANTE recebe 403 `PAPEL_NAO_PERMITIDO` em todas as rotas desta seção (PM-03 h). Registro de outra empresa responde 404.

Depois do certificado, o que ele atesta não muda: pesagem, peça nova e etapa diferente de `DESTINACAO` devolvem 409 `VEICULO_CERTIFICADO`, e evidência de classificação que mudaria o tipo devolve 409 `TIPO_IMUTAVEL_APOS_CERTIFICADO` (PM-03 f).

| Método e rota | Entrada | Saída e regras |
| --- | --- | --- |
| `POST /veiculos` | `chassi`, `placa`, `renavam`, `data_entrada`, `tipo`, `origem_aquisicao`, `documento_entrada_tipo`, `documento_entrada_numero`, `certidao_baixa_numero`, `peso_entrada_kg`, `sem_viabilidade_desmontagem` | Veiculo. 409 `CHASSI_DUPLICADO`. Todo tipo diferente de `SUCATA_INSERVIVEL` (inclusive `LICENCIADO_RODAGEM`) é rebaixado para `SUCATA_INSERVIVEL` enquanto não houver anexo `EVIDENCIA_CLASSIFICACAO`, com `tipo_declarado` preservado |
| `GET /veiculos` | `?estado=&chassi=` | Lista de Veiculo |
| `GET /veiculos/{id}` | | Veiculo com `etapas`, `anexos`, `pendencias_certificado`, `percentual_aproveitado`, `rebaixado`, `laudo_id` e `certificado_id` (PM-03 a) |
| `POST /veiculos/{id}/anexos` | multipart: `arquivo`, `tipo`, `etapa_tipo` | Anexo. Anexar `EVIDENCIA_CLASSIFICACAO` aplica o `tipo_declarado`. `etapa_tipo` é obrigatório só para `FOTO` (422 `ETAPA_OBRIGATORIA`); nos demais o padrão é `RECEPCAO`. 413 `ARQUIVO_GRANDE_DEMAIS`, 415 `TIPO_DE_ARQUIVO_NAO_PERMITIDO`, 422 `ARQUIVO_VAZIO` (PM-03 c) |
| `GET /anexos/{id}/arquivo` | | Arquivo |
| `PUT /veiculos/{id}/etapas/{tipo}` | `iniciada_em`, `concluida_em?`, `observacoes?` | Etapa |
| `POST /veiculos/{id}/pecas` | `nome`, `descricao`, `classificacao`, `condicao`, `destino` | Peca. Reutilizável recebe `codigo_rastreio` e `etiqueta` (`nome`, `chassi`, `data`, `cnpj`, `codigo`). `condicao` é obrigatória só para peça reutilizável; peça não reutilizável só aceita destino `RECICLAGEM`, `DESCARTE`, `REMANUFATURA` ou `RECONDICIONAMENTO` (422 `DESTINO_INCOMPATIVEL`) (PM-03 d) |
| `PATCH /pecas/{id}` | `destino?`, `descaracterizada?` | Peca. 422 `DESCARACTERIZACAO_IRREVERSIVEL` ao desmarcar |
| `GET /pecas` | `?veiculo_id=&chassi=&nome=&condicao=&destino=&classificacao=` | Lista de Peca. Toda Peca traz `chassi` (PM-WEB-04). `chassi` busca por trecho; `veiculo_id` é exato |
| `GET /pecas/rastreio/{codigo}` | público | `nome`, `chassi`, `data`, `cnpj`, `codigo` e `destino`. Nada além disso: a `condicao` não é pública (PM-WEB-05) |
| `POST /veiculos/{id}/pesagens` | `fracao`, `destino`, `peso_kg` | Pesagem |
| `GET /veiculos/{id}/pesagens` | | `itens`, `total`, `peso_total_kg`, `percentual_aproveitado`, `meta_ano` e `atende_meta` (PM-03 b) |
| `POST /veiculos/{id}/dmrs` | `numero`, `destinatario_nome`, `destinatario_cnpj`, `tipo_material`, `peso_kg` | Dmr com `mtr_numero` simulado. 409 `DMR_DUPLICADA` para número repetido no mesmo veículo (PM-03 g) |
| `GET /veiculos/{id}/dmrs` | | Lista de Dmr |
| `POST /veiculos/{id}/laudo` | `responsavel_nome`, `responsavel_registro` | Laudo. Exige etapas de descontaminação e destruição concluídas: 422 `PENDENCIAS_LAUDO` com `pendencias`. 409 `LAUDO_JA_EMITIDO` (PM-03 e) |
| `GET /veiculos/{id}/laudo` | | Laudo, antes ou depois do certificado. 404 `NAO_ENCONTRADO` se ainda não foi assinado (PM-WEB-03) |
| `POST /veiculos/{id}/certificado` | | Certificado com `credito`. 422 `PENDENCIAS_CERTIFICADO` com `pendencias` (pré-condições 1 a 7). 409 `CERTIFICADO_JA_EMITIDO` se o chassi já tem certificado (pré-condição 8; PM-04) |
| `GET /certificados` | `?empresa_id=` | Lista de Certificado |
| `GET /certificados/{id}` | | Certificado com laudo, veículo e crédito |

## URV e MMV (backend-urv)

Rotas "da empresa" usam a empresa do token. AUDITOR e ADMIN não têm empresa: em `/urv/saldo` e `/portabilidade/exportar` informam `?empresa_id=` (obrigatório, 422 `EMPRESA_OBRIGATORIA`); em `/urv/extrato`, `/urv/creditos`, `/urv/consumos` e `/mmvs` podem informar, e sem ele veem tudo (PM-URV-03 a). Para usuário de empresa, o escopo é sempre a própria empresa: informar `?empresa_id=` de outra empresa nessas rotas responde 404 `NAO_ENCONTRADO`, sem revelar se ela existe.

| Método e rota | Papel | Entrada | Saída e regras |
| --- | --- | --- | --- |
| `POST /mmvs` | FABRICANTE | `codigo`, `ncm`, `nivel`, `percentual_reciclabilidade`, `ja_comercializado` | Mmv com `efeitos_a_partir_de` e `rm`. 409 `MMV_DUPLICADO` (PM-URV-04) |
| `GET /mmvs` | FABRICANTE, AUDITOR, ADMIN | `?empresa_id=` | Lista de Mmv |
| `GET /urv/saldo` | empresa; AUDITOR e ADMIN com `?empresa_id=` | | `empresa_id`, `saldo`, `regularizar_ate?` |
| `GET /urv/extrato` | empresa; AUDITOR e ADMIN | `?empresa_id=&tipo=` | Lista de Lancamento (PM-URV-03 e) |
| `GET /urv/creditos` | empresa; AUDITOR e ADMIN | `?status=&empresa_id=` | Lista de Credito com `certificado` (`id`, `numero`, `tipo_veiculo`, `fator`, `emitido_em`) e `chassi` (PM-WEB-05) |
| `POST /urv/creditos/{id}/transferir` | DESMONTADORA, RECICLADORA | `fabricante_id` | Credito. 409 `CREDITO_JA_TRANSFERIDO`, 422 `SEM_VINCULO`, 422 `FABRICANTE_SEM_REGISTRO_COMPROMISSOS` (PM-URV-04) |
| `POST /urv/consumos/simular` | FABRICANTE | `mmv_id`, `quantidade`, `preco_medio` | `urv_debito`, `saldo_atual`, `saldo_apos`, `saldo_suficiente`, `permitido`, `regularizar_ate?`, `prazo_saldo_negativo` e `memoria_calculo` (`formula`, `qv`, `nivel`, `rm`, `pm`, `pb`, `razao_preco`, `multiplicador`) (PM-URV-03 d, PM-WEB-05) |
| `POST /urv/consumos` | FABRICANTE | `mmv_id`, `periodo`, `preco_medio`, `chassis[]` | Consumo. 409 `SALDO_INSUFICIENTE`, 409 `CHASSI_JA_CONSUMIDO`, 422 `MMV_SEM_EFEITOS` (também para MMV retirado), 422 `CHASSI_REPETIDO_NA_LISTA` (PM-URV-04) |
| `GET /urv/consumos` | FABRICANTE, AUDITOR, ADMIN | `?empresa_id=&chassi=` | Lista de Consumo com `fora_do_prazo` e `chassis`. `chassi` é busca exata, normalizada como no registro (PM-WEB-06) |
| `GET /relatorios/mdic` | AUDITOR, ADMIN | `?ano=` | `registros`, `certificados_emitidos`, `urv_gerada`, `urv_transferida`, `urv_consumida`, `materiais` (peso por fração e destino) |
| `GET /portabilidade/exportar` | empresa; AUDITOR e ADMIN com `?empresa_id=` | | Arquivo JSON versionado com todo o histórico da empresa |
| `POST /portabilidade/importar` | ADMIN | O documento exportado, no corpo, como `application/json`, não multipart (PM-URV-03 b) | `importados` (lista de `{tipo, chave}`), `rejeitados` (lista de `{tipo, chave, motivo, detalhe}`; motivo, por exemplo, `CHASSI_JA_CREDITADO`), `total_importados`, `total_rejeitados`, `saldo_arquivo`, `saldo_local`, `saldo_confere` (PM-URV-03 c). O arquivo inteiro é recusado com 422 `HASH_INVALIDO`, `VERSAO_FORMATO_NAO_SUPORTADA`, `EMPRESA_NAO_CADASTRADA` ou `EMPRESA_TIPO_DIVERGENTE` (PM-URV-04) |

`gerar_credito` (chamado pela emissão do certificado, sem rota própria) levanta 409 `CERTIFICADO_JA_CREDITADO` se o certificado já gerou crédito (PM-URV-04).

## Formatos de resposta (PM-WEB-05)

Os nomes que valem são os dos backends, como saem em `/openapi.json`; o frontend gera os tipos a partir dele (`web/src/api/schema.d.ts`). Campo com `?` pode faltar no JSON; os demais sempre vêm, alguns com `null`.

Suposições do frontend resolvidas a favor do backend: o Anexo traz `nome_original` (não `nome_arquivo`); a memória de cálculo traz `nivel`, `razao_preco` e `multiplicador` (não `fator_preco`), e `saldo_atual` fica na raiz da simulação, não dentro de `memoria_calculo`; o rastreio público não traz `condicao`; o 422 do laudo é `PENDENCIAS_LAUDO`, como o frontend esperava.

| Schema | Campos |
| --- | --- |
| `UsuarioSaida` | `id`, `nome`, `email`, `papel`, `empresa` |
| `LoginSaida` | `access_token`, `token_type`?, `usuario` |
| `EmpresaSaida` | `id`, `cnpj`, `razao_social`, `tipo`, `credenciamento_status`, `credenciamento_validade`, `registro_compromissos`, `criado_em`, `credenciamento_vigente` |
| `EmpresaResumo` | `id`, `cnpj`, `razao_social`, `tipo` |
| `VinculoSaida` | `id`, `geradora_id`, `fabricante_id`, `ativo`, `criado_em`, `geradora`, `fabricante` |
| `EventoSaida` | `id`, `sequencia`, `ocorrido_em`, `usuario_id`, `empresa_id`, `tipo`, `entidade`, `entidade_id`, `payload`, `hash_anterior`, `hash` |
| `VerificacaoSaida` | `integra`, `total`, `primeira_quebra` |
| `FatoresSaida` | `itens`, `total`, `preco_base` |
| `FatorSaida` | `tipo`, `fator`, `vigente_desde` |
| `VeiculoSaida` | `id`, `empresa_id`, `chassi`, `placa`, `renavam`, `data_entrada`, `tipo_declarado`, `tipo`, `origem_aquisicao`, `documento_entrada_tipo`, `documento_entrada_numero`, `certidao_baixa_numero`, `peso_entrada_kg`, `sem_viabilidade_desmontagem`, `estado`, `criado_em`, `rebaixado` |
| `VeiculoDetalhe` | `id`, `empresa_id`, `chassi`, `placa`, `renavam`, `data_entrada`, `tipo_declarado`, `tipo`, `origem_aquisicao`, `documento_entrada_tipo`, `documento_entrada_numero`, `certidao_baixa_numero`, `peso_entrada_kg`, `sem_viabilidade_desmontagem`, `estado`, `criado_em`, `etapas`, `anexos`, `pendencias_certificado`, `percentual_aproveitado`, `laudo_id`, `certificado_id`, `rebaixado` |
| `EtapaSaida` | `id`, `veiculo_id`, `tipo`, `iniciada_em`, `concluida_em`, `observacoes` |
| `AnexoSaida` | `id`, `veiculo_id`, `etapa_tipo`, `tipo`, `sha256`, `nome_original`, `content_type`, `tamanho_bytes`, `enviado_por`, `criado_em` |
| `PecaSaida` | `id`, `veiculo_id`, `chassi`, `nome`, `descricao`, `classificacao`, `codigo_rastreio`, `condicao`, `destino`, `descaracterizada`, `criado_em`, `etiqueta` |
| `Etiqueta` | `nome`, `chassi`, `data`, `cnpj`, `codigo` |
| `RastreioSaida` | `nome`, `chassi`, `data`, `cnpj`, `codigo`, `destino` |
| `PesagemSaida` | `id`, `veiculo_id`, `fracao`, `destino`, `peso_kg`, `criado_em` |
| `PesagensSaida` | `itens`, `total`, `peso_total_kg`, `percentual_aproveitado`, `meta_ano`, `atende_meta` |
| `DmrSaida` | `id`, `veiculo_id`, `numero`, `mtr_numero`, `destinatario_nome`, `destinatario_cnpj`, `tipo_material`, `peso_kg`, `emitida_em` |
| `LaudoSaida` | `id`, `veiculo_id`, `responsavel_nome`, `responsavel_registro`, `assinado_em`, `hash_conteudo`, `assinatura` |
| `AssinaturaSaida` | `algoritmo`, `valor` |
| `CertificadoSaida` | `id`, `numero`, `veiculo_id`, `chassi`, `empresa_id`, `tipo_veiculo`, `fator`, `percentual_aproveitado`, `meta_ano`, `atende_meta`, `emitido_em`, `hash_conteudo`, `credito` |
| `CertificadoDetalhe` | `id`, `numero`, `veiculo_id`, `chassi`, `empresa_id`, `tipo_veiculo`, `fator`, `percentual_aproveitado`, `meta_ano`, `atende_meta`, `emitido_em`, `hash_conteudo`, `credito`, `laudo`, `veiculo` |
| `CreditoResumo` | `id`, `quantidade`, `status`, `geradora_id`, `titular_id` |
| `MmvSaida` | `id`, `fabricante_id`, `codigo`, `ncm`, `nivel`, `percentual_reciclabilidade`, `ja_comercializado`, `efeitos_a_partir_de`, `status`, `criado_em`, `rm` |
| `SaldoSaida` | `empresa_id`, `saldo`, `regularizar_ate`? |
| `LancamentoSaida` | `id`, `empresa_id`, `tipo`, `quantidade`, `credito_id`, `consumo_id`, `contraparte_id`, `contraparte`, `criado_em` |
| `CreditoSaida` | `id`, `certificado_id`, `certificado`, `chassi`, `geradora_id`, `geradora`, `titular_id`, `titular`, `quantidade`, `status`, `criado_em` |
| `CertificadoResumo` | `id`, `numero`, `tipo_veiculo`, `fator`, `emitido_em` |
| `SimulacaoSaida` | `urv_debito`, `saldo_atual`, `saldo_apos`, `saldo_suficiente`, `permitido`, `regularizar_ate`?, `prazo_saldo_negativo`, `memoria_calculo` |
| `MemoriaCalculo` | `formula`, `qv`, `nivel`, `rm`, `pm`, `pb`, `razao_preco`, `multiplicador` |
| `ConsumoSaida` | `id`, `fabricante_id`, `mmv_id`, `mmv_codigo`, `periodo`, `qv`, `rm`, `pm`, `pb`, `urv_debito`, `saldo_apos`, `regularizar_ate`, `prazo_reporte`, `registrado_em`, `fora_do_prazo`, `chassis` |
| `RelatorioMdicSaida` | `ano`, `registros`, `certificados_emitidos`, `urv_gerada`, `urv_transferida`, `urv_consumida`, `materiais`, `peso_total_kg` |
| `MaterialSaida` | `fracao`, `destino`, `peso_kg` |
| `ResultadoImportacao` | `versao_formato`, `empresa_id`, `importados`, `rejeitados`, `total_importados`, `total_rejeitados`, `saldo_arquivo`, `saldo_local`, `saldo_confere` |
| `ItemImportado` | `tipo`, `chave` |
| `ItemRejeitado` | `tipo`, `chave`, `motivo`, `detalhe` |
| `Erro` | `detail`, `codigo`, `pendencias`? |

## Usuários de demonstração (seed)

| E-mail | Papel | Empresa |
| --- | --- | --- |
| `admin@urv.local` | ADMIN | |
| `auditor@mdic.local` | AUDITOR | |
| `operador@desmonte.local` | DESMONTADORA | Desmonte Paraná S.A. (credenciada) |
| `fiscal@montadora.local` | FABRICANTE | Montadora Exemplo S.A. |

Senha de todos: `demo1234`. O seed cria o vínculo entre as duas empresas.
