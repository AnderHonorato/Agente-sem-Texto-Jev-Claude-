# O juiz

## Por que é um agente separado

O agente que construiu a coisa já decidiu que ela é boa — escolheu cada valor nela. Ele também
carrega toda a conversa de construção, então pontua o próprio raciocínio em vez dos pixels. Um juiz
com **nenhum contexto de construção** vê apenas as duas imagens.

Gere o agente **`design-judge`** com os caminhos de imagem, o tipo de superfície e o caminho do
alvo — um novo a cada rodada; nunca dê fork nele nem reutilize o juiz anterior.

## O que passar a ele

Caminhos absolutos, todos eles, toda rodada:

- O alvo travado
- A captura atual
- **A captura e o veredito da rodada anterior**, se houver

O handoff do veredito anterior é o que torna as regressões visíveis. Sem ele o juiz não consegue
distinguir melhoria de deriva, e as pontuações vagam.

Nomeie o modo — `ui` ou `scene` — e o agente lê sua própria rubrica. Não diga a ele o que você
mudou, o que você pretendia, ou o que achou difícil. Isso é o contexto que você está pagando para
manter de fora.

## Lidando com o veredito

Escreva-o em `.design-loop/verdict-<n>.md` literalmente. Você precisa do histórico para detectar
estagnação.

**Resolva cada lacuna, as mais difíceis primeiro.** Escolher só as fáceis é como um loop estagna em
6/10: a lacuna cara sobrevive a toda rodada e o juiz continua a nomeando.

O juiz pode estar errado. Se uma lacuna contradiz um gate obrigatório, o sistema de design ou a
escala do mundo real, **o gate vence** — anote a discordância em `notes.md` e siga em frente. Não
discuta com o juiz rodando-o de novo no mesmo estado esperando um número melhor.

## Retransmitindo ao usuário

A saída do juiz é a prosa crua de um subagente e não segue o estilo de saída da casa. **Nunca a
cole diretamente.** Reformate antes que chegue ao usuário: pontuação e veredito primeiro, falhas
de gate em seguida, depois o que você mudou e o que ainda está em aberto.
