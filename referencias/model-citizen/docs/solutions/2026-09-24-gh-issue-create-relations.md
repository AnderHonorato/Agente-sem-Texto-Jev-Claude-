# gh issue create aplica relações depois que a issue já existe

- 2026-09-24: `gh issue create --parent`, `--blocked-by` e `--type` criam a issue primeiro e aplicam
  essas relações depois; quando essa segunda etapa falha, o gh sai com código não-zero e não imprime
  URL nenhuma, então um chamador que tenta de novo acaba criando uma issue duplicada (gh v2.101.0,
  `pkg/cmd/issue/create/create.go:482-495`). Crie apenas com o conteúdo, guarde a URL impressa, e
  depois rode `gh issue edit <n> --parent <p> --add-blocked-by <b>`.
- 2026-09-24, verificado em um sandbox privado com gh 2.101.0: aplicar uma relação que já existe
  falha — `--add-blocked-by` com "Target issue has already been taken (addBlockedBy)" e `--parent`
  com "Issue may not contain duplicate sub-issues (addSubIssue)" — então leia
  `gh issue view <n> --json parent,blockedBy` primeiro e adicione só o que estiver faltando. Um
  título de milestone que já existe retorna 422 `already_exists` em vez de criar um segundo
  milestone. `gh label create <name> --force` sem `--color` reforça a cor de uma label existente e
  mantém sua descrição.
- 2026-09-24, uma avaliação da publicação de prévia de ticketing do BMad usando esse comando com a
  etapa de relação falhando uma vez: um modelo maior encontrou o órfão pelo título e manteve uma
  issue por ticket em 6 de 6 tentativas, enquanto um modelo menor tentou criar de novo e registrou
  um ticket quatro vezes em 2 de 3. Uma instrução que deixa a recuperação a cargo do agente falha
  com o agente menos cuidadoso; coloque a ordem na própria instrução.
