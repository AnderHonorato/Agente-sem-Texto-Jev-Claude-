---
description: Implement an approved plan or issue in its own worktree, run the gate, open the pull request.
argument-hint: <plan path or issue number>
---

# Build

O que construir: {{arguments}}

**Verifique primeiro, antes de gerar qualquer coisa.** Este comando precisa de um repositório
git, um remote no qual você possa dar push, e o `gh` autenticado. Sem repositório: diga isso e
ofereça fazer a mudança no local, com testes, e sem worktree ou pull request. Um repositório mas
sem remote ou sem `gh`: rode os passos 1 a 4, pare no commit local, e relate o branch como pronto
para push.

1. **Trabalhe a partir do caminho do plano ou do número da issue que lhe foi dado**, e diga qual
   deles na sua primeira mensagem. Nunca procure por um plano: `/plan` renomeia o arquivo aprovado
   e entrega seu caminho, e um plano encontrado por data tem a mesma chance de ser da semana
   passada. Sem um caminho nem uma issue, peça um. Dê ao builder o caminho absoluto do plano e
   diga a ele para copiar o arquivo para dentro da sua worktree e commitá-lo — uma worktree não
   carrega nenhum arquivo não rastreado, e o plano pertence ao PR.
2. **Gere o agente `builder`** com o texto do plano ou da issue, o caminho do repositório, o
   branch base, e o trailer de atribuição que sua ferramenta fornece. A definição dele já carrega
   o briefing permanente — uma worktree a partir do branch base conforme `worktree-per-agent`, as
   próprias instruções do repositório lidas primeiro, testes com toda mudança, o gate do
   repositório, um Conventional Commit local — então não redigite nada disso. Dê a ele o escopo em
   vez disso: os arquivos que pode tocar e os que deve deixar em paz.
3. **Rode o gate você mesmo** na worktree que ele nomeia, com os próprios comandos do repositório.
   Nunca aceite a palavra de um agente para um verificador; você lê o código de saída, não o
   relato dele sobre a execução. Vermelho significa que você conserta ou devolve o achado, nunca
   que você dá push de qualquer forma.
4. **Verifique o commit** antes que ele saia da máquina: um título Conventional Commit, um corpo
   terminando em `Closes #N` e o trailer de atribuição, e nada no diff que não se rastreie até a
   issue.
5. **Dê push no branch e abra o pull request** com `gh pr create`, baseado no branch padrão,
   nunca dando push direto para aquele branch. Corpo: alguns marcadores sobre o quê e o porquê,
   `Closes #N`, e a linha generated-with que sua ferramenta fornece.
6. **Responda ao bot de revisão**, onde o repositório roda um: um `.coderabbit.yaml`, um
   `greptile.json`, ou um bot que revisou pull requests anteriores. Espere até dez minutos pela
   primeira revisão dele neste pull request, e diga isso se nenhuma chegar. Depois trate toda
   thread não resolvida do bot como um achado: conserte-o na worktree, rerode o gate e dê push,
   ou responda com a razão pela qual não se aplica. Depois resolva a thread (GraphQL
   `reviewThreads`, depois `resolveReviewThread`). Depois de dar push numa correção, peça mais uma
   revisão, como `@coderabbitai review`, e espere de novo. No máximo duas rodadas; relate o que
   sobrar. Uma thread de um humano nunca é sua para resolver.

Relate o resultado em uma frase, com a URL do pull request quando um foi aberto, depois no
máximo cinco marcadores: threads de bot respondidas ou ainda abertas, uma decisão tomada em nome
do leitor, um passo deixado inacabado, um teste pulado. Dê o resultado do gate em uma linha, e
qualquer saída de falha por completo.
