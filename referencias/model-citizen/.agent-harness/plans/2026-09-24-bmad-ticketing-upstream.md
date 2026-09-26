# Ticketing do BMad: correção do armazenamento no GitHub e pitch de reconciliação a montante, adoção com portão aqui

> **Veredito.** Este plano termina no pitch: uma correção de bug com issue primeiro que torna a
> publicação no GitHub segura para rodar de novo, mais um pedido de funcionalidade para uma
> verificação de reconciliação árvore-para-rastreador, tudo nos próprios canais do projeto a
> montante (upstream). Do nosso lado, registramos um épico de adoção cujo portão segue o roteiro do
> upstream; o spike e a construção da reconciliação ganham cada um sua própria rodada quando seu
> portão abrir.
> **Decidido em 2026-09-24.** Recomendações 2–5 aceitas · decisão 1: uma nova sessão conduz isso,
> não a sessão irmã · uma parada de confirmação, todos os rascunhos em lote, antes de qualquer
> issue ou PR ser criado.
> **Esforço** ~1 dia de agente · **Risco** baixo: dois textos pequenos e uma correção de prosa de
> ~12 linhas · **Raio de impacto** a configuração de uma skill de preview a montante; um arquivo de
> épico aqui

## Em resumo

- **Resultado** — o upstream tem um bug reproduzido com um PR de correção e uma proposta de
  reconciliação aguardando um mantenedor; o agent-harness tem um épico que diz exatamente quando
  trocamos.
- **Abordagem** — reprodução primeiro; issue de bug "v7 preview", depois um PR que o corrige; issue
  de pedido de funcionalidade e uma introdução no Discord para a reconciliação; nosso épico
  registra o portão.
- **Toca** — fork `JakeSelby/BMAD-METHOD` (só `config/gh-ticketing.toml`); `_bmad-output/` do
  agent-harness (1 épico); um repositório sandbox privado.
- **Novas dependências** — Nenhuma. gh CLI 2.94 ou mais recente localmente (2.93.0 instalado).
- **Fora de escopo** — construir a reconciliação ou ids seguros entre branches antes de um sim; o
  spike; portar `bmad_issue_sync.py`; migrar nossas 433 issues mapeadas.
- **Teste de saída** — issue de bug e PR abertos no upstream com CI verde; pedido de funcionalidade
  aberto; a resposta do mantenedor, ou o silêncio, registrado em nosso épico.
- **Pergunta em aberto** — nenhuma; as cinco decisões foram fechadas em 2026-09-24.

## Design do sistema

```text
sandbox repo ── repro ──▶ *bug issue ──▶ *PR 1 (fork → dev) ──▶ maintainer
ticket tree ── write ──▶ *create, content only ── number ──▶ tracker_id
                              └─▶ *parent · blocked-by, if missing
*feature request + Discord ┄┄ yes ┄┄▶ later round: tickets.py reconcile
agent-harness: issue-map + bmad_issue_sync.py ┄┄ gate ┄┄▶ *adoption epic
```

`*` = novo ou alterado. Links pontilhados esperam por outra pessoa: o sim do mantenedor, o roteiro
do upstream.

## Passos

