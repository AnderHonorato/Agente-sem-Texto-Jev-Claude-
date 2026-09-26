# Variante de voz `concise` com formatos de resposta escolhidos pela finalidade

> **Veredito.** Adiciona uma voz `concise` com seis formatos de resposta escolhidos pela finalidade e
> sete regras que toda resposta mantém, tudo em prosa simples. Selecioná-la define o estilo nativo
> `Concise` do Claude Code, envia a mesma postura para o Codex, e remove os templates de resposta
> concorrentes do texto sempre carregado.
> **Esforço** ~2 dias · **Risco** médio, o conjunto sempre carregado está em 199 de 200 linhas ·
> **Raio de impacto** formato de resposta sob toda voz, e briefs de subagente sem teto

## Em resumo

- **Resultado** — `voice: concise` pode ser selecionada, e as respostas assumem o formato que sua
  finalidade pede, tanto no Claude Code quanto no Codex.
- **Abordagem** — um mapa de estilos nativos ao lado do registro de arquivos em `bin/harness`, um
  novo arquivo de postura, as linhas de template concorrentes reescritas, e dois detectores
  condicionados (gated).
- **Toca** — só este repositório, cerca de 40 arquivos: harness, arquivos de voz, três regras, dois
  hooks, dois workflows, duas skills, avisos, listagens, testes.
- **Novas dependências** — Nenhuma. O texto é adaptado de openai/codex (Apache-2.0),
  openai/openai-cookbook (MIT) e garrytan/gstack (MIT).
- **Fora de escopo** — mudar a voz padrão, `model_verbosity` do Codex, a reescrita em linguagem
  simples das outras regras, a correção do estilo Scannable, o humanizer.
- **Teste de saída** — `harness lint` está limpo, `unittest discover -s tests` passa, e um sync
  mostra `Concise` mais a postura no `AGENTS.md` do Codex.
- **Pergunta em aberto** — como encaixar cerca de 24 linhas a mais sempre carregadas sob um teto de
  200 linhas (decisão 2).

## Design do sistema

```text
config: voice = concise ──▶ harness sync
harness sync ─┬─▶ *mapa de estilo nativo ── "Concise" ──▶ Claude settings.json
              ├─▶ *voice/concise.md ──▶ regras de postura do Claude Code
              │                      └─ mesmo texto ──▶ Codex AGENTS.md
              └─▶ *regras, workflows, skills: templates de resposta removidos
*brief-guard ── brief + formato de retorno ──▶ subagente
cada resposta final ── rótulos de esqueleto, cabeçalho primeiro ──▶ *rule-detectors
```

`*` marca um nó novo ou alterado. O lado do Codex não precisa de mudança de código, porque
`render_codex_agents` já emite a postura selecionada.

## Passos

