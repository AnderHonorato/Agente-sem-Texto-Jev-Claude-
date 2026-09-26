---
name: design-loop
description: Raise the visual quality of something that already renders: build, screenshot, independent scored critique, fix, against rubrics with hard accessibility, design-token, runtime and asset-licensing gates. Use when asked to make a UI, page, HTML doc, dashboard, game scene or 3D asset look dramatically better, more polished or more professional; to improve the visual design, look, styling or visual quality of a surface; to iterate toward a reference, mockup or screenshot; and proactively after building or substantially changing a user-facing surface. Not for deciding what screens exist or how flows behave. (Eleve a qualidade visual de algo que já renderiza: construir, tirar screenshot, crítica pontuada independente, corrigir, contra rubricas com gates obrigatórios de acessibilidade, tokens de design, runtime e licenciamento de assets. Use quando pedido para fazer uma UI, página, doc HTML, dashboard, cena de jogo ou asset 3D parecer dramaticamente melhor, mais polido ou mais profissional; para melhorar o design visual, aparência, estilização ou qualidade visual de uma superfície; para iterar em direção a uma referência, maquete ou screenshot; e proativamente depois de construir ou mudar substancialmente uma superfície voltada ao usuário. Não serve para decidir quais telas existem ou como os fluxos se comportam.)
---

# Design loop

Um loop fechado que eleva a qualidade visual por medição em vez de gosto pessoal. O agente que
construiu a coisa não pode avaliá-la, então um **juiz independente com contexto limpo** pontua cada
rodada contra um **alvo travado** até que ela supere a barra ou estagne.

