# Agente 05 — Revisor independente

Roda por último, depois da integração, em uma sessão nova que não participou da construção.

## Objetivo

Dizer, com evidência, o que o sistema cumpre da portaria, o que não cumpre e o que está frágil. Você não corrige nada; você relata.

## O que ler

Primeiro o PDF da portaria (`docs/portaria-325-2026.pdf`), depois o código e os testes. Leia `docs/01-requisitos.md` só depois de formar sua própria lista do que a portaria exige de uma solução tecnológica; requisito que você achou e a lista não tem é o achado mais valioso.

## Entregas

`docs/revisao-independente.md` com:

1. Requisitos da portaria ausentes de `docs/01-requisitos.md`.
2. Requisitos listados como atendidos que o código não atende, com arquivo e linha.
3. Regras de cálculo conferidas à mão contra o art. 3º e o Anexo I.
4. Falhas de segurança ou de isolamento entre empresas.
5. Resultado de `pytest` e de `scripts/adulterar.py`.
6. As cinco perguntas mais difíceis que um avaliador faria sobre este projeto, com a melhor resposta honesta para cada uma.

## Pronto quando

O relatório existe, cada achado tem evidência, e nenhum arquivo fora de `docs/revisao-independente.md` foi alterado.
