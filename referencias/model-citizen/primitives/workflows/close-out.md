---
description: Close a finished session: sweep for unfinished work, ask once, land, file the follow-ups, hand off, tell the sessions that depend on this one, then archive.
argument-hint: [what is finishing, and "archive" if it should archive without asking again]
---

# Close out

O que está terminando: {{arguments}}

**Varra antes de mudar qualquer coisa.** Um close-out que abre com uma mesclagem já pulou a
pergunta que existe para fazer. Fora de um repositório, os passos 3 e 5 não se aplicam; diga isso.

1. **Nomeie o que ainda está em aberto.** Arquivos não commitados e não rastreados em todo
   checkout que esta sessão tocou, `citizen worktree audit`, os pull requests que esta sessão
   abriu e o estado de seus checks, trabalho de fundo ainda rodando, e as decisões que você
   estacionou para o usuário. Relate essa lista primeiro; uma varredura vazia é um resultado,
   então diga isso e siga em frente.
2. **Agrupe os follow-ups, depois pergunte uma vez.** Uma linha cada, título e por quê, para o
   que esta sessão encontrou e não fez; nunca conserte um silenciosamente aqui em vez disso. Peça
   por um sinal verde explícito nomeando-os, os pull requests que o passo 3 mesclaria, e qualquer
   coisa que o passo 4 abriria e depois mesclaria. Aja apenas sobre o que ele aprovar.
3. **Finalize o que está pronto** com o workflow `land`, nunca colocando seus passos inline: a
   prova de mesclagem e suas recusas são o ponto dele. O sinal verde do passo 2 é o que ele pede.
   Qualquer coisa não verde, não aprovada, ou não sua para mesclar fica em aberto e vai no
   relatório.
4. **Registre os follow-ups aprovados**; o sinal verde do passo 2 cobre registrá-los e finalizar
   o que eles escrevem. Quando o registro escreve arquivos rastreados, como um mapa de issues ou
   um arquivo de história, rode-o numa worktree nova a partir do branch padrão atualizado, coloque
   o que ele escreveu em seu próprio pull request sob as regras de pull request do repositório, e
   finalize isso com o workflow `land` uma vez que os checks passem.
5. **Faça o handoff** com o workflow `handoff`, e apenas quando o trabalho neste repositório
   continua além desta sessão. Um trabalho terminado não precisa de arquivo de progresso.
6. **Avise as sessões que dependem desta**, onde o cliente pode listá-las e enviar mensagem a
   elas: um branch que uma esperava, um arquivo que uma mantém aberto, uma conclusão que reverte
   sua premissa. Compartilhar um grupo ou um repositório não é uma dependência; onde o cliente não
   pode, use o handoff.
7. **Arquive, ou pare.** Arquive quando a invocação já pediu por isso, desde que todo pull request
   que o passo 4 abriu tenha sido mesclado; caso contrário termine na checklist e espere. Nunca dê
   clear ou compact antes: arquivar encerra a sessão, então ambos só queimam o contexto que você
   ainda precisa. Dar clear pertence a continuar na mesma sessão, o oposto deste workflow.

Registre o close-out antes da chamada de arquivamento, que encerra o turno, e relate o que foi
finalizado, o que você registrou, a quem você avisou, e o que você está deixando em aberto.