Derivado de [dream-loop](https://github.com/achimala/dream-loop) (MIT) — veja `ATTRIBUTION.md`.

**Duas regras permanentes que se aplicam mesmo fora do loop.** Trabalho visual é verificado por uma
captura que o agente lê antes de qualquer coisa ser mostrada ao usuário; uma alegação sobre como
algo parece sem uma captura por trás não é verificada. E o visual é projetado em loops baratos —
uma maquete, um esboço, um render descartável — antes de ser incorporado ao pipeline real.
A mecânica do loop é a contribuição dele. As rubricas, os gates obrigatórios, o escalonamento e a
política de assets aqui são nossos e diferem deliberadamente; não reintroduza o capítulo de
obtenção de assets dele.

## Quando esta é a skill errada

Esta skill **refina algo que já renderiza**. Ela precisa de um artefato rodando para tirar
screenshot. Ela não decide quais telas existem, quais são os fluxos, ou como qualquer coisa se
comporta.

| Se o pedido é | Use |
| --- | --- |
| Quais telas existem, quais são os fluxos, como se comporta | o workflow de especificação de UX do seu framework de planejamento |
| Uma maquete, wireframe ou design de tela do zero | `design` — canvas, sem necessidade de artefato rodando |
| Estilizar uma página de Artifact publicada | `artifact-design` |
| Fazer a coisa que existe parecer muito melhor | **esta skill** |

Uma especificação de UX produz o briefing. Isto produz o acabamento. Se uma superfície foi
especificada mas não construída, construa-a primeiro — não há nada para capturar até então.

## Escolha um modo primeiro

| Modo | Superfície | Rubrica |
| --- | --- | --- |
| **ui** | App web, app iOS/Mac, landing page, doc HTML autônomo, dashboard | [references/rubric-ui.md](references/rubric-ui.md) |
| **scene** | Cena 3D, visão de jogo, asset renderizado, saída do Blender | [references/rubric-scene.md](references/rubric-scene.md) |

Leia apenas a rubrica do seu modo. Se o pedido abrange os dois, rode dois loops com alvos
separados — nunca faça a média de uma rubrica entre os dois.

## O loop

Pré-requisitos: um alvo travado e um comando de captura funcionando. Obtenha os dois antes da
rodada 1.

1. **Estabeleça e trave o alvo** — [references/targets.md](references/targets.md). Escreva-o em
   `.design-loop/target.<ext>` e não o regenere no meio do loop.
2. **Estabeleça o comando de captura** — [references/capture.md](references/capture.md). Verifique
   que ele produz um screenshot real antes de começar, não depois.
3. **Implemente uma passada** no alvo. Quando a sessão roda abaixo da classe mais forte, passe os
   passos 3 a 5 e 7 para o agente `designer`, que declara essa classe; dê a ele o workspace, o
   alvo, o comando de captura e o último veredito. Ele nunca julga; o passo 6 continua seu.
4. **Valide você mesmo.** Precisa realmente rodar, carregar e funcionar. Corrija quebras,
   orientação errada, assets faltando e falhas de carregamento aqui. Não use este passo para
   ajustar visuais.
5. **Capture** o estado atual em `.design-loop/round-<n>.png`.
6. **Julgue** — gere o agente `design-judge` com os caminhos de imagem, o tipo de superfície e o
   caminho do alvo, conforme [references/judge.md](references/judge.md). Nunca julgue seu próprio
   trabalho inline.
7. **Resolva cada lacuna** que o juiz nomeou, as mais difíceis primeiro. Não escolha só as fáceis.
8. **Avalie os critérios de saída** abaixo. Saia, escalone, ou volte ao passo 4.

## Gates obrigatórios

Cada rubrica define gates que são **pass/fail, não pontuados**. Um gate falho bloqueia a saída em
qualquer pontuação. Acessibilidade, aderência a tokens de design, orçamento de runtime e
licenciamento de assets são gates precisamente porque um loop otimizando para "parece bom" vai
trocá-los de outra forma.

Nunca abaixe um gate para sair do loop. Relate-o como não cumprido em vez disso.

## Critérios de saída

- **Pontuação ≥ 8/10 e todos os gates passam** — pronto. Mostre a captura mais recente, declare a
  pontuação e as lacunas conhecidas restantes, e pergunte se deve continuar.
- **Pontuação ≥ 8/10 mas um gate falha** — corrija o gate. Rejulgue depois para confirmar que a
  correção não custou qualidade visual. Uma correção de gate que regride a pontuação não está
  terminada.
- **Estagnação se aproximando** — a melhor pontuação não melhorou um ponto inteiro em 2 rodadas,
  *ou* o juiz nomeou a mesma lacuna duas vezes seguidas. Pare de fazer ajustes incrementais. Dê um
  passo atrás e encontre a razão estrutural: sistema de layout errado, paleta errada, câmera
  errada, qualidade de asset errada, escala de tipografia errada. Faça uma mudança dramática, não
  cinco pequenas.
- **Estagnado** — a mudança dramática não moveu a pontuação. Pare. Não gaste tokens numa segunda
  aposta arquitetural. Escalone.
- **Orçamento de rodadas gasto** — o teto padrão é **5 rodadas**. Isso é um teto, não uma meta.
  Escalone.
- **Caso contrário** — continue no loop. Não saia cedo porque o progresso parece adequado.

## Escalonamento

Siga a regra permanente de loop autônomo: interrompa apenas para achados bloqueantes, para
decisões de produto, UX, segurança ou schema fora do briefing, ou para qualquer coisa destrutiva.
Tudo mais vai para uma lista corrente de **Decisões necessárias** enquanto o loop continua se
movendo.

Decisões de design ambíguas não são interrupções. Implemente o padrão sensato, continue, e
destaque-o no final para confirmação ou substituição.

Quando você parar, relate: a pontuação atual com a divisão por eixo, o status dos gates, o que
você mudou, o que ainda está em aberto, e a pergunta específica que precisa de resposta.

## Assets

**A obtenção é governada inteiramente pela postura `licensing` escolhida**, mais qualquer regra
de asset com escopo de caminho que o projeto carregue. Invoque a skill `licensing-review` antes de
incorporar qualquer coisa nova.

Três coisas que este loop nunca deve fazer, não importa quanto melhorariam a pontuação:

- **Nunca baixe assets sem liberar a licença primeiro.** "Download grátis", "royalty-free" e uma
  tag de marketplace não são prova.
- **Nunca sobrescreva uma restrição que o usuário definiu.** Se ele disse para não baixar assets,
  isso inclui serviços de geração 3D, APIs de imagem-para-3D e marketplaces de assets. Pergunte;
  não reinterprete.
- **Nunca entregue assets 3D gerados em termos não resolvidos.** A saída de imagem-para-3D carrega
  os termos do fornecedor, não uma licença limpa. Material não resolvido fica fora da produção.

Se nenhum asset compatível supera a barra, adapte uma base compatível ou crie geometria original.
Diga isso claramente em vez de silenciosamente substituir por algo mais fraco.

## Arquivos de trabalho

Mantenha tudo em `.design-loop/` na raiz do repositório:

```
.design-loop/
  target.png          referência travada, escrita uma vez
  round-1.png         captura por rodada
  verdict-1.md        saída do juiz por rodada
  notes.md            decisões necessárias, suposições, status dos gates
```

Adicione `.design-loop/` a `~/.config/git/ignore` uma vez para que fique fora de todo repositório.

## Orçamento de tempo

Se recebido um, registre o relógio depois que o alvo estiver travado e verifique entre as rodadas.
**Não troque qualidade visual pelo prazo** — atingir o limite com progresso real e bonito supera
entregar completo e feio. Relate o que você faria com mais uma rodada.

Se nenhum orçamento for dado, rode até um critério de saída e avise antecipadamente que isso
consome tokens reais: cada rodada é uma passada de construção, uma captura e um subagente juiz.
