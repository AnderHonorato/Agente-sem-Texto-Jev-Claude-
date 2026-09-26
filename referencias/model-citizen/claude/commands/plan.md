---
description: Turn a topic or issue into a plan the reviewer approves in the native plan pane.
argument-hint: <topic or issue number>
---

# Plan (planejar)

O que planejar: $ARGUMENTS

1. **Invoque a skill `plan-authoring` e leia-a por completo.** Nunca escreva o cartão de memória
   sobre o seu contrato; um hook valida o arquivo que você escreve.
2. **Delegue a leitura ampla antes do modo de planejamento.** `citizen role run planner` escreve
   um artefato e o modo de planejamento não permite nenhuma escrita além do seu próprio arquivo de
   plano, então rode isso aqui quando a delegação compensar — runtime ativo, modelo de sessão
   explícito, arquivo de brief, `--artifact <new-plan.md>`.
3. **Pergunte antes de entrar no modo de planejamento**, em uma linha nomeando o tópico — entrar
   nesse modo é decisão do usuário. Sem modo de planejamento, ou se o usuário recusar, o passo 8 é
   o comando inteiro.
4. **Colete dentro do modo de planejamento.** Leia a issue se lhe foi dado um número e leia o
   código que o plano vai tocar; pesquisa longa vai para o scratchpad, nunca ao lado do arquivo do
   plano. Pergunte ao usuário somente o que você não conseguir encontrar sozinho, e agrupe toda
   pergunta em uma única mensagem.
5. **Escreva o Review Card no arquivo de plano que o modo de planejamento designou.** O runtime
   nomeia esse arquivo e você não pode renomeá-lo enquanto planeja. O cartão é a primeira tela do
   arquivo e tudo mais vive abaixo dele, sob `# Addendum`.
6. **Poste a mensagem de revisão no formato da skill, depois chame `ExitPlanMode`.** Deixe de fora
   a linha de fechamento de build dela: a aprovação nativa é o portão, então nunca peça também uma
   resposta digitada.
7. **Uma vez aprovado, nomeie o plano e o entregue.** Renomeie o arquivo para um slug do tópico no
   mesmo diretório, nunca sobre um nome já existente — use `-2` e diga isso — e termine invocando
   `/build <caminho absoluto>`. O builder o commita, para que chegue ao pull request.
8. **Sem modo de planejamento:** escreva o plano sob `.agent-harness/plans/` — raiz do repositório,
   ou o diretório atual quando não houver repositório — nomeado pelo tópico, abra-o para o revisor
   com um caminho absoluto, e termine na linha de build da skill.

Este comando não precisa de repositório nem de código. Não implemente nada; não crie branch nem
worktree, isso acontece no build. Se o usuário voltar com mudanças, revise o arquivo, atualize sua
linha **Changed this round**, diga no chat somente o que mudou, e chame `ExitPlanMode` de novo.
