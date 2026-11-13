# Contrato da API

Base: `/api/v1`. JSON em snake_case. Autenticação por `Authorization: Bearer <token>`, exceto login e consulta pública de etiqueta. O OpenAPI gerado pelo FastAPI em `/openapi.json` deve refletir este documento; o frontend gera os tipos a partir dele.

Erros seguem `{ "detail": "mensagem", "codigo": "CODIGO_ESTAVEL", "pendencias": ["..."] }`. `pendencias` só aparece em 422 de pré-condição.

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
| `GET /auditoria/eventos` | AUDITOR, ADMIN | `?entidade=&entidade_id=&tipo=` | Lista de Evento |
| `GET /auditoria/verificar` | AUDITOR, ADMIN | | `integra`, `total`, `primeira_quebra` |
| `GET /configuracao/fatores` | todos | | `{itens: [{tipo, fator, vigente_desde}], total, preco_base}` |

## Fluxo do veículo (backend-fluxo)

Papel: DESMONTADORA e RECICLADORA escrevem nos próprios veículos; AUDITOR e ADMIN leem tudo.

| Método e rota | Entrada | Saída e regras |
| --- | --- | --- |
| `POST /veiculos` | `chassi`, `placa`, `renavam`, `data_entrada`, `tipo`, `origem_aquisicao`, `documento_entrada_tipo`, `documento_entrada_numero`, `certidao_baixa_numero`, `peso_entrada_kg`, `sem_viabilidade_desmontagem` | Veiculo. 409 `CHASSI_DUPLICADO`. Todo tipo diferente de `SUCATA_INSERVIVEL` (inclusive `LICENCIADO_RODAGEM`) é rebaixado para `SUCATA_INSERVIVEL` enquanto não houver anexo `EVIDENCIA_CLASSIFICACAO`, com `tipo_declarado` preservado |
| `GET /veiculos` | `?estado=&chassi=` | Lista de Veiculo |
| `GET /veiculos/{id}` | | Veiculo com `etapas`, `anexos`, `pendencias_certificado`, `percentual_aproveitado` |
| `POST /veiculos/{id}/anexos` | multipart: `arquivo`, `tipo`, `etapa_tipo` | Anexo. Anexar `EVIDENCIA_CLASSIFICACAO` aplica o `tipo_declarado` |
| `GET /anexos/{id}/arquivo` | | Arquivo |
| `PUT /veiculos/{id}/etapas/{tipo}` | `iniciada_em`, `concluida_em?`, `observacoes?` | Etapa |
| `POST /veiculos/{id}/pecas` | `nome`, `descricao`, `classificacao`, `condicao`, `destino` | Peca. Reutilizável recebe `codigo_rastreio` e `etiqueta` (`nome`, `chassi`, `data`, `cnpj`, `codigo`) |
| `PATCH /pecas/{id}` | `destino?`, `descaracterizada?` | Peca |
| `GET /pecas` | `?chassi=&nome=&condicao=&destino=&classificacao=` | Lista de Peca |
| `GET /pecas/rastreio/{codigo}` | público | Dados da etiqueta e destino atual |
| `POST /veiculos/{id}/pesagens` | `fracao`, `destino`, `peso_kg` | Pesagem |
| `GET /veiculos/{id}/pesagens` | | Lista e `percentual_aproveitado` |
| `POST /veiculos/{id}/dmrs` | `numero`, `destinatario_nome`, `destinatario_cnpj`, `tipo_material`, `peso_kg` | Dmr com `mtr_numero` simulado |
| `GET /veiculos/{id}/dmrs` | | Lista de Dmr |
| `POST /veiculos/{id}/laudo` | `responsavel_nome`, `responsavel_registro` | Laudo. Exige etapas de descontaminação e destruição concluídas |
| `POST /veiculos/{id}/certificado` | | Certificado com `credito`. 422 `PENDENCIAS_CERTIFICADO` com `pendencias` |
| `GET /certificados` | `?empresa_id=` | Lista de Certificado |
| `GET /certificados/{id}` | | Certificado com laudo, veículo e crédito |

## URV e MMV (backend-urv)

| Método e rota | Papel | Entrada | Saída e regras |
| --- | --- | --- | --- |
| `POST /mmvs` | FABRICANTE | `codigo`, `ncm`, `nivel`, `percentual_reciclabilidade`, `ja_comercializado` | Mmv com `efeitos_a_partir_de` e `rm` |
| `GET /mmvs` | FABRICANTE, AUDITOR, ADMIN | | Lista de Mmv |
| `GET /urv/saldo` | empresa | | `saldo`, `regularizar_ate?` |
| `GET /urv/extrato` | empresa; AUDITOR com `?empresa_id=` | | Lista de Lancamento |
| `GET /urv/creditos` | empresa | `?status=` | Lista de Credito com certificado e chassi |
| `POST /urv/creditos/{id}/transferir` | DESMONTADORA, RECICLADORA | `fabricante_id` | Credito. 409 `CREDITO_JA_TRANSFERIDO`, 422 `SEM_VINCULO` |
| `POST /urv/consumos/simular` | FABRICANTE | `mmv_id`, `quantidade`, `preco_medio` | `urv_debito`, `saldo_apos`, memória de cálculo |
| `POST /urv/consumos` | FABRICANTE | `mmv_id`, `periodo`, `preco_medio`, `chassis[]` | Consumo. 409 `SALDO_INSUFICIENTE`, 409 `CHASSI_JA_CONSUMIDO`, 422 `MMV_SEM_EFEITOS` |
| `GET /urv/consumos` | FABRICANTE, AUDITOR, ADMIN | | Lista de Consumo com `fora_do_prazo` |
| `GET /relatorios/mdic` | AUDITOR, ADMIN | `?ano=` | `registros`, `certificados_emitidos`, `urv_gerada`, `urv_transferida`, `urv_consumida`, `materiais` (peso por fração e destino) |
| `GET /portabilidade/exportar` | empresa | | Arquivo JSON versionado com todo o histórico da empresa |
| `POST /portabilidade/importar` | ADMIN | Arquivo JSON | `importados`, `rejeitados` com motivo (por exemplo `CHASSI_JA_CREDITADO`) |

## Usuários de demonstração (seed)

| E-mail | Papel | Empresa |
| --- | --- | --- |
| `admin@urv.local` | ADMIN | |
| `auditor@mdic.local` | AUDITOR | |
| `operador@desmonte.local` | DESMONTADORA | Desmonte Paraná S.A. (credenciada) |
| `fiscal@montadora.local` | FABRICANTE | Montadora Exemplo S.A. |

Senha de todos: `demo1234`. O seed cria o vínculo entre as duas empresas.
