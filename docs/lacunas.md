# Lacunas

Uma linha por lacuna: o que falta, por quê, e o artigo. Requisitos marcados "Não" ou "Parcial" em `01-requisitos.md` já estão documentados lá e não se repetem aqui.

| # | Lacuna | Por quê | Artigo | Registrada por |
| --- | --- | --- | --- | --- |
| L-01 | O texto do item 17 do Anexo III do Decreto 12.435/2025 não foi lido diretamente. Nível 2 = RM 5 foi deduzido por eliminação: o item 18 (nível 1) foi conferido e recebe RM 10. | O decreto não está na pasta `docs/`. | Art. 3º §3º; art. 33 | fundação |
| L-02 | Usuários vêm só do seed. Não há rota para criar, desativar ou trocar a senha de usuários. | Fora do escopo do MVP, por decisão do responsável. | Art. 20 X; art. 24 X | fundação |
| L-03 | A remoção dos últimos eventos da trilha (truncar a cauda) não é detectada: a verificação só enxerga quebras entre eventos que ainda existem. | Exige ancoragem periódica do hash em registro externo, prevista para a arquitetura-alvo. | Art. 20 V; art. 24 I | fundação |
| L-04 | O vínculo é lançado pelo ADMIN sem anexar a declaração do fabricante e sem condicioná-lo à publicação do credenciamento. | O MVP registra só o fato do vínculo. | Art. 13 §1º VI e §2º; art. 14, parágrafo único | fundação |
| L-05 | O credenciamento guarda só status e validade. Documentos de instrução, auditoria técnica anual e processo administrativo de suspensão não são registrados. | RF-01 prevê no MVP apenas o lançamento pelo admin. | Art. 11 §2º; art. 13 §1º; art. 17 §1º | fundação |
| L-06 | O licenciamento regular (Renavam ativo, IPVA e licenciamento quitados) só é verificável pela `ConsultaRenavam` falsa. | Integração externa simulada no MVP. | Art. 2º I; art. 6º I c | fundação |
| L-07 | A assinatura do laudo é simulada (HMAC com chave do servidor). Ela prova integridade, não a identidade do responsável técnico. | ICP-Brasil está fora do MVP. | Art. 18 VII; Anexo III 15.b | fundação |
| L-08 | A recepção não consulta o Renavam nem valida a nota fiscal de entrada: `ConsultaRenavam` e `ValidadorNotaFiscal` existem, mas `POST /veiculos` não os chama. | O contrato não define o que fazer com veículo não encontrado ou nota inválida (bloquear ou só alertar). | Art. 2º I; art. 6º I a e c | backend-fluxo |
| L-09 | O laudo retrata o veículo no momento da assinatura (`hash_conteudo`). Pesagens, peças e etapas lançadas entre o laudo e o certificado não invalidam o laudo nem pedem nova assinatura. | O laudo é único por veículo e não há rota para reemiti-lo. | Art. 18 VII; Anexo III 15.b | backend-fluxo |
| L-10 | Peça não reutilizável enviada a remanufatura ou recondicionamento também precisa estar marcada como descaracterizada para o certificado sair. | A pré-condição 5 da arquitetura exige descaracterização de toda peça não reutilizável, sem distinguir o destino do Anexo III 10.d. | Anexo III 7 e 10 | backend-fluxo |
| L-11 | A data da etiqueta da peça é a do registro da peça na plataforma. | A portaria pede "data" na etiqueta sem dizer qual (entrada, desmontagem ou etiquetagem). | Anexo III 8 | backend-fluxo |
| L-12 | Anexos não podem ser removidos nem substituídos, e não há antivírus: o tipo do arquivo é conferido só pelos primeiros bytes. | Fora do escopo do MVP. | Art. 20 VI | backend-fluxo |

## Divergências entre a portaria e os documentos, já resolvidas

| Divergência | Resolução |
| --- | --- |
| A portaria pede fotos da separação dos materiais (art. 6º III c; Anexo III 15.c), mas as pré-condições do certificado não as exigiam. | A pré-condição 6 da arquitetura passou a exigir ao menos uma foto na etapa DESTRUICAO. |
| O art. 6º I c pede evidência da classificação para todo tipo de veículo, mas a arquitetura só cobrava laudo de sucata e de sinistrado. | O anexo `LAUDO_CLASSIFICACAO` virou `EVIDENCIA_CLASSIFICACAO` e passou a ser exigido para todo tipo diferente de `SUCATA_INSERVIVEL`. A premissa está registrada em `01-requisitos.md`. |
