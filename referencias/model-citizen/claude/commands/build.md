---
description: Implement an approved plan or issue in its own worktree, run the gate, open the pull request.
argument-hint: <plan path or issue number>
---

# Build

O que construir: $ARGUMENTS

**Verifique primeiro, antes de criar qualquer subagente.** Este comando precisa de um repositório
git, de um remote no qual você possa dar push, e do `gh` autenticado. Sem repositório: diga isso e
ofereça fazer a mudança no local, com testes, e sem worktree nem pull request. Um repositório mas
sem remote ou sem `gh`: rode os passos 1 a 4, pare no commit local, e reporte o branch como pronto
para push.

1. **Trabalhe a partir do caminho do plano ou do número da issue que lhe foi dado**, e diga qual
   deles na sua primeira mensagem. Nunca procure um plano por conta própria: `/plan` renomeia o
   arquivo aprovado e entrega seu caminho, e um plano encontrado por data tem tanta chance de ser
   da semana passada. Sem caminho nem issue, peça um. Dê ao builder o caminho absoluto do plano e
   diga para copiar o arquivo para dentro da sua worktree e commitá-lo — uma worktree não carrega
   arquivo não versionado, e o plano pertence ao PR.
2. **Crie o agente `builder`** com o texto do plano ou da issue, o caminho do repositório, o branch
   base, e o trailer de atribuição que sua ferramenta fornece. A definição dele já carrega o brief
   padrão — uma worktree a partir do branch base conforme `worktree-per-agent`, as próprias
   instruções do repositório lidas primeiro, testes com toda mudança, o gate do repositório, um
   Conventional Commit local — então não redigite nada disso. Dê a ele o escopo em vez disso: os
   arquivos que ele pode tocar e os que deve deixar intocados.
3. **Rode o gate você mesmo** na worktree que ele nomeia, com os próprios comandos do repositório.
   Nunca aceite a palavra de um agente como verificação; você lê o status de saída, não o relato
   dele sobre a execução. Vermelho significa que você corrige ou devolve a constatação, nunca que
   você faz push mesmo assim.
4. **Confira o commit** antes que ele saia da máquina: um título no padrão Conventional Commit, um
   corpo terminando em `Closes #N` e o trailer de atribuição, e nada no diff que não se relacione
   com a issue.
5. **Faça push do branch e abra o pull request** com `gh pr create`, baseado no branch padrão,
   nunca fazendo push direto para esse branch. Corpo: alguns bullets sobre o quê e por quê, `Closes
   #N`, e a linha de "gerado com" que sua ferramenta fornece.
6. **Responda ao bot de revisão**, onde o repositório rodar um: um `.coderabbit.yaml`, um
   `greptile.json`, ou um bot que revisou pull requests anteriores. Espere até dez minutos pela
   primeira revisão dele neste pull request, e diga se nenhuma chegar. Depois trate cada thread do
   bot não resolvida como uma constatação: corrija na worktree, rode o gate novamente e faça push,
   ou responda com o motivo pelo qual não se aplica. Depois resolva a thread (GraphQL
   `reviewThreads`, depois `resolveReviewThread`). Após enviar uma correção, peça mais uma revisão,
   como `@coderabbitai review`, e espere de novo. No máximo duas rodadas; reporte o que restar. Uma
   thread de um humano nunca é sua para resolver.

Reporte o resultado em uma frase, com a URL do pull request quando um foi aberto, depois no máximo
cinco bullets: threads do bot respondidas ou ainda abertas, uma decisão tomada em nome do leitor,
um passo deixado inacabado, um teste pulado. Dê o resultado do gate em uma linha, e qualquer saída
de falha na íntegra.
