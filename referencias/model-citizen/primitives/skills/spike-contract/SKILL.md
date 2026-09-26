---
name: spike-contract
description: Frame a spike so its result is a decision: the question, the cheapest experiment, a numeric exit criterion, the measured result, the machine it ran on. Use when asked to "spike", "prototype to find out", "de-risk", or "check whether X is feasible", and when writing the spikes section of a plan or README. (Enquadre um spike para que seu resultado seja uma decisão: a pergunta, o experimento mais barato, um critério de saída numérico, o resultado medido, a máquina em que rodou. Use quando pedido para "fazer um spike", "prototipar para descobrir", "reduzir risco", ou "verificar se X é viável", e ao escrever a seção de spikes de um plano ou README.)
---

# O contrato do spike

Um spike responde a uma pergunta com o experimento mais barato que pode respondê-la, e é julgado
contra um número escrito antes do experimento rodar. Tudo mais é um protótipo procurando um
propósito.

## Antes de rodar qualquer coisa, escreva a linha

Cada spike recebe uma entrada, no README de spikes do projeto ou no adendo do plano:

- **Pergunta** — uma frase, respondível sim/não ou com um número. "O núcleo consegue simular 14
  milhões de células a um tick por segundo na máquina alvo?"
- **Experimento mais barato** — a menor coisa que produz o número. Um script descartável, um
  dataset sintético, um stub do caminho real. Nomeie o que é falsificado.
- **Critério de saída** — o número e a comparação. "Abaixo de 800 ms por tick, média de 100
  ticks." Escrito antes da execução, não ajustado depois.
- **Status** — `not started`, `running`, `passed`, `failed`, `inconclusive`, com a data.
- **Máquina** — o hardware e SO em que o orçamento foi medido. Um orçamento medido num laptop não
  se transfere para o CI ou para a máquina alvo sem dizer isso.

## Rode

- Registre o comando exato e a saída bruta, na linha ou num arquivo vinculado.
- Rode vezes suficientes para ver a variância. Relate a média e a dispersão, não a melhor
  execução.
- Se o experimento teve que mudar no meio do caminho, atualize a linha do experimento e diga por
  quê. Se o critério teve que mudar, isso é um spike novo.

## Leia o resultado contra o número

- **Passou** significa que o número medido atendeu ao critério na máquina nomeada. Nada mais é
  "passou".
- **Falhou** é um resultado, não um revés. Escreva o que foi aprendido e qual seria o próximo
  experimento mais barato.
- **Inconclusivo** significa que o experimento não conseguiu produzir o número. Diga o que o
  bloqueou.

Nunca leia um spike contra impressões. "Pareceu rápido" e "parece que funcionou" não são status.

## Ordem e dependência

Rode primeiro o spike que poderia invalidar mais outros trabalhos. Nomeie o fallback se ele
falhar, para que o plano já saiba o que acontece num `failed`.
