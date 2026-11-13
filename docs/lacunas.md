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

## Divergências entre a portaria e os documentos, já resolvidas

| Divergência | Resolução |
| --- | --- |
| A portaria pede fotos da separação dos materiais (art. 6º III c; Anexo III 15.c), mas as pré-condições do certificado não as exigiam. | A pré-condição 6 da arquitetura passou a exigir ao menos uma foto na etapa DESTRUICAO. |
| O art. 6º I c pede evidência da classificação para todo tipo de veículo, mas a arquitetura só cobrava laudo de sucata e de sinistrado. | O anexo `LAUDO_CLASSIFICACAO` virou `EVIDENCIA_CLASSIFICACAO` e passou a ser exigido para todo tipo diferente de `SUCATA_INSERVIVEL`. A premissa está registrada em `01-requisitos.md`. |
