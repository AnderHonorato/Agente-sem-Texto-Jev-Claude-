---
description: Close a finished session: sweep for unfinished work, ask once, land, file the follow-ups, hand off, tell the sessions that depend on this one, then archive.
argument-hint: [what is finishing, and "archive" if it should archive without asking again]
---

# Close out (encerramento)

O que está terminando: $ARGUMENTS

**Faça a varredura antes de mudar qualquer coisa.** Um encerramento que começa com um merge já
pulou a pergunta que existe para ser feita. Fora de um repositório, os passos 3 e 5 não se
aplicam; diga isso.

1. **Nomeie o que ainda está aberto.** Arquivos não commitados e não versionados em todo checkout
   que esta sessão tocou, `citizen worktree audit`, os pull requests que esta sessão abriu e o
   estado de seus checks, trabalho em segundo plano ainda em execução, e as decisões que você
   deixou pendentes para o usuário. Reporte essa lista primeiro; uma varredura vazia é um
   resultado, então diga isso e siga em frente.
2. **Agrupe os follow-ups, depois pergunte uma vez.** Uma linha cada, título e porquê, para o que
   esta sessão encontrou e não fez; nunca corrija um silenciosamente aqui em vez disso. Peça um
   sinal verde explícito nomeando-os, os pull requests que o passo 3 mesclaria, e qualquer um que
   o passo 4 abriria e depois mesclaria. Aja somente sobre o que for aprovado.
3. **Finalize o que está pronto** com o workflow `land`, nunca colocando os passos dele inline: a
   prova de merge e suas recusas são o propósito dele. O sinal verde do passo 2 é o que ele pede.
   Qualquer coisa que não esteja verde, não aprovada, ou que não seja sua para mesclar permanece
   aberta e vai para o relatório.
4. **Registre os follow-ups aprovados**; o sinal verde do passo 2 cobre registrá-los e finalizar o
   que eles escrevem. Quando o registro escreve arquivos versionados, como um mapa de issues ou um
   arquivo de história, rode isso em uma nova worktree a partir do branch padrão atualizado, coloque
   o que foi escrito em seu próprio pull request sob as regras de pull request do repositório, e
   finalize isso com o workflow `land` assim que os checks passarem.
5. **Faça o handoff (repasse)** com o workflow `handoff`, e somente quando o trabalho neste
   repositório continuar além desta sessão. Um trabalho finalizado não precisa de arquivo de
   progresso.
6. **Avise as sessões que dependem desta**, onde o cliente puder listá-las e enviar mensagens a
   elas: um branch que uma estava esperando, um arquivo que uma mantém aberto, uma conclusão que
   reverte sua premissa. Compartilhar um grupo ou um repositório não é uma dependência; onde o
   cliente não puder, use o handoff.
7. **Arquive, ou pare.** Arquive quando a invocação já pediu isso, desde que todo pull request que
   o passo 4 abriu tenha sido mesclado; caso contrário, termine na checklist e espere. Nunca limpe
   ou compacte antes: arquivar encerra a sessão, então ambos só consomem o contexto que você ainda
   precisa. Limpar pertence a continuar na mesma sessão, o oposto deste workflow.

Registre o encerramento antes da chamada de arquivamento, que encerra o turno, e reporte o que foi
finalizado, o que você registrou, a quem você avisou, e o que você está deixando aberto.
