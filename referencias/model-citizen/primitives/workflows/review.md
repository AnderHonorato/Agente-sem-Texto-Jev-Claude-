---
description: Review the branch's diff in two fresh contexts — scope against the spec, then quality — and report findings only.
argument-hint: [base ref, default main] [optional spec: issue number, plan path or PR number]
---

# Review

Leia {{arguments}} como uma referência base e uma fonte de especificação. A base é uma
referência, `main` quando ausente. A especificação é um número de issue, um caminho para um
arquivo de plano, ou um número de pull request; quando nenhuma é dada, passe `infer` e deixe a
passada de escopo recorrer ao nome do branch e à última mensagem de commit.

1. **Estabeleça o diff, antes de gerar qualquer coisa.** Rode `git diff --stat <base>...HEAD` e
   `git diff <base>...HEAD`. Se a base não resolve, diga isso e pare em vez de revisar contra a
   árvore errada. Fora de um repositório git não há diff algum: diga isso, e ofereça revisar
   arquivos nomeados ou um patch colado em vez disso.
2. **Gere `spec-reviewer` primeiro**, em seu próprio contexto novo, com a base e a fonte de
   especificação. Ele relata apenas o que o diff faz que ninguém pediu, o que foi pedido e está
   faltando, e quais critérios de aceitação declarados o diff não comprova. Diga a ele para
   deixar toda questão de correção, estilo e qualidade de teste para a segunda passada.
3. **Depois gere `reviewer`**, num segundo contexto novo que não viu nem o trabalho nem a passada
   de escopo. Instrua-o para apenas achados: sem reafirmar o que leu, sem resumo da mudança, sem
   elogio. Cada achado carrega uma severidade, um `file:line`, o que está errado e por que
   importa. Diga a ele para tratar um teste faltando ou um caminho de erro não testado como um
   achado.
4. **Não retransmita nada literalmente.** Verifique todo achado de cada passada contra o código
   você mesmo antes que chegue ao usuário e descarte os que não se sustentam. Onde você discorda,
   diga isso com seu raciocínio em vez de passar o achado adiante.
5. **Relate duas seções** — **Escopo** primeiro, depois **Qualidade** — cada uma uma lista
   ranqueada por severidade, cada item um marcador liderado por negrito carregando seu
   `file:line`. Declare o veredito primeiro. Uma seção sem nada sobrevivendo é uma única linha
   dizendo isso.

Dois contextos são o ponto: um revisor que acabou de ler o código atrás de bugs racionaliza fuga
de escopo, então a passada de escopo roda antes dele e nunca vê o que ele encontrou.

Não faça edições. Este comando lê, não conserta. Entregue os achados e deixe o usuário decidir
quais ações tomar — `/build` é onde as mudanças acontecem.
