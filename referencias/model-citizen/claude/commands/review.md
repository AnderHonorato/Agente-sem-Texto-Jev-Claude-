---
description: Review the branch's diff in two fresh contexts — scope against the spec, then quality — and report findings only.
argument-hint: [base ref, default main] [optional spec: issue number, plan path or PR number]
---

# Review (revisão)

Leia $ARGUMENTS como uma referência base e uma fonte de especificação. A base é uma referência,
`main` quando ausente. A especificação é um número de issue, um caminho para um arquivo de plano,
ou um número de pull request; quando nenhuma for dada, passe `infer` e deixe a passada de escopo
recair sobre o nome do branch e a última mensagem de commit.

1. **Estabeleça o diff, antes de criar qualquer subagente.** Rode `git diff --stat <base>...HEAD`
   e `git diff <base>...HEAD`. Se a base não resolver, diga isso e pare em vez de revisar contra a
   árvore errada. Fora de um repositório git não há diff nenhum: diga isso, e ofereça revisar
   arquivos nomeados ou um patch colado em vez disso.
2. **Crie primeiro o `spec-reviewer`**, em seu próprio contexto novo, com a base e a fonte da
   especificação. Ele reporta somente o que o diff faz que nada pediu, o que foi pedido e está
   faltando, e quais critérios de aceitação declarados o diff não comprova. Diga a ele para deixar
   toda questão de correção, estilo e qualidade de teste para a segunda passada.
3. **Depois crie o `reviewer`**, em um segundo contexto novo que não viu nem o trabalho nem a
   passada de escopo. Instrua-o para constatações apenas: sem reafirmar o que leu, sem resumo da
   mudança, sem elogios. Cada constatação carrega uma severidade, um `file:line`, o que está
   errado e por que importa. Diga a ele para tratar um teste faltando ou um caminho de erro não
   testado como uma constatação.
4. **Não repasse nada ao pé da letra.** Verifique cada constatação de qualquer uma das passadas
   contra o código você mesmo antes que chegue ao usuário e descarte as que não se sustentam. Onde
   você discordar, diga isso com seu raciocínio em vez de repassar a constatação.
5. **Reporte duas seções** — **Escopo** primeiro, depois **Qualidade** — cada uma uma lista
   ranqueada por severidade, cada item um bullet liderado em negrito carregando seu `file:line`.
   Declare o veredito primeiro. Uma seção sem nada sobrevivendo é uma única linha dizendo isso.

Dois contextos é o ponto central: um revisor que acabou de ler o código atrás de bugs racionaliza
o aumento de escopo, então a passada de escopo roda antes dele e nunca vê o que ele encontrou.

Não faça edições. Este comando lê, não corrige. Entregue as constatações e deixe o usuário decidir
sobre quais agir — `/build` é onde as mudanças acontecem.
