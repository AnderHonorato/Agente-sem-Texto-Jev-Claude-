# Revisão do CodeRabbit para o agent-harness, com threads do bot resolvidas antes do merge

> **Veredito.** Adiciona um `.coderabbit.yaml` para que o CodeRabbit revise todo PR para `main` de
> forma silenciosa e gratuita, e dá ao `/build` um passo que responde as threads do bot antes de um
> PR subir para aprovação. O `/land` então para numa thread aberta pelo nome, porque o
> `main-review` já bloqueia essa mesclagem e hoje o `land` só descobre isso quando o `gh` recusa.
> **Esforço** cerca de meio dia de agente · **Risco** baixo: um arquivo de configuração e dois
> textos de workflow · **Raio de impacto** `/build` e `/land` em todo repositório que o harness
> atende

> **Mudou nesta rodada.** Correções acontecem no `/build`, em um PR (resolvido) · `CONTRIBUTING.md`
> diz a contribuidores externos como trabalhar com o bot · a decisão de nova revisão agora
> responde por contribuidores.

## Em resumo

- **Resultado** — todo PR para `main` recebe uma revisão do CodeRabbit, suas threads são corrigidas
  ou respondidas antes de você aprovar, e o `/land` nunca encontra um bloqueio de thread de
  surpresa
- **Abordagem** — um `.coderabbit.yaml` validado por schema (tranquilo, uma revisão por PR,
  linters de prosa desligados, instruções por caminho), mais o passo 6 do `/build` e uma
  verificação de thread no passo 1 do `/land`
- **Toca** — só o agent-harness: a configuração, `primitives/workflows/{build,land}.md` e suas
  cópias geradas, um parágrafo de `CONTRIBUTING.md`, um fragmento de changelog, a história e o
  mapa de issues; cerca de 9 arquivos
- **Novas dependências** — o GitHub App do CodeRabbit, um serviço hospedado grátis para
  repositórios públicos; nada vendorizado
- **Fora de escopo** — Greptile, qualquer mudança no ruleset `main-review`, o CodeRabbit como check
  obrigatório, texto de vitrine (landing copy)
- **Teste de saída** — gate verde, os quatro checks obrigatórios verdes no PR, e o CodeRabbit o
  revisa assim que você instalar o app
- **Pergunta em aberto** — se pushes recebem uma nova revisão automática; veja a decisão 1

## Design do sistema

```text
/build ── PR ──▶ GitHub ── PR opened ──▶ *CodeRabbit (.coderabbit.yaml)
                                               │
                                        review threads
                                               ▼
*/build step 6 ◀┄┄ waits up to 10 min ┄┄ unresolved threads
     │ fix and push, or reply; then resolve
     ▼
you approve ──▶ */land step 1: no open thread ──▶ squash merge
```

`*` = novo ou alterado. A regra do `main-review` de que threads precisam estar resolvidas
continua como está.

## Passos

1. **Validar a configuração contra o schema ao vivo do CodeRabbit** —
   `/tmp/review-bots-research/coderabbit.yaml`, feito durante o planejamento.
   *Saída:* 0 erros de schema e 0 chaves desconhecidas; os dois controles negativos foram
   capturados.
