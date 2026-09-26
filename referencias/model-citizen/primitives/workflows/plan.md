---
description: Turn a topic or issue into a plan the reviewer approves in the native plan pane. (Transforma um tópico ou issue num plano que o revisor aprova no painel de plano nativo.)
argument-hint: <topic or issue number>
---

# Plan

O que planejar: {{arguments}}

1. **Invoque a skill `plan-authoring` e leia-a por completo.** Nunca escreva o card de memória do
   seu contrato; um hook valida o arquivo que você escreve.
2. **Delegue a leitura ampla antes do modo de plano.** `citizen role run planner` escreve um
   artefato e o modo de plano não permite nenhuma escrita além do seu próprio arquivo de plano,
   então rode-o aqui quando a delegação compensa — runtime ativo, modelo de sessão explícito,
   arquivo de briefing, `--artifact <new-plan.md>`.
3. **Pergunte antes de entrar no modo de plano**, em uma linha nomeando o tópico — entrar nele é
   decisão do usuário. Sem modo de plano, ou o usuário o recusa, e o passo 8 é o comando inteiro.
4. **Colete dentro do modo de plano.** Leia a issue se lhe deram um número e leia o código que o
   plano vai tocar; pesquisa extensa vai para o scratchpad, nunca ao lado do arquivo de plano.
   Pergunte ao usuário apenas o que você não consegue encontrar sozinho, e agrupe toda pergunta
   numa única mensagem.
5. **Escreva o Review Card no arquivo de plano que o modo de plano designou.** O runtime nomeia
   esse arquivo e você não pode renomeá-lo enquanto planeja. O card é a primeira tela do arquivo e
   tudo mais vive abaixo dele, sob `# Addendum`.
6. **Poste a mensagem de revisão na forma da skill, depois chame `ExitPlanMode`.** Deixe de fora
   sua linha de fechamento de build: a aprovação nativa é o gate, então nunca peça por uma resposta
   digitada também.
7. **Uma vez aprovado, nomeie o plano e entregue-o.** Renomeie o arquivo para um slug de tópico no
   mesmo diretório, nunca sobre um nome existente — use `-2` e diga isso — e termine invocando
   `/build <caminho absoluto>`. O builder o commita, então ele chega ao pull request.
8. **Sem modo de plano:** escreva o plano sob `.agent-harness/plans/` — raiz do repositório, ou o
   diretório atual quando não há repositório — nomeado pelo tópico, abra-o para o revisor com um
   caminho absoluto, e termine na linha de build da skill.

Este comando não precisa de repositório nem de código. Não implemente nada; não crie branch nem
worktree, o que acontece no build. Se o usuário voltar com mudanças, revise o arquivo, atualize
sua linha **Changed this round**, diga no chat apenas o que mudou, e chame `ExitPlanMode` de novo.