1. **[Issue de entrega e arquivo de história](#passo-1--issue-de-entrega-e-arquivo-de-história)** —
   `scripts/bmad_issue_sync.py new`, tipo história, marco `v0.14.0`.
   *Saída:* `_bmad-output/issue-map.json` mapeia a issue, e o arquivo de história existe.
2. **[Escrever a postura e medir o orçamento](#passo-2--escrever-a-postura-e-medir-o-orçamento)** —
   `primitives/stances/voice/concise.md`, depois lint.
   *Saída:* a linha `context:` de `python3 bin/harness lint` é registrada no arquivo de história, e
   a resposta da decisão 2 cobre o excedente.
3. **[Ligar a variante ao estilo Concise](#passo-3--ligar-a-variante-ao-estilo-concise)** —
   `bin/harness`, `claude/OWNERSHIP.json`, dois arquivos de teste.
   *Saída:* `python3 -m unittest tests.test_voice_output_style tests.test_voice_stance` passa.
4. **[Remover os templates concorrentes](#passo-4--remover-os-templates-concorrentes)** — três
   regras, `brief-guard.py`, `/research`, `/build`, duas skills.
   *Saída:* `grep -rn "What changed" primitives/rules primitives/workflows policy/hooks` não
   imprime nada, e os testes de brief passam.
5. **[Reescrever answer-card e scannable em prosa simples](#passo-5--reescrever-answer-card-e-scannable-em-prosa-simples)**
   — as duas posturas e o texto do Scannable.
   *Saída:* `grep -n "arrow list" primitives/presentation/scannable.md` não imprime nada, e os
   testes de voz e detector passam.
6. **[Dois detectores condicionados a concise](#passo-6--dois-detectores-condicionados-a-concise)**
   — `policy/hooks/rule-detectors.py`, seus testes e o corpus rotulado.
   *Saída:* `python3 -m unittest tests.test_rule_detectors` e
   `python3 scripts/detector_corpus.py --floor 0.9` passam.
7. **[Atribuição e listagens](#passo-7--atribuição-e-listagens)** — avisos, `third-party.json`,
   `product.json`, README, docs, `changelog.d`.
   *Saída:* `python3 bin/harness lint` e `python3 scripts/cost_bench.py static --check` passam.
8. **[Gates, verificação de sync e acompanhamentos](#passo-8--gates-verificação-de-sync-e-acompanhamentos)**
   — todo comando do CI, um sync de home descartável, três issues de acompanhamento.
   *Saída:* `python3 -m unittest discover -s tests` passa, e o sync mostra `outputStyle` `Concise`
   e a postura no `AGENTS.md` do Codex.

## Decisões para o revisor

> **1. As instalações novas devem manter `scannable` como voz padrão?**
> *Recomendação* sim, para esta mudança. `docs/compatibility-policy.md` trata o comportamento
> efetivo de um padrão alterado como uma mudança quebrando compatibilidade a menos que seja
> opt-in, então meça `concise` primeiro e reavalie depois.
> *Alternativa* tornar `concise` o padrão agora. Toda instalação nova ganha os formatos desde o
> primeiro dia, mas sob essa política isso é uma mudança de versão major.

> **2. Como a postura é paga em texto sempre carregado?**
> *Recomendação* elevar o teto de 200 linhas para 225. Se o passo 2 também encontrar o teto de
> tokens excedido, eleve-o pelo tamanho medido da postura e cite esta issue. A postura precisa
> alcançar toda resposta, e uma skill não consegue fazer isso.
> *Alternativa* manter os dois tetos. Cortar a postura para 12 linhas sem exemplos, e dobrar
> `cache-hygiene.md` para dentro da postura `cost`, já que `docs/preferences.md` já chama essa
> regra de mal colocada.

> **3. A correção das instruções de codificação do Scannable deve entrar antes desta mudança?**
> *Recomendação* sim, como seu próprio pull request de bug. `scannable` é o padrão de fábrica,
> então instalações padrão rodam hoje sem as instruções de codificação do Claude Code, e o passo 5
> edita o mesmo estilo.
> *Alternativa* registrar agora e entrar depois. As duas revisões ficam independentes, mas o
> defeito continua vivo por mais tempo e este branch precisa de um rebase.

> **4. Quais briefs o `brief-guard` deve dar o formato de retorno?**
> *Recomendação* só briefs sem limite de retorno definido, que é o caminho já existente do hook.
> Sua paridade com o detector de teto continua exata, e a regra ainda pede ao orquestrador para
> escrever um formato.
> *Alternativa* todo brief sem uma frase de formato. Briefs com teto também ganham o formato, mas
> a maioria dos disparos muda e o hook precisa de um segundo padrão para reconhecer um formato.

> **5. Onde mora o aviso do texto adaptado?**
> *Recomendação* em `THIRD_PARTY_NOTICES.md` e `third-party.json`, nomeando o arquivo de postura e
> o que mudou. Qualquer linha dentro da postura é paga em todo turno.
> *Alternativa* adicionar também um comentário de uma linha no rodapé da postura. Essa é a leitura
> mais literal do aviso de arquivo modificado da Apache-2.0, e custa uma linha sempre carregada.

## Riscos

- **Concise está ausente no cliente Linux fixado (2.1.278), ou é ignorado em sessões de bridge e
  do Agent SDK.** A postura ainda carrega os formatos. Declare o piso do cliente no changelog e em
  `docs/compatibility.md`.
- **Pontuação de corpus sem gate empurra `voice/scaffold-leak` abaixo do piso de 0,9.** Rotule as
  linhas de esqueleto já presentes em ambos os corpora como positivas em vez de estreitar o padrão.
- **Uma reescrita derruba "no tables" ou "at most one table", que a aceitação nativa lê da
  postura.** Mantenha as duas frases, e fixe-as em `tests/test_voice_stance.py`.

---

# Anexo

Tudo abaixo é para o agente que implementa. Os caminhos são relativos à raiz do repositório.

## Passo 1 — Issue de entrega e arquivo de história

- Trabalhe em um worktree gerenciado (`harness worktree create`), nunca em um checkout irmão.
- Registre a issue:
  `python3 scripts/bmad_issue_sync.py new --title "feat(voice): concise voice with reply shapes chosen by purpose" --kind story --body-file <body.md> --milestone v0.14.0`.
  - O corpo linka este plano, lista os passos, e não nomeia nenhuma pessoa.
  - O marco é `v0.14.0` porque adicionar um primitivo com padrão inalterado é um lançamento minor
    sob `docs/compatibility-policy.md:37-38`.
  - Se o marco ainda não existir, crie-o (`AGENTS.md:66-67`).
- Conforme `docs/bmad-governance.md:33-37`, `new` reserva o ID do BMad no mesmo passo. O brief
  também pediu `reserve --issue N`, mas rode
  `python3 scripts/bmad_issue_sync.py reserve --issue N --kind story` somente se
  `_bmad-output/issue-map.json` não mapear N depois.
- O arquivo de história em `_bmad-output/implementation-artifacts/<BMad ID>.md` precisa das seções
  que `bmad_issue_sync.py:44` espera para uma história: Story, Acceptance criteria, Design, Tasks,
  Dev notes. Os critérios de aceitação são os testes de saída do cartão.
- Se a decisão 3 for respondida "primeiro", registre o bug do Scannable agora (texto no passo 8) e
  faça-o entrar antes do passo 5.

## Passo 2 — Escrever a postura e medir o orçamento

- **Linha de base, contada por número de linhas durante o planejamento:**
  - `claude/CLAUDE.md`: 10 linhas.
  - `claude/rules/`: 112 linhas em 10 arquivos.
  - A variante mais longa de cada uma das 9 dimensões de postura: 77 linhas, com
    `voice/answer-card.md` contado em 9.
  - Total: 199 linhas contra `ALWAYS_LOADED_CAP = 200` (`bin/harness:180`).
  - O teto de tokens é `12607 // 3 = 4202` (`bin/harness:173-174`), fixado por
    `tests/test_harness.py:420-424`. O total de tokens atual não foi medido durante o planejamento.
- Escreva `primitives/stances/voice/concise.md` a partir do rascunho abaixo. Tem 33 linhas, então
  substitui uma variante mais longa de 9 linhas e adiciona cerca de 24 linhas e aproximadamente 600
  tokens (a quatro caracteres por token).
- As reescritas do passo 4 substituem linhas uma a uma, então liberam quase nada. Espere cerca de
  223 linhas antes de aplicar a decisão 2.
- Rode `python3 bin/harness lint` e copie sua linha `context:` para as Dev notes do arquivo de
  história. Pare se a decisão 2 não estiver respondida e o lint estiver acima de qualquer teto.
- Sonda de estilo: rode `claude --version`. Com `"outputStyle": "Concise"` definido nas
  configurações de um home descartável, confirme que `/output-style` lista `Concise` nesse
  cliente. Registre a versão nas Dev notes.
  - O estilo foi verificado presente na 2.1.280.
  - A rodada de qualificação Linux registrou a 2.1.278 (`docs/compatibility.md:199-200`).

## Passo 3 — Ligar a variante ao estilo Concise

- **`bin/harness`**
  - Ao lado de `harness_output_styles()` (linha 439), adicione
    `BUILTIN_OUTPUT_STYLES = {"concise": "Concise"}`, com um comentário de uma linha dizendo que
    isso seleciona o próprio estilo do Claude Code pelo nome e não copia nenhum texto.
  - Mude `voice_output_style` (linha 461) para retornar primeiro o estilo apoiado em arquivo, e
    depois o nativo.
  - Mantenha os estilos nativos fora de `harness_output_styles()` propriamente dita.
    `strip_claude_settings` remove todo nome que essa função retorna quando o diário não está
    registrado (linha 553), e um `Concise` próprio do usuário precisa sobreviver a uma desinstalação
    que precede o diário.
  - Atualize o docstring nas linhas 440-446, que chama o diretório de arquivos de "o registro
    inteiro".
- **Codex:** nenhuma mudança de código. `render_codex_agents` já escreve o corpo da postura
  selecionada (linhas 1024-1025), e o acréscimo de apresentação continua ligado a `scannable`
  (linhas 1026-1028).
- **`claude/OWNERSHIP.json`** `output_style` e **`docs/settings-ownership.md:11-17`:** uma variante
  mapeada para um estilo nativo do Claude Code (hoje só `concise`) instala esse estilo pelo nome. A
  posse do diário não muda.
- **`tests/test_voice_output_style.py`**
  - `EXPECTED` ganha `"concise": "Concise"`.
  - `test_the_style_name_is_read_from_the_style_file` verifica apenas estilos apoiados em arquivo.
  - `RuntimeAgreementTests` tem uma premissa falsa sob `concise`: o Claude instala um estilo, mas o
    Codex não recebe arquivo de apresentação. Reformule como "o Codex acrescenta a apresentação
    Scannable exatamente quando a variante é `scannable`", e adicione um teste de que o texto do
    Codex sob `concise` contém o corpo da postura.
  - Adicione testes de preservação: um `Concise` próprio do usuário sobrevive a um sync em `off`, e
    sobrevive a `strip_claude_settings(live, TEMPLATE, harness.UNRECORDED)`.
- **`tests/test_voice_stance.py`**
  - Quatro variantes.
  - `LONGEST_VARIANT` definido para a contagem de linhas final de `concise.md`.
  - Verifique frases de formato em texto normalizado por espaço em branco: "no tables" em
    answer-card e concise, "at most one table" em scannable, "Concise wins" em concise.
- **`tests/test_native_acceptance_stance_switch.py:74`:** o sync falso mapeia só `scannable`.
  Adicione `concise` → `Concise` para que o fixture combine com um sync real.

## Passo 4 — Remover os templates concorrentes

- **`primitives/rules/voice-and-format.md`:** substitua as linhas 3-4 pelo rascunho abaixo.
  `tests/test_voice_stance.py:93-98` precisa de 6 linhas ou menos, a frase "subagent brief", e
  nenhum "Scannable".
- **`policy/hooks/brief-guard.py:49-50`** `BOUND` torna-se:
  `"\n\nReturn at most 400 words: the result in your first sentence, then only the findings that change a decision, in plain sentences or short bullets with no section labels. Write anything longer to a file and return its path, not its contents."`
  Mantenha o prefixo "Return at most 400 words" para que `WORD_CAP_RE` continue combinando. Espelhe
  a mudança em `tests/test_brief_budget.py:34`, e rode `tests.test_brief_guard` para a verificação
  de paridade.
- **`primitives/rules/transcript-hygiene.md:8-9`:** "Start with the verdict; thinking summaries
  stay." torna-se "Shape the reply by the `voice` stance; thinking summaries stay."
- **`primitives/skills/transcript-hygiene/SKILL.md:44`:** "Start with the verdict; the reader does
  not need the machinery." torna-se "Shape the reply by the `voice` stance; the reader does not
  need the machinery."
- **`primitives/rules/decisions-and-plans.md:3-6`:** substitua pelo rascunho abaixo, ainda com 4
  linhas.
- **`primitives/workflows/research.md:33-36`**, alinhado ao formato Brief:
  "Report as a brief: two or three sentences of bottom line, then three to five findings with the
  numbers behind them and what they mean for the reader. Link the rest: end with the scratchpad
  file paths the band workers wrote and the worker ids `harness role status` will show, one per
  line. An isolated `gatherer` writes nothing itself: save its returned detail to a scratchpad file
  yourself before you synthesize."
- **`primitives/workflows/build.md:36-37`**, alinhado ao formato Report:
  "Report the outcome in one sentence with the pull request URL, then at most five bullets on what
  the reader must know: a decision taken on their behalf, a step left unfinished, a test that had
  to be skipped. Give the gate result in one line, and its failing output in full if it failed."
- **Cópias geradas:** rode `python3 bin/harness generate` e faça commit dos regenerados
  `claude/commands/research.md` e `build.md`. Nunca edite esses dois arquivos manualmente.
- **`primitives/skills/plan-authoring/SKILL.md`, "Justificativa realocada das regras residentes":**
  - Sob `### Voice and output format`, coloque primeiro uma nota de substituição marcada, depois a
    justificativa atual (rascunhos abaixo).
  - Mantenha os parágrafos de arquivos de plano, repintura de editor e postagens em seu nome. No
    parágrafo de arquivos de plano, mude "verdict-first sections, bolded lead-ins" para "the
    selected voice".
  - Sob `### Presenting decisions`, adicione uma linha de emenda datada em vez de reescrever o
    parágrafo.
  - Parafraseie o ponto da Anthropic sobre formatação de prompt e linke a página da documentação.
    Não a cite: a revisão de biblioteca externa classifica a documentação da Anthropic como
    inspiração apenas, não para texto literal.

## Passo 5 — Reescrever answer-card e scannable em prosa simples

- Reescreva `primitives/stances/voice/answer-card.md` e `primitives/stances/voice/scannable.md` a
  partir dos rascunhos abaixo. Os contratos não mudam.
- Reescreva `primitives/presentation/scannable.md` (servido como
  `claude/output-styles/scannable.md`) como prosa com menos rótulos em negrito, e apague "A causal
  chain is an arrow list" da regra 3 (linha 25). Mantenha tudo a seguir:
  - o frontmatter `name: Scannable`, que `harness_output_styles` lê;
  - toda entrada de `BANNED_OPENERS` e `BANNED_CLOSER`
    (`tests/test_rule_detectors.py:375-379`);
  - a frase "at most one table".
- Não adicione `keep-coding-instructions` aqui. Isso é o bug separado (decisão 3).
- `scripts/native_acceptance.py:1110-1126` procura por "no tables" ou "at most one table" no texto
  de voz resolvido. As duas frases precisam sobreviver.

## Passo 6 — Dois detectores condicionados a concise

- **Gate:** `_VOICE_CONCISE = ("voice", ("concise",))` ao lado de `_VOICE_ON`
  (`rule-detectors.py:385`). Os dois detectores usam a regra `voice-and-format` e o evento
  `assistant-final`, e relatam acertos com `hit(event, tool_use_id=False)`, como `second_table`.
- **`voice/scaffold-leak`**
  - Um acerto por mensagem final.
  - Varra as linhas de `_unmarked(text)` que estão fora de blocos de código (`_fenced_lines` mostra
    a regra de bloco).
  - Um rótulo é uma linha que, depois de um marcador de lista opcional, marcas de cabeçalho e
    negrito ou itálico, começa com um de: What changed, What you need to know, What you need to
    do, Still open, Verification, Why, Catch ou The catch, Alternatives. Precisa ser seguido por
    dois-pontos, um fechamento de ênfase, ou o fim da linha.
  - Também sinalize Fixed, Partially fixed, Not fixed ou Unverified quando usados como rótulo,
    ou seja, envolvidos em negrito ou no início de linha com dois-pontos.
  - Menções entre crases ou entre aspas não contam.
- **`voice/heading-first`:** um acerto quando a primeira linha não vazia do texto final combina com
  `^\s{0,3}#{1,6}\s`.
- **`tests/test_rule_detectors.py`**
  - Adicione um caso que acerta e um caso limpo por id em `CASES`.
  - Defina o corpus `STANCES` (linha 23) para `voice: concise`, o que liga todo detector de voz.
  - Adicione `StanceTests` verificando que os dois novos detectores ficam silenciosos sob
    `scannable`, `answer-card` e `off`.
- **Corpus:** adicione sessões em `tests/fixtures/detector-corpus/build_sessions.py` com rótulos
  `fire`/`near` em `labels.yaml`, seguindo `voice-openers.jsonl` (linha 150).
  `scripts/detector_corpus.py` pontua sem gates (linhas 38-45), então as linhas já existentes que
  contêm o esqueleto precisam ser rotuladas como positivas para `voice/scaffold-leak`.
- **Contagens de detectores publicadas:** dezessete torna-se dezenove em `product.json:177`,
  `README.md:80`, `docs/field-scan.md:166` e `docs/caught-in-the-act.md:79`. Atualize também
  `tests/test_doc_figures_derive_from_code.py:91` (11 torna-se 13) e
  `scripts/detector_corpus.py:5` ("eleven" torna-se "thirteen").
- **`docs/usage.md:775-776`:** adicione uma linha para cada novo id de detector com seu
  significado em uma linha.

## Passo 7 — Atribuição e listagens

- Rode a skill `licensing-review` para as três fontes. Fixe cada uma no commit upstream lido no
  momento da compilação, e verifique se `openai/codex` tem um arquivo `NOTICE` nesse commit. Se
  tiver, seu conteúdo vai para `THIRD_PARTY_NOTICES` (Apache-2.0 §4(d)).
- **`THIRD_PARTY_NOTICES.md`:** adicione uma seção no estilo do design-loop (rascunho abaixo).
- **`THIRD_PARTY_NOTICES`:** adicione os avisos MIT de openai/openai-cookbook e garrytan/gstack com
  suas linhas de copyright, e o texto da Apache-2.0 para openai/codex.
- **`third-party.json`:** anexe um componente por fonte com estes campos:
  - `name`, `version` (o SHA do commit), `source`;
  - `artifact_url` (o arquivo bruto nesse SHA) e `sha256` desse arquivo;
  - `license`, `rightsholder`, `modifications`;
  - `runtime_dependencies: []`, `notice: "THIRD_PARTY_NOTICES"`,
    `file: "primitives/stances/voice/concise.md"`.

  Anexe sem reordenar, porque `tests/test_reconciliation.py:220-223` lê `components[0]`.
- Não crie um `ATTRIBUTION.md` sob `primitives/stances/voice/`. Todo arquivo `.md` ali se torna uma
  variante selecionável (`VariantsTests`, `VoiceStanceTests`).
- **Listagens:**
  - `product.json:130` e `README.md:63`: "Choose concise, answer-card or scannable. Same content,
    shaped for how you read." As duas linhas precisam combinar.
  - `README.md:125`: adicione `concise` à linha de formato de resposta.
  - `docs/preferences.md:52`: adicione `concise` à linha de `voice`. Mantenha o padrão `scannable`.
  - `docs/preferences.md:256-266`: adicione uma frase sobre `concise` (seis formatos, seleciona o
    estilo nativo Concise no Claude Code, só o texto da postura no Codex), e corrija "the only
    variant that carries presentation material" para cobrir o estilo nativo.
  - `docs/preferences.md:296-297`: `voice-and-format.md` não fixa mais o template do Scannable,
    então atualize essa frase.
- **`changelog.d/<N>.added.md`:** "Added a `concise` voice variant. It picks each reply's shape by
  what the reply is for — a one-line done message, a short answer, a report, a decision, a brief
  or a deep dive — and holds every reply to seven rules. On Claude Code it also selects the
  built-in Concise output style, available from Claude Code <verified version>; Codex receives the
  same stance text through AGENTS.md. The default voice is unchanged. The What-changed reply
  template no longer appears in the always-loaded rules, and two new detectors count template
  labels and heading-first replies under this voice."
- **Orçamento:** aplique a decisão 2 em `bin/harness:173-180`, e em `docs/how-it-works.md:119` se o
  teto de tokens mudar. Mantenha a citação de `#430` e da documentação que
  `tests/test_harness.py:427-431` exige. Se `cost_bench.py static --check` relatar crescimento
  acima de 5%, adicione uma entrada em `benchmarks/allow.json` com `harness_version`, `est_tokens`
  e um motivo (`docs/benchmarks.md:30`). Não rode `static --write` no meio do ciclo; isso acontece
  no lançamento.

## Passo 8 — Gates, verificação de sync e acompanhamentos

- **Gates:** rode os comandos que `.github/workflows/ci.yml` roda, nesta ordem:
  - `python3 bin/harness lint`
  - `python3 scripts/smoke_tier.py --skip credentials`
  - `python3 scripts/detector_corpus.py --floor 0.9`
  - `python3 -m unittest discover -s tests -v`
  - `python3 scripts/cost_bench.py static --check`
  - `python3 scripts/bmad_issue_sync.py audit`
  - um `bin/harness sync --dry-run` contra `config.example.json` em um `HOME` descartável.
- **Verificação de sync do Concise:**
  ```sh
  export HOME="$(mktemp -d)"
  mkdir -p "$HOME/.config/agent-harness"
  printf '{"stances":{"voice":"concise"}}' > "$HOME/.config/agent-harness/config.json"
  python3 bin/harness sync --dry-run
  ```
  Procure por `outputStyle` `Concise` na saída. Se o dry run imprime o valor das configurações e se
  o corpo do `AGENTS.md` foi verificado não foi checado durante o planejamento. Se não imprimir
  nenhum dos dois, rode os mesmos comandos sem `--dry-run` (o home é descartável), depois
  `grep outputStyle "$HOME/.claude/settings.json"` e
  `grep -c "Voice: concise" "$HOME/.codex/AGENTS.md"`.
- **Issues de acompanhamento:** registre com `bmad_issue_sync.py new`; não construa nenhuma delas
  aqui.
  - **História:** "Rewrite the always-loaded rules in plain language". Menos rótulos em negrito, e
    exemplos positivos em vez de proibições. Espera-se que devolva linhas sempre carregadas.
  - **Bug:** "Scannable output style drops Claude Code's coding instructions".
    `claude/output-styles/scannable.md` não tem `keep-coding-instructions: true`, e `scannable` é a
    voz padrão. Pule esta se o passo 1 já a tiver registrado.
  - **Spike:** "Licence review of the humanizer skill for drafts". O repositório é MIT, mas sua
    lista de padrões deriva de uma página CC BY-SA, e se o texto copiado carrega termos
    share-alike ainda não está resolvido.
- Abra o pull request com `Closes #N` e a linha de geração.

## Depois do merge, fora do repositório

- O revisor troca sua própria configuração para `concise`
  (`bin/harness config set stances.voice concise`), roda `bin/harness sync`, e inicia uma nova
  sessão.
- O revisor agenda uma reexecução semanal de seu índice privado de histórico de respostas e
  compara a mistura de formatos e o tamanho das respostas contra sua linha de base. A decisão 1
  espera por essa medida. O índice e suas saídas ficam fora deste repositório.

## Rascunho: a postura concise

```markdown
# Voice: concise

Write each reply for a reader who will act on it, and let the shape of the answer match the shape
of the problem: pick the shape by what the reply is for, and keep it as short as that shape
allows. On Claude Code the built-in Concise output style is active too; where the two differ,
Concise wins.

A done message is one line, with the link or identifier the reader needs. An answer puts the
answer in its first sentence and ends within three, with a caveat only if it changes what the
reader would do. A report gives the outcome in one sentence, then at most five bullets that
change what the reader does next; the detail stays in the pull request or a file, and if the
explanation outgrows the change, cut the explanation. A decision opens with the question and your
recommendation, then numbered options, one line each with its honest case, so the reader can
answer by number. A brief, for research, review or status, gives two or three sentences of
bottom line, three to five findings with their numbers, and what they mean for the reader, then
links the rest. Go deep only when the reader asks for depth or is deciding a design, and then
lead with a summary and use headers that state conclusions. A draft in the user's name is the
draft, then at most two lines of notes, under any personal voice profile.

Whatever the shape, the first sentence is the result, the answer, or your question, and anything
the reader must do or decide is in the first two lines. Use plain words: no coined terms,
internal IDs or file paths unless the reader will act on them, and give an issue number its
title. Add structure only when it is real: bullets for parallel items, headers only in a long
answer, no tables unless asked, and never an empty section. Skip the ritual: no status labels
unless you are reporting a fix, no recap, no narration of your steps, and no caveat or
alternatives unless there is one. After the answer, post nothing that does not change it; a
background task finishing is not news. Errors, failing output, security warnings and
confirmations of destructive actions keep their full detail.

A done message: "Merged #214, Fix the login redirect loop." A report that leads with the point:
"auth.ts:47 returns undefined when the session cookie expires, so users see a white screen. The
fix is a null check and a redirect to /login." Not: "I've identified a potential issue in the
authentication flow that may cause problems under certain conditions."
```

De onde vem cada trecho emprestado:

- "let the shape of the answer match the shape of the problem" vem do prompt do Codex CLI
  (Apache-2.0).
- Os limites em níveis (uma linha, até três frases, no máximo cinco marcadores) adaptam o
  `output_verbosity_spec` do cookbook (MIT).
- "If the explanation outgrows the change, cut the explanation" e o par de exemplos bom/ruim são
  adaptados da diretriz de voz do gstack (MIT).

Se a decisão 2 for para a alternativa, retire o último parágrafo e funda os formatos em um único
parágrafo de 5 linhas.

## Rascunhos: as regras, vozes e avisos editados

`primitives/rules/voice-and-format.md`:

```markdown
# Voice and output format

- **Every subagent brief carries its output shape**, since a subagent inherits no voice; the
  `brief-guard` hook appends one to a brief that states no return bound.
- **Deliverables and posts in the user's name honor any personal voice profile first**, then use the
  `voice` stance for layout; never imitate incidental typos. See `plan-authoring`.
```

`primitives/rules/decisions-and-plans.md`, primeiro marcador:

```markdown
- **No chooser widget for substantive decisions.** Flag the ask in the reply's first two lines; the
  numbered decision block may still close the message: each question stated unambiguously, the
  assessment, a recommendation with reasoning, the alternatives with their honest case. Batch
  them; choosers suit trivial forks whose labels carry full meaning.
```

`primitives/stances/voice/answer-card.md`:

```markdown
# Voice: answer card

Treat each reply as a decision, not a summary; where this and the output style differ, this wins.
When a file, plan or artifact holds the reasoning, link it once and do not argue it again.

Put the answer in the first line. Then say why, then the catch, then the alternatives with their
honest case, then what you need from the reader. Keep it to about 150 words and use no tables,
since they wrap unreadably on a narrow screen. Report status in the literal words Fixed, Partially
fixed, Not fixed or Unverified.
```

`primitives/stances/voice/scannable.md`:

```markdown
# Voice: scannable

The Scannable output style governs the main conversation; its text is in
`primitives/presentation/scannable.md`, and it does not reach subagents. When you relay what a
subagent found, rewrite it to that contract: the verdict first, action items under one heading,
paragraphs of at most three sentences, at most one table, and status in the literal words Fixed,
Partially fixed, Not fixed or Unverified.
```

SKILL.md do `plan-authoring`, a abertura de `### Voice and output format`:

```markdown
*Replaced on <merge date> by #N.* The paragraphs that stood here described the Scannable style's
What changed template and status words as the contract for relays and subagent briefs. The
`voice` stance now owns reply shape and the `brief-guard` hook appends the subagent return shape;
the earlier text is in this file's git history.

The selected `voice` variant governs the main conversation. On Claude Code, `concise` and
`scannable` also set an output style, which reaches only the main conversation and its forks;
other subagents run their own system prompt and inherit no voice. So a relayed report is
rewritten in the selected voice's shape, a finding that does not change what the reader does is
cut, and every subagent brief carries its return shape.

The voice files are written in plain prose with few bold labels because a prompt's formatting
tends to carry into the reply; see Anthropic's prompting guidance on controlling response format
(<link>).
```

A linha de emenda sob `### Presenting decisions`:

```markdown
*Amended on <merge date> by #N:* the block may still close the message, but the reply's first two
lines say that a decision is waiting.
```

Seção de `THIRD_PARTY_NOTICES.md`:

```markdown
## concise voice stance — adapted wording (Apache-2.0, MIT)

`primitives/stances/voice/concise.md` adapts short passages from three sources: from
[openai/codex](https://github.com/openai/codex) (Apache-2.0, commit <sha>), the Codex CLI
prompt's "let the shape of the answer match the shape of the problem"; from
[openai/openai-cookbook](https://github.com/openai/openai-cookbook) (MIT, commit <sha>), the tiered
length limits of `output_verbosity_spec` in the GPT-5.1 and GPT-5.2 prompting guides; and from
[garrytan/gstack](https://github.com/garrytan/gstack) (MIT, commit <sha>), the bounded closer and a
good/bad example pair from its voice directive. Modifications: reworded, shortened and merged into
six reply shapes and seven rules. Upstream licence texts are in `THIRD_PARTY_NOTICES`. Claude
Code's built-in Concise style is selected by name; none of its text is included.
```

## Evidência e verificação

- **Orçamento de linhas:** contado por arquivo durante o planejamento. `claude/CLAUDE.md` tem 10
  linhas, as regras 112, e as variantes de postura mais longas 77, totalizando 199. O total de
  tokens não foi medido.
- **Registro de estilos:** ele é orientado por arquivo (`bin/harness:439-464`), então um estilo
  nativo precisa de seu próprio mapa. A remoção de diário não registrado tira todo nome que o
  registro retorna (`bin/harness:553`).
- **Voz padrão:** é `scannable` (`config.example.json:19`, `tests/test_voice_stance.py:61-64`). É
  por isso que a ausência de `keep-coding-instructions` afeta instalações padrão, não só quem
  escolhe Scannable.
- **Detectores:**
  - Gates são declarados por detector (`policy/hooks/rule-detectors.py:384-406`).
  - O corpus roda sob um `STANCES` fixo (`tests/test_rule_detectors.py:23`) e é pontuado sem gates
    (`scripts/detector_corpus.py:38-45`).
  - As contagens de detectores são publicadas e testadas
    (`tests/test_doc_figures_derive_from_code.py:77-107`).
- **CI:** os gates estão em `.github/workflows/ci.yml:23-70`.
- **Não verificado:**
  - o que `sync --dry-run` imprime para `outputStyle` e `AGENTS.md`;
  - se o Concise existe na 2.1.278;
  - se `outputStyle` se aplica em sessões de bridge e do Agent SDK.

## Adiado, e por quê

- **O formato de relatório de `/review`** (`primitives/workflows/review.md:28`) **e o "pontuação e
  veredito primeiro" do juiz do design-loop** (`references/judge.md:40`) não estavam na lista
  desta mudança. Vão para o acompanhamento de linguagem simples.
- **Os limites de palavras nos retornos de subagente** em `transcript-hygiene.md` e `brief-guard`
  continuam em palavras, porque o detector de teto analisa contagens de palavras. A regra de
  orçamento sem palavras se aplica a respostas, não a retornos.
- **`model_verbosity` do Codex** foi descartado do escopo pelo revisor.
- **Mudar a voz padrão** espera pela decisão 1 e pela medida semanal.
