---
description: Merge an approved pull request, clean up its worktree and branch, then check whether a release is due. (Mescla um pull request aprovado, limpa sua worktree e branch, depois verifica se um release é devido.)
argument-hint: <pull request number or URL> [worktree name]
---

# Land

O que finalizar: {{arguments}}

**Verifique primeiro, antes de mudar qualquer coisa.** Este comando precisa de um repositório
git, um remote, e o `gh` autenticado. Resolva o pull request, o branch por trás dele, e a
worktree que o produziu; quando algum dos três está faltando, diga qual e pare. Mesclar tem gate
de aprovação — obtenha um sinal verde explícito antes da mesclagem — e este comando nunca cria
tag e nunca faz deploy.

1. **Verifique a ponta que vai mesclar.** Todo check obrigatório verde na ponta atual, não numa
   push anterior; onde o repositório roda um check de posse de issue ou de link de fechamento,
   confirme que ele passou nessa mesma ponta. Um check pendente, falho ou obsoleto para o
   workflow, nomeado. O mesmo vale para uma thread de revisão não resolvida (GraphQL
   `reviewThreads`): nomeie-a e pare. Uma correção pertence ao `/build`, antes da aprovação, e uma
   thread de um humano é dele para resolver.
2. **Mescle-o** com `gh pr merge --squash --delete-branch`, no branch padrão.
3. **Faça fast-forward do checkout compartilhado** no seu branch padrão com `git pull --ff-only`.
   Qualquer coisa além de um fast-forward significa que o branch divergiu: pare e relate isso,
   nunca mescle localmente.
4. **Remova a worktree e seu branch** com `citizen worktree remove <name> --merged`: ele ignora
   os caches regeneráveis que uma execução de gate escreveu, remove o checkout, depois apaga o
   branch uma vez que leu um pull request mesclado cujo commit de topo é a ponta do branch, a
   prova que substitui a ancestralidade que uma mesclagem squash destrói. Nunca force uma
   remoção. Arquivos modificados, não rastreados ou outros ignorados param o workflow com a razão
   e o caminho, para que o trabalho possa ser lido primeiro, e o mesmo vale para uma ponta que
   essa prova não contempla. Adicione `--also-clear <name>` para um diretório de nível superior
   regenerável que este repositório escreve e que a lista embutida não cobre.
5. **Audite** com `citizen worktree audit`, e relate todo checkout obsoleto ou sujo que ele nomeia
   junto com o que cada um ainda guarda. Deixe-os no lugar; removê-los é decisão do usuário.
6. **Verifique a regra de release.** Leia as próprias instruções de agente do repositório para
   quando um release é devido. Ou declare "nenhum release devido" com a razão que aquelas
   instruções dão, ou poste um cartão de release — a versão, o que foi finalizado desde o último,
   as superfícies que as instruções exigem — e espere aprovação. A aprovação pertence ao release,
   não a este comando.

O passo 4 é onde um branch é apagado, atrás da prova de mesclagem. Nunca `git branch -D` no seu
próprio shell, que não tem tal prova, e mantenha exclusões fora de comandos compostos: o hook de
avaliação de shell nega um comando composto inteiro quando um segmento é irreversível.

Relate o commit de mesclagem, o que foi removido, o que a auditoria ainda mostra, e a decisão de
release com a linha das instruções do repositório de onde ela veio.
