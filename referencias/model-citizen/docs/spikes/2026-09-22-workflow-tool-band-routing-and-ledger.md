# Spike: a ferramenta Workflow do Claude Code contorna o roteamento de banda, o confinamento e o ledger?

> **Resultado: parcialmente contornado, medido em 2026-09-22 no Claude Code 2.1.280.** As chamadas
> `agent()` de um script de workflow não produzem nenhuma chamada de ferramenta `Agent` na sessão,
> então `tier-agent-spawns`, `brief-guard` e a recusa de papel restrito em
> `lib/harness_core/lifecycle.py` nunca as veem: tanto o roteamento de banda quanto o confinamento
> de papel são contornados, e um script consegue rodar um papel do harness somente-leitura na
> própria sessão apenas nomeando-o. O ledger de uso não é contornado — `usage-log.py` registra
> todo agente de workflow — mas seu join de redirecionamento fica vazio para essas linhas, então a
> conformidade não pode ser medida a partir delas.

## Pergunta

Quando uma sessão roda a ferramenta `Workflow`, e o script chama
`agent(prompt, {label, phase, schema, model?})`, esses spawns passam pela cadeia `PreToolUse`
`Agent` do harness, e seus retornos caem em `~/.local/state/agent-harness/usage.jsonl` como linhas
de subagente atribuídas à sessão pai?

Três subperguntas, vindas da issue: `tier-agent-spawns` dispara sobre as chamadas `agent()` de um
script; um script consegue invocar `harness role run` para um papel confinado; `usage-log` atribui
os agentes de um script à sessão pai.

## Máquina

Apple M5 Pro, macOS 26.5 (Darwin 25.5.0). Claude Code 2.1.280, harness 0.12.0 instalado em escopo
de usuário com seus hooks ativos. Quatro execuções headless `claude -p`, $0,90 no total, cada uma
com menos de cinco segundos.

## Experimento

Um workflow de projeto em `/tmp/ah013/s540-probe/.claude/workflows/ah-spike-probe.js` com três
chamadas `agent()` em uma fase, rodado em modo headless a partir desse diretório:

```sh
claude -p "/ah-spike-probe" --model sonnet --allowedTools Workflow --output-format json
```

1. `agent('… ALPHA …', { label: 'bare' })` — não nomeia nada, o que através da ferramenta `Agent` é
   o que `tier-agent-spawns` reescreve para o worker de banda padrão da variante de custo.
2. `agent('harness-role: reviewer\n… BETA …', { label: 'marker' })` — um brief declarando um papel
   confinado, que `marker_role` recusa através da ferramenta `Agent`, seja como for que o spawn
   ocorra.
3. `agent('… GAMMA …', { label: 'named', agentType: 'reviewer' })` — nomeia o papel confinado
   diretamente, o que `constrained_role` recusa com a instrução de `harness role run`.

Três execuções adicionais sondaram o alcance do runtime: uma pediu a um agente para rodar `echo`,
uma pediu para rodar um `rm -rf` destrutivo contra um diretório descartável, e uma pediu para fazer
spawn de um subagente aninhado.

## Resultado medido

**As três chamadas rodaram.** A sondagem retornou `{"bare":"ALPHA","marked":"BETA","named":"GAMMA"}`.
Os sidecars de agente sob
`~/.claude/projects/<project>/<session>/subagents/workflows/wf_23583536-65e/` registram o que
rodou:

```json
{"agentType":"workflow-subagent","description":"bare","workflowPhase":"probe","spawnDepth":1}
{"agentType":"workflow-subagent","description":"marker","workflowPhase":"probe","spawnDepth":1}
{"agentType":"reviewer","description":"named","workflowPhase":"probe","spawnDepth":1}
```

**Não existe chamada de ferramenta `Agent` para nenhuma delas.** A transcrição pai da sessão de
sondagem carrega exatamente um bloco `tool_use`, `Workflow`. `decisions.jsonl` carrega zero linhas
para o id dessa sessão, então nenhum hook da cadeia rodou nos spawns, e nenhum rodou no
lançamento também: o template de configurações casa com `Bash`, `WebFetch`, `Agent` e
`Write|Edit`, e nada casa com `Workflow`.

**O script escolhe classe e esforço diretamente.** A própria assinatura do runtime, lida do
cliente instalado, é
`agent(prompt, opts?: {label?, phase?, schema?, model?, effort?, isolation?, agentType?})`.
`model`, `effort` e `agentType` são justamente o que as posturas `delegation` e `cost` existem para
decidir, e um script define os três sem nada no caminho.

