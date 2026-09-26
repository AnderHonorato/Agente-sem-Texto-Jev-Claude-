---
description: Merge an approved pull request, clean up its worktree and branch, then check whether a release is due.
argument-hint: <pull request number or URL> [worktree name]
---

# Land (finalizar/mesclar)

O que finalizar: $ARGUMENTS

**Verifique primeiro, antes de mudar qualquer coisa.** Este comando precisa de um repositório git,
de um remote, e do `gh` autenticado. Resolva o pull request, o branch por trás dele, e a worktree
que o produziu; quando qualquer um dos três estiver faltando, diga qual e pare. O merge é
condicionado a aprovação — obtenha um sinal verde explícito antes do merge — e este comando nunca
cria tag e nunca faz deploy.

1. **Verifique o head que vai ser mesclado.** Todo check obrigatório verde no head atual, não em um
   push anterior; onde o repositório rodar um check de posse de issue ou de link de fechamento,
   confirme que ele passou nesse mesmo head. Um check pendente, falhando ou desatualizado
   interrompe o workflow, nomeado. O mesmo vale para uma thread de revisão não resolvida (GraphQL
   `reviewThreads`): nomeie-a e pare. Uma correção pertence ao `/build`, antes da aprovação, e uma
   thread de um humano é dele para resolver.
2. **Mescle** com `gh pr merge --squash --delete-branch`, no branch padrão.
3. **Avance o checkout compartilhado (fast-forward)** no seu branch padrão com `git pull --ff-only`.
   Qualquer coisa que não seja um fast-forward significa que o branch divergiu: pare e reporte,
   nunca mescle localmente.
4. **Remova a worktree e seu branch** com `citizen worktree remove <name> --merged`: ele ignora os
   caches regeneráveis que uma execução do gate escreveu, remove o checkout, depois apaga o branch
   assim que tiver lido um pull request mesclado cujo commit de topo é a ponta do branch, a prova
   que substitui a ancestralidade que um squash merge destrói. Nunca force uma remoção. Arquivos
   modificados, não versionados ou outros arquivos ignorados interrompem o workflow com o motivo e
   o caminho, para que o trabalho possa ser lido primeiro, o mesmo vale para uma ponta que a prova
   não contempla. Adicione `--also-clear <name>` para um diretório de nível superior regenerável
   que este repositório escreve e que a lista embutida não cobre.
5. **Audite** com `citizen worktree audit`, e reporte todo checkout desatualizado ou sujo que ele
   nomear junto com o que cada um ainda contém. Deixe-os no lugar; removê-los é decisão do usuário.
6. **Verifique a regra de lançamento.** Leia as próprias instruções de agente do repositório para
   saber quando um lançamento é devido. Ou declare "nenhum lançamento devido" com o motivo que
   essas instruções dão, ou publique um cartão de lançamento — a versão, o que foi finalizado
   desde o último, as superfícies que as instruções exigem — e espere pela aprovação. A aprovação
   pertence ao lançamento, não a este comando.

O passo 4 é onde um branch é apagado, respaldado pela prova de merge. Nunca `git branch -D` no seu
próprio shell, que não tem essa prova, e mantenha remoções fora de comandos compostos: o hook de
avaliação de shell nega um comando composto inteiro quando um segmento é irreversível.

Reporte o commit de merge, o que foi removido, o que a auditoria ainda mostra, e a decisão de
lançamento com a linha nas instruções do repositório de onde ela veio.
