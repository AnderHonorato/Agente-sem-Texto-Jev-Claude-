---
description: Write the repository handoff file for the next session, and record any durable learning.
argument-hint: [note to carry into the next session]
---

# Handoff (repasse)

Nota para levar adiante: $ARGUMENTS

1. **Sobrescreva `.agent-harness/progress.md`** na raiz do repositório, ou no diretório atual quando
   não houver repositório. É um retrato instantâneo, nunca um acréscimo; o início de sessão lê suas
   primeiras oitenta linhas. Use exatamente estes cabeçalhos:

   ```markdown
   # Handoff <ISO date>

   ## Done
   ## Open
   ## Next command
   ## Decisions needed
   ## Learnings
   ```

   Preencha-os a partir desta sessão, não do arquivo que você está substituindo. **Done** e
   **Open** são bullets curtos nomeando arquivos e comandos. **Next command** é uma linha
   executável e nada mais. **Decisions needed** é o que só o usuário pode resolver. **Learnings**
   é o que você gostaria de ter sabido quando esta sessão começou.

2. **Salve o contrato de tarefa compartilhado.** Leia `citizen task show` primeiro. Escreva uma
   entrada JSON com `objective`, `next_steps`, `decisions`, e `artifacts`; adicione o checkout do
   framework e a baseline quando um framework de planejamento for dono dos artefatos. Salve com
   `citizen task save --input <file> --runtime <runtime> --revision <current-revision>`. O próximo
   runtime lê os mesmos dados, reconfere a árvore, e estabelece suas próprias permissões. Um
   handoff nunca transfere uma aprovação.

3. **Promova qualquer coisa durável.** Se um aprendizado ajudaria uma sessão futura neste
   repositório — uma correção que generaliza, uma armadilha que vale evitar, um comando que
   realmente funciona — anexe-o como um bullet datado em `docs/solutions/<yyyy-mm-dd>-<slug>.md`
   sob a raiz do repositório, ou sob `.agent-harness/` quando não houver repositório, criando a
   pasta quando ela estiver faltando. Uma ou duas frases, carregando o comando ou o caminho, para
   que uma correção vire um artefato em vez de um prompt que o usuário precisa repetir. Nada
   durável, nenhum arquivo.

Encerre o turno com os dois caminhos: o arquivo de progresso, e o arquivo de soluções se você
escreveu um.