1. **[Reproduzir a duplicata](#passo-1--reproduzir-a-duplicata)** — gh 2.94+ contra um
   repositório sandbox privado; também testar se o `gh label create --force` do setup apaga um
   rótulo existente.
   *Saída:* a issue existe, código de saída ≠ 0, nenhuma URL impressa; transcrição salva;
   resultado do rótulo anotado como sim ou não.
2. **[Registrar a issue de bug](#passo-2--registrar-a-issue-de-bug)** — template de relatório de
   bug, título começando com "v7 preview:", reprodução e as linhas de origem do gh; texto exato
   para sua aprovação.
   *Saída:* sua aprovação; issue aberta em `bmad-code-org/BMAD-METHOD`.
3. **[Fork e linha de base](#passo-3--fork-e-linha-de-base)** — fork para
   `JakeSelby/BMAD-METHOD`, clone para `~/repos/BMAD-METHOD`, `upstream` com push desabilitado,
   worktree a partir de `upstream/dev`.
   *Saída:* `uv run --frozen pre-commit run --all-files` verde em `dev` intocado.
4. **[Tornar a publicação segura para rodar de novo](#passo-4--tornar-a-publicação-segura-para-rodar-de-novo)**
   — só as linhas 50-56 de `[verbs].write`; a reescrita do corpo pela #2944 fica intocada.
   *Saída:* gates verdes; falha de relação forçada, publicação rodada duas vezes: uma issue por
   ticket em 3 de 3 execuções, duplicatas de linha de base.
5. **[Abrir o PR 1](#passo-5--abrir-o-pr-1)** — What/Why/How/Testing com menos de 200 palavras,
   `Fixes #<bug>`, o link para a construção independente e para o harness.
   *Saída:* sua aprovação no texto; PR aberto contra `dev`; `quality` verde no ubuntu e no windows.
6. **[Pitch da reconciliação](#passo-6--pitch-da-reconciliação)** — issue de pedido de
   funcionalidade (reconciliação, com ids seguros entre branches como uma oferta) e uma introdução
   de três frases no Discord.
   *Saída:* sua aprovação nos dois; issue aberta; você posta no Discord; nada é construído antes do
   sim de um mantenedor.
7. **[Registrar nosso épico de adoção](#passo-7--registrar-nosso-épico-de-adoção)** —
   `bmad_issue_sync.py new` depois `reserve`; bloqueadores e cinco condições de portão; PR
   mesclado, `/land`.
   *Saída:* épico mapeado em `issue-map.json`; `bmad_issue_sync.py audit` limpo; links do upstream
   registrados.

## Decisões para o revisor

> **1. Qual sessão conduz isso?**
> *Recomendação* a sessão irmã `bridge-cse-015hyoaxenpjgu8qqxkns4tj-33`, que recebeu o mesmo
> trabalho; esta sessão está além de seu limiar de contexto.
> *Alternativa* esta sessão, que guarda o raciocínio, a um custo por turno maior daqui em diante.

> **2. Issue de bug mais um PR de ~12 linhas, ou só a issue?**
> *Recomendação* os dois: o CONTRIBUTING roteia bugs por issues e diz que uma correção pequena pode
> simplesmente "Just open the PR", então ele ganha algo para mesclar ou copiar.
> *Alternativa* só a issue: nenhum PR de ticketing externo foi mesclado ainda, e ele mesmo escreve
> a maior parte desta skill.

> **3. O que entra no pitch?**
> *Recomendação* reconciliação como o pedido, ids seguros entre branches como uma oferta de uma
> linha: as duas são lições que nossa sincronização pagou para aprender.
> *Alternativa* só a reconciliação, para o pedido mais estreito; ou adicionar tipos de issue
> nativos, que estaríamos inventando em vez de trazendo.

> **4. Do nosso lado: épico e portão agora, spike depois?**
> *Recomendação* sim: o upstream diz que bmad-build e sprint-planning ainda não leem a árvore de
> tickets, então um spike agora não testaria nada que roda.
> *Alternativa* spike agora sobre o preview como está, para uma leitura antecipada de IDs e
> critérios de aceitação.

> **5. Um repositório sandbox privado na sua conta?**
> *Recomendação* `JakeSelby/bmad-ticketing-sandbox`, privado, apagado assim que o PR 1 fechar.
> *Alternativa* um repositório de uma organização, que também permitiria tipos de issue nativos mais
> tarde.

## Riscos

- **A #2944 mescla primeiro e reescreve `write`** — faça rebase do PR 1; a mudança fica nas linhas
  que a #2944 deixa intocadas.
- **Ele corrige isso no próprio branch dele** — feche o PR 1 com agradecimento; a issue cumpriu seu
  papel.
- **O passo 1 não reproduz** — nenhuma issue de bug ou PR; o pitch lidera só com a reconciliação.

---

# Anexo

## O que podemos trazer para o upstream (questão 1)

Fontes: `dev` upstream em `29372f4`, os PRs abertos #2944–#2949, o código-fonte do gh v2.101.0, e
os resumos da outra sessão em `/tmp/carve-715/` (`bmad-ticketing.md`, `bmad-contrib.md`,
`ours-mechanics.md`). O armazenamento é prosa: `config/gh-ticketing.toml` guarda os verbos
`setup`, `write` e `query` que o agente roda com `gh`; `tickets.py` só lida com a árvore local e
nunca toca um rastreador.

- **U1, publicação segura para rerun: bug, neste plano.** `pkg/cmd/issue/create/create.go:482-495`
  do gh cria a issue, depois resolve e aplica `--type`, `--parent` e `--blocked-by`; em um erro,
  retorna antes de `fmt.Fprintln(opts.IO.Out, newIssue.URL)`. O upstream coloca as duas relações na
  chamada de criação (`gh-ticketing.toml:51-52`) e espelha `tracker_id` só depois de uma escrita
  bem-sucedida (`:61-62`); não existe busca, marcador ou deduplicação em lugar nenhum. Gatilhos: um
  número de pai desatualizado, GHES abaixo de 3.19, um limite de taxa secundário em uma rajada no
  início. A criação de marco (milestone) não tem verificação de existência (`:58`). Nossas lições:
  POST puro, depois relações em chamadas separadas (`create_issue:1594`,
  `apply_manifest:1189-1213`); uma falha após registrar nomeia a issue registrada (`:1608`); o
  endpoint de listagem do GitHub fica atrás de um POST (AH-B040, #392).
- **U2, reconciliação: funcionalidade, apresentada aqui, construída em uma rodada posterior.** O
  upstream compara um ticket de cada vez ("A body that differs from the file: show and ask",
  `board.md:25`) e adota só filhos de um pai consultado (`gh-ticketing.toml:73`); issues externas
  sem pai e desvio de árvore inteira não são tratados, e os hooks não estão integrados, então o
  desvio se acumula entre execuções. Nosso: `live_findings:780` e adoção com portão de triagem
  (`accepted_for_delivery:760`).
- **U4, ids seguros entre branches: oferecido em uma linha.** "Cross-branch collisions: nothing in
  the skill addresses them"; `tickets.py` só detecta ids duplicados depois do fato
  (`tickets.py:216-217,266-267,326-329`). Nosso `survey_ids_elsewhere:1307` lê o mapa em todo
  worktree e branch antes de alocar. Isso corrige a rodada 1, que chamou a pesquisa de
  desnecessária.
- **Segundo bug candidato, só se o passo 1 confirmar.** O setup roda `gh label create <name>
  --force` sem cor ou descrição (`gh-ticketing.toml:44`), o que pode reescrever um rótulo `bug`
  existente de um repositório. Uma correção por PR: seria sua própria issue.
- **Não oferecido.** Tipos de issue nativos (U3): o upstream tipa por rótulo e não temos lição
  nenhuma para trazer, só um modo de projeção. Sub-issues e reparentamento: já no upstream, e
  `--add-sub-issue` passa `replaceParent: true` (`api/queries_issue.go:689`). Links de fechamento
  de PR: o bmad-build está no meio de uma reescrita na #2944. O bloco de corpo gerenciado e a
  renderização de status de sprint: o design do upstream remove a necessidade.

## Por que ainda não podemos adotar, e o que muda aqui (questão 2)

1. **O upstream diz que ainda não está pronto.** "While ticketing is in preview,
   `bmad-create-epics-and-stories` with `bmad-sprint-planning` remains the supported route"; suas
   histórias "are not read by `bmad-sprint-planning`, do not appear in `sprint-status.yaml`, and
   the current `bmad-build` does not move their status (YET)"; "Hooks are not integrated yet".
   Nenhum procedimento de graduação ou promessa de estabilidade.
2. **Não lançado.** Instala só através de `npx skills add ... --skill bmad-preview-ticketing` e
   `bmad setup`; a tag `latest` do npm é 6.12.0; fixamos `bmad-method` em 6.12.0
   (`docs/bmad.md:15-19`).
3. **No meio de uma reescrita.** A #2944 é a parte um de quatro em
   `feat/integrate-build-skills-with-ticketing`; as outras partes movem bmad-build, review e
   retrospective para a árvore e removem a rota de sprint-status.
4. **Faltam guardas.** U1 e U2; nosso check obrigatório `issue-ownership` e a auditoria diária ao
   vivo precisam dos dois.
5. **Layout e identidade.** Os três checks leem `issue-map.json` e arquivos planos `AH-*.md`
   (`check_issue_ownership.py:13,60-72`, `ci.yml:64-65`, `bmad-traceability.yml:28`); a v7 usa
   pastas, ids inteiros por épico e frontmatter `tracker_id`. O mapa guarda 433 itens.
6. **Se encaixa com customização.** Os critérios de aceitação podem ficar locais editando nossa
   cópia de `write` ("edits survive skill updates", `store-setup.md:6`); `tracker_status` já
   prevalece sobre `status` para o estado do quadro (`SKILL.md:97`).

A migração, quando o portão abrir, é seu próprio plano: fixar o lançamento, converter os 433 itens
com os IDs do AH mantidos como apelidos, reapontar os três checks, customizar `write`, e
aposentar os comandos sobrepostos em `bmad_issue_sync.py`.

## Passo 1 — Reproduzir a duplicata

```sh
brew upgrade gh && gh --version            # expect 2.94 or later
gh repo create JakeSelby/bmad-ticketing-sandbox --private --add-readme
S=JakeSelby/bmad-ticketing-sandbox
gh issue create -R $S --title "repro: relation after create" --body "x" --blocked-by 999999; echo "exit=$?"
sleep 10; gh issue list -R $S --state all --json number,title
gh label list -R $S --json name,color,description | grep -A2 '"bug"'
gh label create bug -R $S --force; gh label list -R $S --json name,color,description | grep -A2 '"bug"'
```

Esperado: um erro ao resolver `--blocked-by`, um código de saída diferente de zero, nenhuma URL, e
a issue listada (liste de novo depois de 30 segundos antes de concluir o contrário). Para o
rótulo: compare cor e descrição antes e depois. Salve tudo em `/tmp/bmad-research/repro.txt`.

## Passo 2 — Registrar a issue de bug

Pesquise issues abertas e fechadas por "duplicate", "publish" e "tracker_id" primeiro. Use o
template de relatório de bug; preencha seus campos a partir deste rascunho. Nenhum travessão
longo; `grep -n $'—'` antes de mostrar ao Jake.

```markdown
Title: v7 preview: GitHub publish files a ticket twice when a relation fails

The GitHub store's `write` verb creates each issue with `--parent` and `--blocked-by` on `gh issue create`. gh makes the issue first and adds those relations afterwards (`pkg/cmd/issue/create/create.go`, `DeferredUpdateIssue`), and it prints the url only when both succeed. When the relation step fails, the issue exists but `tracker_id` is never written back, so the next publish creates the ticket again.

Steps to reproduce: with gh 2.94 or later, run `gh issue create --title test --body x --blocked-by 999999`. It exits non-zero and the issue is there anyway.

Expected: one issue, recorded in the ticket file. Actual: an orphan issue, and a second one on the next publish.

Environment: gh <version>, Claude Code with <model>, bmad-preview-ticketing at <sha>.
```

## Passo 3 — Fork e linha de base

```sh
gh repo fork bmad-code-org/BMAD-METHOD --clone=false
git clone https://github.com/JakeSelby/BMAD-METHOD.git ~/repos/BMAD-METHOD && cd ~/repos/BMAD-METHOD
git remote add upstream https://github.com/bmad-code-org/BMAD-METHOD.git
git remote set-url --push upstream no_push && git fetch upstream dev
harness worktree create ticketing-gh-publish-rerun ~/repos/BMAD-METHOD \
  --branch ticketing-gh-publish-rerun --base upstream/dev   # check --help for the repo argument
uv sync --frozen && uv run --frozen pre-commit run --all-files --show-diff-on-failure
```

Nunca faça commit direto na `dev` ou `main` locais do fork. Uma linha de base vermelha é do
upstream: registre o resultado e pare.

## Passo 4 — Tornar a publicação segura para rodar de novo

Edite só `[verbs].write`, linhas 50-56 da dev. As linhas 57-64 ficam como estão: a #2944 reescreve
59-60, e uma edição que as tocasse entraria em conflito. Formulação alvo, cortada para caber no
estilo do arquivo:

```text
One issue per new ticket, created in tree and prerequisite order so every relation has a number to point at.
An initiative's milestone must exist first: look for it with `gh api repos/{owner}/{repo}/milestones?state=all`,
and create it only when missing.
Create with content only: `gh issue create --title <t> --body-file <b> --label <type>,<[tickets.status].<state>>
[,hitl,risk:<r>,P<n>] [--milestone <initiative>]`, and write tracker_id and remote from the url it prints
before anything else. Then `gh issue edit <n> --parent <n> --add-blocked-by <n,n>`, leaving out what
`gh issue view <n> --json parent,blockedBy` already shows. Relations stay off the create: gh adds them after
the issue exists, and when that fails it exits non-zero without printing the url, so a retry files the ticket twice.
A create that fails: before creating again, look for the ticket among the newest issues
(`gh issue list --state all --limit 20 --json number,title,body`, matching the body's id and parent lines),
twice a few seconds apart, since the list can trail a create.
```

O corpo mantém as linhas `id` e `parent` do frontmatter (só cinco são removidas), então a busca não
precisa de marcador. Avalie em `/tmp/bmad-sandbox-project` (`git init`, fora de qualquer
repositório): instale o preview conforme `docs/plan/help-test-v7-previews.md:29-32`, registre o
SHA, `bmad setup` com o starter do GitHub e `repo = "JakeSelby/bmad-ticketing-sandbox"`. Árvore:
um épico, duas histórias, história 2 `after` história 1; force a falha definindo o `tracker_id` do
épico como 999999. Um teste é duas execuções idênticas do Claude Code sem interface, pedindo para
publicar o épico; conte issues por ticket, depois `gh issue delete` nelas. Três testes com o verbo
atual, três com o corrigido em `_bmad/custom/ticketing-store-config.toml`. Registre o modelo e a
versão do gh.

## Passo 5 — Abrir o PR 1

Commit `fix(ticketing): make GitHub publishing safe to rerun` com o trailer Co-Authored-By; rode o
gate na `HEAD`. Mostre ao Jake o corpo com números reais; sinalize as linhas em primeira pessoa;
nenhum travessão longo.

```markdown
## What
Publishing to GitHub can now be rerun without filing a ticket twice. The issue is created with content only, its number goes into the ticket file straight away, and parent, blocked-by and milestone are added afterwards when missing.

## Why
Fixes #<bug>. `gh issue create` applies `--parent` and `--blocked-by` after the issue exists, and when that step fails it exits non-zero without printing the url, so `tracker_id` is never written and the next publish creates the issue again.

## How
- `write` creates with title, body, labels and milestone, then mirrors `tracker_id` and `remote`.
- Relations go on with `gh issue edit`, skipping any that `gh issue view` already shows.
- A failed create is looked up among the newest issues, twice, before any retry.

## Testing
With a forced relation failure, publishing one epic twice left <n> issues per ticket before this change and one after, in three runs each (gh <version>, <model>).

I found this comparing the preview with a BMad-to-GitHub sync I built independently for my agent harness (https://github.com/JakeSelby/agent-harness), which tracks 433 issues.
```

Depois da aprovação: `git push -u origin ticketing-gh-publish-rerun`;
`gh pr create --repo bmad-code-org/BMAD-METHOD --base dev --head JakeSelby:ticketing-gh-publish-rerun --title "<subject>" --body-file <approved body>`.
CodeRabbit e Greptile vão comentar: verifique cada um contra o código, depois redija uma resposta
ou uma correção para a aprovação do Jake.

## Passo 6 — Pitch da reconciliação

Template de pedido de funcionalidade (Describe your idea / Why is this needed? / How should it
work? / PR / Additional context). Rascunho:

```markdown
Title: v7 preview: reconcile the ticket tree with the tracker

Describe your idea: a read-only check that compares the ticket tree with the tracker and lists what drifted.

Why is this needed? `query` reads one ticket, a container's children or a word search. Nothing shows a tracker item that is missing, closed on one side only, reparented, blocked by something `after` no longer names, filed twice, or filed outside BMad with no parent. With hooks not integrated yet, that drift builds up between runs.

How should it work? `tickets.py reconcile <folder> --tracker <listing>`. Each store's `query` verb gains a sentence on producing the listing (number, state, parent, blocked-by, labels, and the id and parent lines from the body), and `tickets.py` compares it with the tree and prints JSON grouped by kind of drift. Fixing stays with `write` and the user.

PR: under 400 lines with tests, once the shape suits you.

Additional context: I run an independent BMad-to-GitHub sync in my agent harness (https://github.com/JakeSelby/agent-harness) that makes this check daily across 433 issues. It also taught me that ids handed out on two branches at once collide, so it surveys every branch before allocating one; I can propose that separately.
```

Introdução no Discord para o Jake postar em https://discord.gg/gk8jAdXWmj:

```markdown
Hi, I'm Jake. I run BMad against GitHub Issues through a sync I built independently for my agent harness (https://github.com/JakeSelby/agent-harness), and I'd rather put what it taught me into the ticketing preview than keep a parallel tool. I filed #<bug> with a small fix in #<pr>, and #<feature> proposes a reconcile check between the tree and the tracker: would that shape work for you before I write it?
```

Registre a data e o resumo de qualquer resposta em nosso épico. Um sim inicia uma nova rodada de
planejamento para a construção: na `dev` depois que a #2944 mesclar, seis classes de desvio
(faltando no rastreador, desconhecido da árvore, registrado duas vezes, discordância
aberto/fechado, discordância de pai, blocked-by contra `after`), um fixture para cada em
`scripts/tests/test_tickets.py`, no máximo 400 linhas.

## Passo 7 — Registrar nosso épico de adoção

Em um worktree cortado de um `origin/main` recém-buscado:
`harness worktree create bmad-ticketing-adoption --base origin/main`. Registre com
`scripts/bmad_issue_sync.py new`; ele relata "filed but not reserved" por atraso da listagem toda
vez, então rode `reserve --issue N --kind epic` na hora. Rótulo `type::epic`; sem marco de
lançamento. O corpo carrega os seis pontos da questão 2 e o portão:

1. bmad-build e sprint planning leem a árvore de tickets (as quatro partes da #2944 mescladas).
2. Um lançamento com tag do BMad entrega a skill de ticketing pelo npm.
3. U1, ou equivalente, está nesse lançamento.
4. Uma verificação de reconciliação está nele, ou mantemos `bmad_issue_sync.py audit --live` ao
   lado dela.
5. Um spike, planejado quando 1 a 4 valerem, reaponta nossos três checks e mantém os IDs do AH
   localizáveis.

O PR que carrega o arquivo do épico não fecha nada (o épico continua aberto), então precisa de sua
própria issue de chore: registre-a da mesma forma e coloque `Closes #<chore>` no corpo. Se `main`
recriar o épico sob outro ID, use o de `main` e rode a auditoria de novo.

## Regras de trabalho para o agente que implementa

- **Coordenação:** uma nova sessão é dona deste trabalho. Antes de criar qualquer coisa, verifique
  se já existe um fork, um repositório sandbox, ou issues e PRs de JakeSelby no upstream. Pesquisa
  anterior está em `/tmp/carve-715/`.
- **Paradas:** uma, antes de a primeira issue ou PR ser criado, mostrando todo rascunho de uma vez
  (issue de bug, corpo do PR 1, issue de funcionalidade, introdução no Discord, épico e issues de
  chore nossos, corpo do nosso PR) com placeholders `#<n>` preenchidos à medida que os itens são
  criados. Pare de outra forma só para uma decisão, um gate que falhou e você não consegue
  corrigir, ou um `trust_check` em L1 ou L2.
- **Skills, em ordem:** `upstream-contribution` (passos 2-6), `worktree-per-agent` (passos 3 e 7),
  um agente `builder` para o passo 4 (gate e commit local, nunca um push), `land` depois que nosso
  PR mesclar, `handoff` no final.
- **Governança:** `trust_check` antes de `gh repo create`, `gh repo fork`, cada `gh issue create`,
  commit, push e `gh pr create`, e `bmad_issue_sync.py new`; `action_log` depois de cada um.
- **Voltado para fora:** toda issue, corpo de PR, linha do Discord e resposta de bot é texto exato
  com a aprovação do Jake por item, sem travessão longo, linhas em primeira pessoa sinalizadas.
- **Portão do upstream:** `uv sync --frozen && uv run --frozen pre-commit run --all-files --show-diff-on-failure`;
  o CI adiciona windows-latest. **Nosso portão:**
  `python3 bin/harness lint && python3 -m unittest discover -s tests`, lido pelo código de saída.

## Evidência e verificação

- **Lido diretamente:** `config/gh-ticketing.toml`, `SKILL.md`, `references/board.md`,
  `references/store-setup.md`, `assets/story-template.md` do upstream, `CONTRIBUTING.md:32-95`, o
  template do PR, os ids do hook de pre-commit; código-fonte do gh v2.101.0
  `create.go:455-545`, `queries_issue.go:538-562,677-689`, `edit.go:265-274`; notas de lançamento
  do gh 2.94.0; dist-tags do npm; contagens de `issue-map.json`.
- **De gatherers e dos resumos da outra sessão, não relido linha por linha:** as referências de
  linha da nossa sincronização, os trechos de armazenamento da #2944, citações da #666 e da #1668,
  o histórico de merge de PRs externos, as limitações declaradas do preview.
- **Realidade de merge:** nenhum PR de ticketing externo foi mesclado; cinco de um contribuidor
  abertos em 24/09, nenhum ainda revisado por uma pessoa; merges externos até hoje levaram uma
  mediana de cerca de dez dias.
- **Ainda não verificado:** a duplicata em um repositório ao vivo e a reescrita de rótulo (passo
  1); se `--add-blocked-by` dá erro numa relação já existente; se `tickets.py find` consegue
  resolver um apelido.

## Adiado, e por quê

- **Construir a reconciliação ou ids seguros entre branches:** espera o sim de um mantenedor;
  depois sua própria rodada de planejamento.
- **O spike e a migração:** esperam as condições de portão 1 a 4.
- **Portar `bmad_issue_sync.py` ou entregá-lo como um módulo:** falha na regra das 800 linhas, lê
  nosso layout v6, compete com o armazenamento do mantenedor; um módulo da comunidade,
  `bmad-issue-tracking`, já existe.