**`agentType` resolve as definições de agente do usuário.** A terceira chamada rodou como
`reviewer` no modelo dessa definição em vez do `sonnet` da sessão, dentro da sessão, sem nenhum
worker isolado — exatamente o spawn que `role_deny` recusa através da ferramenta `Agent`.

**O ledger registrou tudo isso.** `usage-log.py` percorre `subagents/` recursivamente, então a
sessão de sondagem produziu uma linha de sessão e três linhas de subagente, cada uma com
`workflow: "wf_23583536-65e"`:

| agent_type | model | output | tool_use_id | rerouted | budget_output_tokens |
| --- | --- | --- | --- | --- | --- |
| workflow-subagent | claude-sonnet-5 | 702 | `""` | false | null |
| workflow-subagent | claude-sonnet-5 | 7 | `""` | false | null |
| reviewer | claude-opus-5-5 | 198 | `""` | false | 22000 |

O `.meta.json` de um agente de workflow não carrega nenhum `toolUseId` — o de um subagente
dentro da sessão carrega — então `mark_reroutes` não tem nada em que fazer join, e
`requested_type` e `rerouted` ficam vazios para toda linha assim. Ao longo do histórico desta
máquina, o ledger já carrega 1.657 linhas de workflow, todas em `spawn_depth` 1, todas com
`tool_use_id` vazio: 1.642 como `workflow-subagent` e 15 como `Explore` ou `Plan`, em modelos de
`claude-sonnet-5` até `claude-fable-5-1`, a classe que `tier-agent-spawns` recusa por solicitação,
em esforços de até `max`.

**Um script não consegue alcançar o confinamento, e não precisa disso.** O runtime não dá ao corpo
do script acesso a sistema de arquivos ou shell, e recusa `import()`, então nenhum script consegue
chamar `harness role run` sozinho; só um agente que ele faça spawn poderia, através de `Bash`. E
não tem motivo para isso: nomear o papel em `agentType` já consegue o papel sem confinamento.

**O fan-out tem um nível de profundidade.** Um agente ao qual se pediu para fazer spawn de um
subagente aninhado retornou `NO-AGENT-TOOL`; a definição embutida `workflow-subagent` proíbe a
ferramenta `Agent`. Isso combina com toda linha histórica que está em `spawn_depth` 1, e significa
que a cadeia `Agent` não tem uma segunda chance dentro de uma execução.

**Não medido:** se `PreToolUse` dispara sobre o próprio `Bash` de um agente de workflow. A
sondagem de `echo` foi pontuada em 0, o que o harness não registra, e a sondagem de `rm -rf` foi
recusada pelo próprio agente antes de chegar à ferramenta. A documentação afirma que "as chamadas
de ferramenta dos agentes recebem as mesmas verificações de permissão e o mesmo sandboxing que
qualquer outra chamada de ferramenta na sessão"; essa afirmação não foi testada aqui.

## Veredito

| Subpergunta | Resposta |
| --- | --- |
| `tier-agent-spawns` dispara sobre as chamadas `agent()` de um script? | **Não.** Contornado. |
| Um script consegue invocar `harness role run` para um papel confinado? | **Não** — e consegue rodar o papel sem confinamento em vez disso. Contornado. |
| `usage-log` atribui os agentes de um script à sessão pai? | **Sim.** Não contornado. |

Parcialmente contornado: roteamento e confinamento estão fora de alcance, a contabilidade está
intacta.

## Pendências que o código precisa

1. **Proteger o lançamento do `Workflow`.** O harness não consegue reescrever uma chamada
   `agent()` dentro de um script, mas o lançamento é uma chamada de ferramenta com a qual ele
   consegue casar. Um ramo `PreToolUse` `Workflow` deveria registrar o lançamento em
   `decisions.jsonl`, recusá-lo quando a postura `delegation` estiver `off`, e recusar um script
   cujo texto nomeia um papel confinado em `agentType`, com a mesma frase de `role_instruction`
   que a recusa do `Agent` carrega; essa mesma leitura é onde um `effort` ou `model` que um script
   nomeia poderia ser lido contra a variante de custo. A entrada da ferramenta é o próprio script,
   como `script` ou `scriptPath`, então a verificação é uma leitura de texto que a sessão já tem.
2. **Dizer o que uma linha de workflow significa.** O `tool_use_id` vazio de uma linha de workflow
   a faz parecer um spawn que nunca foi redirecionado, então qualquer número de conformidade sobre
   o ledger a conta silenciosamente como conforme; e uma linha nomeada para um papel herda o
   orçamento flexível desse papel embora tenha rodado sem confinamento. `harness usage` deveria
   separar o gasto de workflow e parar de precificar uma linha de workflow contra o orçamento de
   um papel confinado.