2. **[Registrar a issue de entrega](#passo-2--registrar-a-issue-de-entrega)** — um worktree
   gerenciado, depois `bmad_issue_sync.py new`, marco v0.14.0.
   *Saída:* a issue carrega `type::story`, e seu ID e o esqueleto de história existem no worktree.
3. **[Construir](#passo-3--construir)** — o agente `builder` adiciona a configuração, o passo 6 do
   `/build`, a verificação do `/land` e o parágrafo para contribuidores, regenera, escreve o
   fragmento e a história, e faz um commit.
   *Saída:* `bin/harness generate --check` está limpo no worktree.
4. **Rodar o gate eu mesmo** — lint, testes unitários e `generate --check` no worktree.
   *Saída:* `lint: 0 finding(s)`, `OK` sem pulos, generate limpo.
5. **Revisar com `bmad-code-review`** — achados e como cada um foi resolvido entram na história.
   *Saída:* nenhum achado de alta severidade não resolvido.
6. **[Enviar (push) e abrir o PR](#passo-6--enviar-push-e-abrir-o-pr)** —
   `feat/coderabbit-review` para `main`, `Closes #N`, uma linha `Landing copy:`.
   *Saída:* lint, test, issue-ownership e landing-copy estão verdes na ponta (head).
7. **Você instala o app do CodeRabbit** só no JakeSelby/agent-harness; é o único passo que eu não
   posso fazer.
   *Saída:* o CodeRabbit revisa o PR; comente `@coderabbitai review` se o PR for anterior à
   instalação.

## Decisões para o revisor

> **1. O CodeRabbit deve revisar de novo automaticamente depois que uma correção é enviada?**
> *Recomendação* não, como o BMad faz — um contribuidor ainda recebe uma revisão completa quando o
> PR abre, pede outra com `@coderabbitai review`, e usa seu próprio orçamento de taxa.
> *Alternativa* sim — contribuidores veem cada correção confirmada sem pedir, e seus ~35 PRs por
> dia aproximadamente dobram em volume de revisão.

## Riscos

- **O limite de taxa do open-source estrangula revisões nesse volume** — revisões são puladas,
  nunca bloqueando; se acontecer com frequência, restrinja `auto_review` ou pese o plano
  Essentials a $24 por mês.
- **Um achado está errado, ou a prosa recebe nitpicks** — o `/build` responde com o motivo e
  resolve; no máximo duas rodadas; ajuste `path_instructions` a partir do que se repetir.
- **O bot nunca posta (queda ou limite de taxa)** — o passo 6 espera dez minutos, depois diz isso e
  segue em frente.

---

# Anexo

## Passo 2 — Registrar a issue de entrega

`trust_check` classifica `coding.shell_exec`, `coding.git_commit` e `coding.git_push` em L2 para
este repositório, então aprovar este plano aprova exatamente os comandos abaixo e no Passo 6, e
mais nada. Rode a primeira linha a partir do checkout compartilhado, e o resto no worktree que ela
imprime.

```sh
bin/harness worktree create coderabbit-review --branch feat/coderabbit-review
python3 scripts/bmad_issue_sync.py new --kind story --milestone 18 \
  --title "Adopt CodeRabbit review and clear review-bot threads before merge" \
  --body-file /tmp/review-bots-research/issue-body.md
# A reserva costuma ficar atrás da listagem de issues; quando isso acontece:
python3 scripts/bmad_issue_sync.py reserve --issue <N> --kind story
```

O corpo da issue é `/tmp/review-bots-research/issue-body.md`, como escrito. O marco 18 é a v0.14.0.

## Passo 3 — Construir

Dispare o `builder` com o caminho absoluto deste plano, o worktree do Passo 2 (ele trabalha ali e
não cria nenhum outro), base `main`, e o trailer Co-Authored-By que a ferramenta fornece.

Permitido tocar:

- **`.coderabbit.yaml`** — copie `/tmp/review-bots-research/coderabbit.yaml` literalmente.
- **`primitives/workflows/build.md`** — adicione o passo 6, abaixo, e adicione "as threads do bot
  respondidas e quaisquer ainda abertas" à linha de relatório.
- **`primitives/workflows/land.md`** — estenda o passo 1, abaixo.
- **`CONTRIBUTING.md`** — adicione o parágrafo abaixo ao final de `## Review`, como escrito.
- **`claude/commands/build.md`, `claude/commands/land.md`** — só através de
  `bin/harness generate`, nunca manualmente.
- **`changelog.d/<N>.changed.md`** — uma linha, seguindo `changelog.d/README.md`.
- **`_bmad-output/implementation-artifacts/<ID>.md`** — preencha toda seção da história a partir
  deste plano: design e decisões do cartão, dev notes deste anexo.
- **`_bmad-output/issue-map.json`** — só como a ferramenta de sincronização o escreve.
- **`.agent-harness/plans/2026-09-24-coderabbit-review.md`** — copie este plano para dentro do
  worktree.

Não deve tocar: `product.json`, qualquer outro workflow, os rulesets, `templates/`.

Novo passo 6 do `/build`, depois de "Push the branch and open the pull request":

> 6. **Answer the review bot**, where the repository runs one: a `.coderabbit.yaml`, a
>    `greptile.json`, or a bot that reviewed earlier pull requests. Wait up to ten minutes for
>    its first review of this pull request. Then take each unresolved bot thread as a finding:
>    fix it in the worktree, rerun the gate and push, or reply with the reason it does not apply.
>    Then resolve the thread (GraphQL `reviewThreads`, then `resolveReviewThread`). Two rounds at
>    most; report whatever remains. A human's thread is never yours to resolve.

Adição ao passo 1 do `/land`, depois de "A pending, failing or stale check stops the workflow,
named.":

> So does an unresolved review thread: name it and stop. A fix belongs to `/build`, before
> approval, and a human's thread is theirs to resolve.

O parágrafo para o final da seção `## Review` do `CONTRIBUTING.md`:

> CodeRabbit also reviews every PR into `main`, forks included, once when it opens. Treat its
> comments as you would a reviewer's: push a fix, or reply with why one doesn't apply, then
> resolve the thread, because `main` won't merge while a review thread is open. Comment
> `@coderabbitai review` for another pass after you push. Its comments are advice, and where you
> disagree with it, the maintainer decides.

O commit é `feat(workflows): adopt CodeRabbit review and clear bot threads before merge`. Seu
corpo tem três marcadores (a configuração, o passo 6 do `/build`, a verificação do `/land`),
depois `Closes #<N>`, depois o trailer. Não usa travessões longos, porque é publicado em nome do
Jake.

## Passo 6 — Enviar (push) e abrir o PR

Antes de enviar (push), rode o `trust_check` para `coding.git_push`.

```sh
git push -u origin feat/coderabbit-review
gh pr create --base main --head feat/coderabbit-review \
  --title "feat(workflows): adopt CodeRabbit review and clear bot threads before merge" \
  --body-file <arquivo de corpo fora do worktree>
```

O corpo segue `.github/PULL_REQUEST_TEMPLATE.md`:

- **O quê e por quê** — os três marcadores de escopo da issue.
- **Onde aterrissa** — os arquivos.
- **Checklist** — marcada honestamente.
- `Closes #<N>`.
- `Landing copy: none; /build and /land gain a step, not a new capability.`
- A linha de geração.

Sem travessões longos.

## Evidência e verificação

- **Configuração:** 0 erros contra `https://coderabbit.ai/integrations/schema.v2.json`
  (jsonschema num venv temporário), e 0 chaves faltando no schema. O schema permite propriedades
  extras, então a varredura de chaves é o teste que morde. Seu controle sinalizou
  `reviews.not_a_key`, e o controle de enum sinalizou `profile: loud`. `mode: "off"` está entre
  aspas porque YAML 1.1 lê um `off` sem aspas como falso.
- **Projeções geradas:** `claude/agents/`, `claude/commands/` e `claude/CLAUDE.md` são gerados
  (`lib/harness_core/catalog.py`, perto da linha 420). `claude/rules`, `claude/skills` e
  `claude/stances` são links simbólicos para dentro de `primitives/`. É por isso que os filtros de
  caminho descartam os três primeiros e revisam `primitives/`.
- **Ruleset:** `main-review` define `required_review_thread_resolution: true` e exige 0
  aprovações, com bypass só para administradores. `/land` mescla com um simples
  `gh pr merge --squash --delete-branch`, que recusa uma mesclagem bloqueada a menos que receba
  `--admin`.
- **Preços, elegibilidade e a evidência do BMAD-METHOD#2957:**
  `/tmp/review-bots-research/digest.md`.

## Histórico de revisão

- **Rodada 1, 2026-09-24:**
  - Resolvido: achados do bot são corrigidos no `/build` antes da aprovação, e a configuração e os
    workflows são entregues em um único PR.
  - Jake perguntou como o bot funciona para contribuidores externos. A resposta:
    - O CodeRabbit revisa PRs de fork; ele revisou o próprio PR de fork do Jake, o
      BMAD-METHOD#2957.
    - O autor de um PR pode resolver suas conversas.
    - Limites de taxa contam por identidade de desenvolvedor.
    - A própria configuração do BMad também define `auto_incremental_review: false`.
  - Adicionado o parágrafo do `CONTRIBUTING.md` para que os contribuidores conheçam o ciclo.

## Adiado, e por quê

- **Greptile:** grátis só através de seu programa open-source, que exige atestar que o
  repositório não faz parte de um produto comercial. Essa é uma decisão do Jake, e um bot já é o
  suficiente para começar.
- **Um `.coderabbit.yaml` em `templates/repo/`:** esperar até este ter rodado por algumas semanas.
- **Revisão automática do Codex como um segundo revisor de uma família de modelo diferente:**
  reconsiderar depois de medir a taxa de acerto do CodeRabbit.
