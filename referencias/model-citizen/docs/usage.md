# Telemetria de uso

Medições identificam seu runtime. Os adaptadores de transcrição do Claude e do Codex
compartilham detectores; snapshots cumulativos de token do Codex são contados uma vez, métricas
indisponíveis permanecem desconhecidas, e relatórios rotulam totais parciais. Falhas de detector
são excluídas dos denominadores de sessão limpa. Veja [controles de runtime](runtime-controls.md)
para os limites. Os detalhes de transcrição do Claude abaixo continuam específicos a esse
adaptador.

O hook `usage-log` roda em `SessionEnd` e mantém um registro por sessão em
`~/.local/state/agent-harness/usage.jsonl`. É um arquivo local e nada mais: nenhuma chamada de
rede, nenhum serviço, nenhuma conta, e nada além do id de sessão, o nome do diretório de
repositório, a branch, ids de modelo e contagens de token. Enviar essas linhas a um backend de
observabilidade é opt-in, desligado por padrão e descrito em [telemetry.md](telemetry.md); o
ledger continua sendo o registro e o backend é uma cópia que `citizen usage export --since`
consegue reconstruir.

## Quais regras dispararam

O mesmo relatório que soma os tokens pontua as regras. `bin/harness usage --rules` conta acertos
de detector por regra na janela em vez de tokens, e `citizen --help` o lista ao lado dos
agrupamentos de token.

```sh
bin/harness usage --rules                      # acertos por detector nos últimos 30 dias
bin/harness usage --rules --by repo            # sessões, acertos e os três principais por repositório
bin/harness usage --rules --by stance          # o mesmo, por dimension=variant
```

Três agrupamentos e nada mais: `rule`, o padrão, uma linha por id de registro; `repo`, uma linha
por nome de diretório de repositório; `stance`, uma linha por `dimension=variant` em vigor.
`--by model` é recusado em vez de silenciosamente reagrupado, já que os acertos de uma sessão não
pertencem a nenhum de seus modelos.

Duas anotações vêm dos números sozinhos, e seus limiares são `RULE_PROMOTE_SHARE` e
`RULE_MIN_SESSIONS` em `bin/harness`. `promote?` marca um detector que acertou em mais de 30 por
cento (`RULE_PROMOTE_SHARE = 0.30`) das sessões na janela; `unobserved` marca um que não acertou
em nenhuma delas. Nenhuma das duas é impressa abaixo de 20 sessões medidas
(`RULE_MIN_SESSIONS = 20`), porque uma fração sobre três sessões diz pouco. Só um registro
carregando um mapa `rules` conta para qualquer uma delas, então o denominador é sessões medidas e
não linhas.

O que cada detector procura, como uma renomeação se dobra e por que uma sessão reescaneada é
excluída do agrupamento de postura estão sob [telemetria de regra](#rule-telemetry) abaixo. Rodar
a medição sem o resto do harness é [medição standalone](standalone-measurement.md).

## O que é registrado

Toda linha nomeia seu `kind`: `session`, `subagent` ou `worker`. Uma linha escrita antes de o
campo existir é lida como uma sessão, que era tudo que havia para registrar, e `--rescan` a
atualiza.

Toda linha também nomeia a `harness_version` que a escreveu, lida do mesmo arquivo `VERSION` que
`citizen --version` imprime, então uma mudança de gasto pode ser lida contra um lançamento. **Uma
linha reescaneada carrega `null`**: a versão que rodou uma sessão passada não é recuperável de sua
transcrição, e carimbar a de hoje faria todo o histórico parecer deste lançamento.

Toda linha nova, neste ledger e no log de decisões, também nomeia o **`profile_fingerprint`** do
perfil que a escreveu: o sha256 do conteúdo de cada módulo ligado, as variantes de postura, as
chaves de configuração que alcançam o modelo ou um hook (`identity`, `permissions`,
`permissions_bypass_acknowledged`, `plan_allow_tools`, `telemetry`, `governance`) e a versão do
harness. `posture.profile()` constrói o documento que ele resume, e `posture.fingerprint()` é a
única definição. Perfis idênticos combinam em qualquer máquina, já que nenhum caminho alcança o
resumo; um módulo, postura ou configuração de diferença, e eles diferem. A linha de um worker de
papel carrega o perfil sob o qual sua execução começou, e uma linha de reprodução carrega o de seu
braço, ou `bare` para o braço que não carrega nenhum harness. Uma linha de antes do campo, uma
sessão reescaneada que o ledger ainda não continha, e uma linha cujo perfil não pôde ser resolvido
carregam nenhum ou `null`, e são lidas como **não atribuídas**: nada nunca recebe uma impressão
digital adivinhada.

Uma linha de sessão também carrega **`context_attribution`**: qual módulo colocou quantos tokens no
contexto da sessão. O contexto é compartilhado, então isso é uma estimativa, e o campo diz isso:

```json
"context_attribution": {"estimand": "soft estimate",
  "method": "chars/4 of resident text: a rule or stance variant whole; a skill, role or workflow its name and description",
  "modules": {"rules/secrets": 222, "stances/voice": 106, "skills/sandbox": 65, "roles/builder": 60}}
```

Cada chave é uma referência de seleção, `kind/unit`, para todo módulo ligado e toda postura com
texto residente antes do primeiro prompt. Uma skill, papel ou workflow é residente como sua
entrada de listagem, e seu corpo carrega sob demanda, então só a entrada conta. O contexto de um
hook chega por evento e não é estimado aqui; o log de decisões atribui o que um hook decidiu em
vez disso. `posture.context_attribution()` é a única definição, então um módulo desligado remove a
entrada desse módulo e não muda nenhuma outra, enquanto a impressão digital muda junto. Uma linha
de reprodução carrega a atribuição do seu braço, sem nenhum módulo para o braço nu. Uma sessão
reescaneada mantém o que o ledger já continha e caso contrário não carrega nenhum campo, nunca a
seleção deste minuto.

**`kind: "session"`** — `session_id`, `repo`, `branch`, `models`, `started`, `ended`, `input`,
`output`, `cache_read`, `cache_write`, `subagents`, `turns`, `effort`, `effort_source`, `days`,
`raw_vs_deduped` e, quando a linha tiver algum, `idless_records`.
A fonte é a transcrição que o Claude Code já escreve sob `~/.claude/projects/`. O worker a
transmite em stream e soma os quatro campos de token sobre mensagens de assistente **uma vez por
id de mensagem, no maior valor daquele id**: uma resposta de API é escrita como várias entradas de
transcrição, então contar por linha infla todo total — mas essas entradas não repetem um objeto
`usage`. As primeiras carregam um `output_tokens` de streaming parcial e a última carrega o número
verdadeiro da resposta, então tomar a primeira o subestima. O máximo campo a campo é o número
final, e uma cauda reordenada ou truncada não consegue baixá-lo. Um registro sem nenhum id de
mensagem é indexado pelo seu `requestId` em vez disso, que nomeia uma chamada de API: a mesma
chamada escrita tanto em um arquivo de sessão quanto em um arquivo de subagente é uma resposta, e
uma chamada cujos outros registros de fato carregam um id de mensagem entra no slot deles em vez
de abrir um segundo. Um registro sem nenhum dos dois ids é desconhecido em vez de duplicata,
então não é deduplicado de forma alguma — é somado como está escrito, e `idless_records` conta
quantos desses registros os totais da linha incluem, os da própria sessão e os dos arquivos de
subagente dobrados neles. Uma linha sem o campo foi deduplicada por inteiro. `subagents` conta
chamadas de ferramenta `Agent`, menos quaisquer que um hook recusou: uma chamada cujo resultado é
um erro e que não deixou nenhuma transcrição de subagente. Um arquivo de sessão carregando linhas
de sidechain é o formato mais antigo, onde um spawn que rodou não tem arquivo próprio, então ali
toda chamada é contada.

`raw_vs_deduped` é **o tamanho medido dessa inflação**: a soma linha a linha dos quatro campos de
token sobre o total deduplicado que a linha carrega, através dos mesmos registros — os da própria
sessão e os dos arquivos de subagente dobrados nela. `1.0` diz que a transcrição não continha nada
para remover; `2.4` diz que contar toda linha teria cobrado desta sessão duas vezes e meia o que
gastou. Uma razão em vez de uma por campo, porque os campos são deduplicados pelos mesmos slots e
a linha já carrega cada um deles para um leitor que os quer separados. A linha de sessão de um
Codex, cujo runtime relata snapshots cumulativos em vez de um número por registro, carrega a
string `"unknown"` em vez de `1.0`, o que alegaria uma medição que ninguém fez. Uma linha de
subagente, uma linha de worker e uma linha escrita antes deste lançamento não carregam **nenhuma
dessa chave**, e um leitor — `citizen usage` incluído — lê essa ausência como desconhecida pela
mesma razão. O número de rodapé que `citizen usage` imprime é a soma bruta da janela sobre sua
soma contada: a razão de cada linha ponderada pelos tokens deduplicados que essa linha contribuiu
às colunas acima dela, que sob `--by day` são suas fatias dentro da janela e não seu total
inteiro. A exportação OTLP carrega o próprio valor de uma linha como o atributo `raw_vs_deduped`, e
uma linha sem a chave não exporta nenhum. Os totais de token **incluem os subagentes da sessão**,
porque seus tokens são a conta da sessão — contados uma vez sobre um único mapa de ids de
mensagem, nunca como uma soma de dois arquivos. O Claude Code mais antigo escrevia os turnos de um
subagente no arquivo de sessão como linhas de sidechain e o Claude Code mais novo os escreve no
próprio arquivo do agente; uma transcrição carregando os dois pagaria de outra forma por todo
token delegado duas vezes.

### Esforço de sessão

`effort` é o esforço de raciocínio sob o qual a sessão majoritariamente rodou, e `effort_source`
diz de onde foi lido: `transcript` para o Claude Code, que escreve `effort` e `perTurnEffort` em
todo registro de assistente, e `turn_context` para o Codex, que o registra por turno e admite
valores até `ultra`. O esforço muda no meio da sessão — 14 de 112 transcrições do Claude Code e 4
de 44 rollouts do Codex medidos em uma máquina — então a linha registra **o valor que cobriu mais
tokens de saída**, não o primeiro nem o último. Para o Claude Code, esse peso é só das próprias
mensagens da sessão; o esforço de um subagente pertence ao spawn, não à sessão. Para o Codex é a
diferença entre snapshots cumulativos consecutivos. Uma transcrição que não registra nenhum
esforço deixa os dois campos `null`, o que faz o relatório não ter nada por que agrupar.

### Fatias por dia

`days` mapeia uma data UTC para `input`, `output`, `cache_read`, `cache_write` e `turns` para essa
data. Uma sessão que roda por duas semanas termina em uma data e gasta em quatorze, e atribuí-la
por inteiro à sua data de término foi o que fez cinco sessões longas serem 68% de todos os tokens
de saída em uma máquina.

As fatias são cortadas do mesmo mapa deduplicado de id de mensagem sobre o qual os totais da linha
são somados, então **a fatia de um dia do Claude Code inclui os tokens de subagente daquele dia**,
exatamente como o total da sessão os inclui: a linha de sessão significa uma coisa, e uma fatia que
os excluísse não conseguiria somar até ela. A primeira data em que um id de mensagem é visto é a
que vale, então uma resposta escrita através da meia-noite pertence a um dia. O Codex não tem
nenhum número por mensagem, só snapshots cumulativos, então uma fatia do Codex é a diferença entre
consecutivos, atribuída à data do snapshot que a fechou; uma linha só com `total_tokens` não recebe
nenhuma fatia.

As fatias são verificadas contra os próprios totais da linha antes de serem escritas, campo por
campo. Um mapa que não soma é descartado em vez de registrado, então um mapa `days` em uma linha
sempre é consistente com a linha.

**`kind: "subagent"`** — uma linha por `agent-<id>.jsonl` em qualquer lugar sob
`<session>/subagents/`, a árvore que o Claude Code escreve ao lado do próprio arquivo da sessão. A
travessia é recursiva porque um agente de ferramenta Workflow vive um nível mais fundo, em
`subagents/workflows/wf_<id>/`, e seu campo `workflow` nomeia esse diretório. `agent_id`,
`agent_type` e `spawn_depth` vêm do `.meta.json` irmão, e um agente escrito sem um é registrado
como `agent_type: "unknown"` em vez de descartado. Depois `model` — o id que a própria transcrição
do agente relata, o mais frequente em seus registros de assistente, recorrendo ao alias que o
spawn pediu apenas quando não registrou nenhum, então um spawn roteado e um direto no mesmo modelo
se agrupam sob um nome — `effort`, os quatro campos de token, `tool_calls` e, quando a transcrição
do agente continha algum, `idless_records`: os registros nos totais desta linha que nem um id de
mensagem nem um id de requisição identificaram. `tool_use_id` é a chamada pai à qual esta linha
pertence, `requested_type` é o tipo de agente que essa chamada pediu, e `rerouted` é os dois
discordando — a medida de quantas vezes um hook de spawn moveu um spawn. Um tipo requisitado só é
mantido quando é um nome que a ferramenta poderia ter resolvido; qualquer outra coisa é registrada
como `"other"`. `budget_output_tokens` e `budget_tool_calls` são o **orçamento flexível que o
papel carrega** — os mesmos números que `brief-guard` escreve em um brief — então um excesso é uma
subtração em uma linha em vez de um join contra o que a tabela de custo diz hoje. São lidos da
tabela no momento em que a linha é escrita, não do brief, que nenhuma varredura consegue ver; um
papel que nada precifica, uma tabela que não constrói e um subagente do Codex todos registram
`null`, porque um zero diria que o spawn não recebeu orçamento nenhum. Um agente de ferramenta
Workflow também registra `null`, seja qual for o papel para o qual é nomeado, e carrega
`unconfined: true`: a ferramenta o lançou, então nenhum hook de spawn o roteou e nenhum brief lhe
deu orçamento. `return_path` e `return_over_budget` medem o retorno que o spawn desta linha
entregou, ligado à chamada `Agent` do pai pelo mesmo `tool_use_id`: se nomeou um caminho que
existia sob a worktree ou o scratchpad no momento em que a linha foi escrita (`"resolvable"`,
`"unresolvable"`, ou `"none"` para um retorno que não nomeou nenhum caminho de forma alguma, que é
um fato e não uma falha), e se sua contagem de palavras passou do limite que seu brief declarou —
o número ao lado da palavra `words` no limite que `rule-detectors` lê, ou o padrão de 400 palavras
que `brief-guard` anexa a um brief que não declara nenhum. Um caminho conta quando está entre
aspas, em um bloco ou em crases, ou quando prosa simples lhe dá a forma própria de um caminho: uma
raiz, um prefixo relativo, ou uma extensão em seu último segmento, então `pass/fail` e
`2026/09/22` são prosa e uma URL não é o arquivo de ninguém aqui. Os dois campos são `null` quando
a varredura não conseguiu medi-los: nenhuma chamada pai para ligar, um retorno vazio, um brief
vazio, um spawn cujo `requested_type` carrega seu limite na própria definição, ou uma linha do
Codex, cujo runtime não liga nenhum retorno de forma alguma. Um resultado em que a varredura
manteve só os primeiros 64 KB de registros recebe `return_measured: "truncated"` em vez disso,
porque uma contagem de palavras sobre o início de um retorno não é uma contagem de palavras do
retorno. A correspondência é uma correspondência de string e a resolução um `os.path.exists`;
nenhum modelo julga o retorno aqui. Essas linhas carregam os mesmos tokens uma segunda vez,
atribuídos, que é por que nenhum agrupamento soma tanto elas quanto sua sessão.

**`kind: "worker"`** — uma linha por worker `citizen role run` completado, com o nome do papel
como `agent_type`. Um worker é uma sessão de CLI isolada; seu runtime relata o que a execução
custou no envelope ou fluxo de eventos que o adaptador já lê, e `workers.py` escreve esses totais
em seu `status.json`. Um runtime que não relata nenhum deixa os campos desconhecidos em vez de
zero. Nenhum dos dois runtimes relata a contagem de chamadas de ferramenta de um worker, então
`tool_calls` é desconhecido para workers. Uma execução que expirou ou falhou não é registrada: seu
total se compara a nada. Um worker é lançado pelo nome, então seu `requested_type` e `tool_use_id`
são nulos.

Nenhuma linha guarda texto de prompt, texto de comando ou um brief: contagens, e os
identificadores `tool_use_id` e `requested_type`, que são o id de uma chamada de ferramenta e um
nome de agente que a ferramenta poderia ter resolvido.

Hooks de `SessionEnd` compartilham um orçamento de 1,5 segundo, então o hook gera um worker
desacoplado e retorna na hora. Linhas são upsertadas por `(session_id, runtime, kind, agent_id)`,
então reler uma transcrição nunca duplica uma, e uma transcrição de subagente só é lida a partir
da sua própria sessão.

### Rollouts do Codex

O Codex é lido de `~/.codex/sessions/` e `~/.codex/archived_sessions/` — `CODEX_HOME` move os
dois — e escreve um subagente em um arquivo de rollout próprio em vez de ao lado do seu pai. O
`session_meta` é o que distingue os dois: o `payload.source` de um rollout de nível superior é uma
string nomeando o front end, o de uma thread gerada é o objeto
`{"subagent": {"thread_spawn": {…}}}` carregando o id da thread pai, a profundidade, o caminho do
agente e um apelido. A linha toma `agent_role` como seu `agent_type` e recorre a
`agent_nickname`, que é o que o fallback de fato faz hoje: o Codex deixa o papel nulo e nomeia
cada thread, então `--by role` agrupa threads do Codex por apelido e os grupos são pequenos. Só o
**primeiro** `session_meta` é próprio deste rollout — uma thread que herdou o histórico do seu pai
carrega o dele mais adiante no arquivo.

**Os tokens de um pai do Codex não incluem os dos filhos**, que é o oposto da regra do Claude Code
acima, então `citizen usage` soma linhas de subagente do Codex e pula as do Claude Code. A
evidência é o corpus de 438 rollouts a partir do qual isso foi construído: das 21 threads pai com
tanto um total tipado quanto filhos com um, quatro relatam menos tokens do que a soma de seus
próprios filhos, 2,0M contra 30,6M no caso mais extremo. Um total que incluísse seus filhos não
poderia ser menor que eles.

`input_tokens` é relatado incluindo `cached_input_tokens`, `total_tokens` é input mais output, e
`reasoning_output_tokens` é parte de `output_tokens` em vez de ao lado dele — nenhuma exceção nos
349 rollouts que carregam uma divisão tipada. O Codex Desktop muitas vezes escreve um snapshot só
com `total_tokens` e todo campo tipado zero (85 de 107 rollouts de Desktop de nível superior
aqui). Essa linha mantém `total`, é marcada `partial`, e deixa os campos tipados desconhecidos,
então o relatório a exclui em vez de ler uma sessão real como gratuita.

A captura do Codex viaja através de `citizen usage --rescan` em vez do hook. O coordenador de
ciclo de vida de fato registra `SessionEnd`, mas se o payload que o Codex envia nomeia o arquivo
de rollout não foi observado aqui — nenhuma CLI do Codex foi instalada na máquina em que isso foi
medido, e nada nos rollouts ou em `~/.codex/logs_*.sqlite` registra um payload de hook. O hook
aceita `rollout_path` e `session_path` ao lado do `transcript_path` do Claude Code por essa
chance; a reescaneada é o caminho conhecido por funcionar. Rode-a depois de um período de trabalho
com o Codex.

### Schema do ledger

O ledger de uso e o log de decisões são lidos por lançamentos diferentes daquele que os escreveu,
então os dois crescem de forma compatível:

- **Toda linha nomeia seu `schema_version`**, a partir da versão 1. Uma linha sem ele foi escrita
  antes de o campo existir e é lida como versão 0; nenhuma linha antiga é reescrita para
  adicioná-lo.
- **Mudanças são aditivas.** Um campo novo é adicionado; nada é removido ou retipado no lugar.
- **Leitores toleram o que não conhecem.** Um campo, uma versão de schema ou um valor que este
  lançamento nunca viu é carregado adiante, nunca recusado, então a linha de um escritor mais novo
  é lida sem erro.
- **Uma renomeação vem com uma dobra.** `FIELD_FOLDS` em `usage-log.py` e em `decisions.py`
  mapeia cada nome de campo antigo para o novo, e todo leitor dobra na leitura: o valor de uma
  linha antiga aparece sob o nome novo, e uma linha carregando os dois mantém o novo.

`SCHEMA_VERSION` em cada um desses módulos é incrementado com qualquer mudança no que uma linha
carrega. A versão 1 é lançada primeiro na v0.14.0 e carrega todo campo que esse lançamento
adiciona, `profile_fingerprint`, `context_attribution` e `module` entre eles.

## Feed de uso

O log de uso é lido depois do fato. O feed é a mesma medição enquanto a sessão ainda está
rodando: o hook `usage-feed` injeta uma ou duas linhas de contexto para que o orquestrador veja o
que está gastando antes de delegar de novo.

- Em **`UserPromptSubmit`**, uma linha com os tokens de saída e chamadas de ferramenta do último
  turno e os da própria sessão — mas só quando há um turno atrás dela e seus números não são os já
  impressos, porque a conclusão de um agente em segundo plano chega como um prompt próprio e
  vários em seguida de outra forma repetem um turno — seguida de uma linha por subagente que
  terminou desde o prompt anterior.
  Essa segunda parte é como um spawn em segundo plano é relatado de qualquer forma: seu
  `PostToolUse` dispara no lançamento, antes de o agente ter gasto qualquer coisa. No máximo cinco
  agentes são listados, depois `… and n more`.
- Em **`PostToolUse`** para um retorno síncrono de `Agent`, uma linha para esse subagente, na
  hora. Qualquer chamada `Agent`, um lançamento em segundo plano incluído, também carrega uma
  linha quando mais agentes estão rodando que `max_parallel`:
  `usage-feed: 7 subagents running against a posture width of 6`. É uma nota e nunca uma decisão
  — o feed não tem nenhum caminho de negação e não escreve nenhum campo de permissão.
- Em **`SubagentStart`** e **`SubagentStop`**, nada é injetado — um contexto de `SubagentStop`
  alcançaria o agente que acabou de terminar — mas o início e o custo são registrados para as
  linhas acima. Rodando significa iniciado e ainda não parado.

O número de um subagente é somado a partir da sua própria transcrição, nunca da resposta da
ferramenta, que relata só a **última** resposta do agente: medida em 3.143 tokens de saída contra
10.575 de fato gastos. Cada linha nomeia o tipo do agente, o que gastou e, quando sua linha carrega
orçamentos, a maior das duas razões contra eles, prefixada com `over budget` além de um múltiplo
de `nudge_at`.

A primeira linha que carrega um número é seguida, uma vez por sessão, pelo que os números são:
tokens de saída e chamadas de ferramenta somados da própria transcrição de cada agente, que não é
o `subagent_tokens` da notificação de tarefa. Medido ao vivo, a linha de um agente disse 31.121
tokens de saída ao lado de um `subagent_tokens 102398` de uma notificação; os dois estavam certos
sobre coisas diferentes.

Um agente retomado com uma mensagem de acompanhamento para uma vez por rodada, contra um único id
de agente e uma transcrição. Toda rodada é alimentada com uma linha — `gatherer finished round 2
at 800 output tokens and 2 tool calls (cumulative)` — porque a transcrição é toda a vida do
agente e o número de uma rodada posterior cobre as anteriores. Continua sendo um subagente na
contagem de sessão, e só a subida alcança os totais da sessão.

A parada de um agente retomado pode disparar antes de as respostas dessa rodada serem
descarregadas, e a transcrição termina na resposta terminada da rodada anterior de qualquer
forma — então nada no arquivo diz que a rodada está incompleta. O que diz é o número: uma soma
que não passou do já relatado é uma rodada que ainda não aterrissou. Tal rodada é ressomada a
cada evento seguinte e nada é dito sobre ela enquanto isso, em vez de uma linha repetindo o
número da rodada anterior; depois de três tentativas, ou uma transcrição que sumiu, é descartada
sem ser dita.

Essa soma tem um teto de 8 MiB do final da transcrição do agente e de quatro segundos, porque
roda dentro do timeout de um hook. Quando um teto morde, a linha diz `(partial)`; quando a soma
não pôde ser feita de forma alguma, diz `spend unknown` em vez de relatar o agente como zero. De
qualquer forma a parada é registrada, porque um agente cuja parada sumiu contaria como rodando
pelo resto da sessão. Um início cuja parada nunca chega é esquecido depois de três horas.

A soma é feita quando o agente é **relatado**, não quando para. Um `SubagentStop` dispara no
instante em que o agente termina, o que pode ser antes de uma de suas respostas ter sido
descarregada em sua transcrição, e não espera por nada porque um prompt pode estar enfileirado
atrás dele — então uma parada sem nenhum número nela, ou uma lida de uma resposta ainda sendo
escrita, é registrada em diário como ainda não somada e é somada de novo na linha que a nomeia,
antes de o lock ser tomado e dentro de um orçamento de relógio compartilhado por todo agente que
esse evento relata. Agentes que esse orçamento não alcança mantêm seu lugar e são somados no
próximo evento. `spend unknown` portanto significa uma transcrição que não está lá; uma
transcrição que está lá e ainda não contém nenhuma resposta diz `spend not yet recorded`, e o
número que ganha depois alcança os totais da sessão sem o agente ser nomeado duas vezes.

`spend unknown` nomeia o agente sobre o qual é — `unknown finished, spend unknown, no transcript
found for agent a1b2c3` — e é alimentada uma vez por sessão para esse agente. Não carrega nenhum
número e nada nunca vai reconciliá-la, então repeti-la turno após turno, o que uma sessão cujo
estado de leitor foi reconstruído costumava fazer, só gasta o contexto do orquestrador em um fato
que já leu.

Um retorno síncrono também pode chegar antes de a última resposta do agente estar em disco: uma
resposta de API é escrita como vários registros, os primeiros carregando uma contagem parcial de
streaming e o último um `stop_reason`. Então o retorno consulta a cauda da transcrição por até um
segundo, esperando por esse registro, e a linha diz `(so far)` quando nunca chega. Seja qual for
o número impresso, o número consolidado que a parada registra depois eleva os totais da sessão —
o agente nunca é nomeado uma segunda vez, e o total da sessão nunca fica abaixo da soma dos
números finais.

Um prompt também carrega uma linha sobre a própria sessão quando seu contexto cresceu além de um
tamanho que a postura chama de sessão cheia:
`usage-feed: session context 120,000 tokens, past the fresh-session threshold of 100,000 — finish
the task, write the handoff, start a fresh session`. O tamanho é os tokens de entrada da resposta
mais nova mais o prefixo que leu do cache e o prefixo que escreveu nele, que é o que todo turno
seguinte relê e o que uma sessão longa mais custa; a linha de turno não mostra nada disso.

É dita uma vez por limiar e não uma vez por turno: uma sessão que fica acima de um permanece
silenciosa até alcançar o próximo, e uma retomada — ou uma transcrição cuja identidade mudou, o que
faz o leitor recomeçar — lê os limiares já ditos de volta do arquivo de estado. Um contexto que
cai de volta abaixo de um limiar, que é o que uma compactação no lugar faz, arma esse limiar de
novo, porque cruzá-lo uma segunda vez é uma cruzada sobre a qual ninguém foi avisado. A linha
nomeia o limiar mais alto recém-cruzado, nunca um já alimentado. Um contexto que nenhuma resposta
relatou ainda não é uma travessia, então nada é dito em vez de um tamanho de zero ser inventado.
Como toda outra linha aqui, é flexível: nada é bloqueado.

Cinco configurações no sidecar da variante `cost` ativa governam tudo isso, e o hook não guarda
nenhum número próprio:

- `turn_feed: "off"` — nada é injetado em lugar nenhum e nenhum arquivo é escrito.
- `turn_feed: "thresholds"` — sem linha de turno; só subagentes em ou acima do menor `nudge_at`.
  Um agente sobre o qual nada foi dito continua não relatado, então uma travessia de limiar
  posterior ainda consegue nomeá-lo.
- `turn_feed: "every-turn"` — a linha de turno e todo subagente terminado. `balanced` e `frugal`
  distribuem isto.
- `nudge_at` — os múltiplos que marcam um retorno como acima do orçamento. Uma lista vazia, que
  `max` distribui, significa nunca.
- `session_nudge_at` — os tamanhos de contexto, em tokens inteiros, do menor ao maior e sem
  repetição, nos quais a linha de sessão nova é dita. `frugal` distribui 80.000 e 120.000,
  `balanced` 120.000 e 160.000, e `max` uma lista vazia, que significa nunca. Esses números são
  pontos de partida escolhidos contra uma janela de 200.000 tokens, não medidos: o
  acompanhamento da #321 os substitui por tamanhos lidos do ledger.
- `max_parallel` — a largura contra a qual a nota de agente rodando mede. `null`, que `max`
  distribui, significa que a nota nunca aparece.

### Estado, e por que são dois arquivos

Esses hooks são processos separados que rodam ao mesmo tempo: chamadas de ferramenta saem em
paralelo e vários agentes terminam de uma vez. Então o estado é dividido, os dois arquivos em
0600 em um diretório 0700 sob `~/.local/state/agent-harness/feed/`.

- `<session-id>.events.jsonl` é só-anexação. Um subagente iniciando ou terminando é uma linha
  abaixo de 4 KB escrita com um único `os.write` em um descritor `O_APPEND` — um anexo atômico
  que nenhum manipulador nunca reescreve, então nenhum registro pode ser perdido para um
  concorrente.
- `<session-id>.json` é o estado de leitor do fio principal: o offset da transcrição, o offset do
  diário, os totais em execução, os ids de mensagem abertos, os agentes ainda em andamento e os
  terminados ainda não nomeados. Tudo que o lê e depois o escreve faz isso sob um `flock`
  exclusivo em `<session-id>.lock` com um limite de dois segundos. Sem lock, sem escrita, e nada
  dito.

Nada lento acontece enquanto esse lock é mantido. `SubagentStart` e `SubagentStop` nunca o tomam —
anexam e saem — e os dois eventos de fio principal somam a transcrição de um subagente antes de
adquiri-lo. Uma soma de quatro segundos sob o lock faria o prompt esperando atrás dele passar
fome, e esse prompt perderia sua linha em silêncio.

Os dois arquivos guardam só contagens e nomes de tipo de agente — nenhum texto de prompt, nenhum
texto de comando, nenhuma saída de agente — e um tipo de agente que não é um nome simples é
registrado como `other`. Os arquivos de uma sessão são varridos uma vez por dia, juntos e só
quando o mais novo deles ficou uma quinzena sem ser tocado, nunca a sessão em execução; `citizen
uninstall` remove o diretório.

Os dois offsets são o que mantém o caminho crítico barato: cada prompt lê a transcrição e o
diário de onde parou, então o total de subagente de uma sessão longa só consegue crescer. É
confiado só enquanto o arquivo é o mesmo arquivo, o que o inode e um hash do primeiro registro
decidem, então uma transcrição substituída por uma *maior* reseta exatamente como uma truncada.
Sem estado utilizável, a leitura começa 8 MiB do final em vez do byte zero, porque a transcrição
de uma sessão retomada roda por centenas de megabytes e um hook morto no seu timeout travaria
todo prompt depois dele. Qualquer leitura que pulou conteúdo, ou que rodou além do seu orçamento
de três segundos, marca os totais `(partial)`.

O Codex não dispara nenhum de `UserPromptSubmit`, `SubagentStart` ou `SubagentStop`, então o feed
é declarado não coberto ali em `adapters/codex/capabilities.json`; a postura ainda alcança o
Codex através de workers de role-run.

### O registro de sessão

Mais um diretório fica ao lado do de feed, `~/.local/state/agent-harness/sessions/`, escrito pelo
início de sessão e por um spawn que aprende de uma recarga em vez de por qualquer medição: um
arquivo pequeno por sessão nomeando as definições de agente que o registro daquela sessão
continha, que é o piso sob se um spawn sem nome pode ser roteado para um worker de banda — veja
[controles de runtime](runtime-controls.md). Guarda nomes de agente e um timestamp, nada sobre o
trabalho; os arquivos são só do dono em um diretório só do dono, varridos depois de uma quinzena
de não uso, e removidos por `citizen uninstall`.

### Eventos de adesão

A linha de sessão nova é uma recomendação, então dizê-la também anexa uma linha `emitted` a
`~/.local/state/agent-harness/adherence.jsonl`: a recomendação, o módulo que a disse
(`hooks/usage-feed`), o id de sessão, o turno em que foi dita e a impressão digital de perfil.
Uma linha `response` ligada a ela por `adherence_id` depois diz `followed`, `not_followed` ou
`unknown`, e `policy/hooks/adherence.py` calcula uma taxa por recomendação a partir das duas.
Nenhuma linha guarda um prompt, uma chamada de ferramenta ou o texto próprio da linha, e registrar
nunca muda o que o feed diz: um ledger que não consegue escrever é pulado em silêncio.

A resposta é lida do ledger de observação (`observation.jsonl`). Uma sessão que termina dentro de
três prompts da linha a seguiu; uma que continua além deles não seguiu. Até que o ponto de
entrada de observação seja registrado em sessões ao vivo, esse ledger não guarda nenhuma linha,
então toda emissão é respondida `unknown` com o motivo `unobserved` assim que completa um dia.

## O log de decisões

`~/.local/state/agent-harness/decisions.jsonl`, ao lado do ledger e escrito pelos mesmos hooks,
guarda **um registro por julgamento que um hook faz** e um segundo registro por julgamento que a
sessão depois resolveu. O ledger diz o que uma execução custou; este diz o que o harness decidiu e
se a decisão se sustentou. Existe para que substituir uma heurística — por um padrão melhor, um
classificador, qualquer coisa — seja medido contra rótulos que o harness já produz e costumava
descartar. Nada aqui é exportado, nada aqui é visível ao modelo, e o arquivo nunca cresce um
token de contexto.

```json
{"kind": "decision", "decision_id": "e38a…", "point": "grade-bash", "session_id": "s-1",
 "ts": "2026-09-21T19:41:05Z", "input_sha256": "d20c…", "input": "git push --force origin main",
 "deterministic_answer": "ask", "outcome": null, "runtime": "claude-code",
 "harness_version": "0.12.0", "profile_fingerprint": "5f1c…", "module": "hooks/grade-bash",
 "schema_version": 1}
{"kind": "outcome", "decision_id": "e38a…", "point": "grade-bash", "session_id": "s-1",
 "ts": "2026-09-21T19:41:22Z", "outcome": "ran", "harness_version": "0.12.0",
 "profile_fingerprint": "5f1c…", "module": "hooks/grade-bash", "schema_version": 1}
```

`module` nomeia o hook que possui a decisão, como `hooks/<id>`: `grade-bash`, `stop-gate` e
`brief-guard` os seus próprios, e a linha de roteamento de banda e o aviso de integração
`hooks/tier-agent-spawns`. Recusas de confinamento de papel, de framework e de evasão e a guarda
de lançamento de Workflow nomeiam `null`, porque nenhum id de hook os desliga, e o mesmo vale para
qualquer outro ponto que nenhum hook possui, como `decision-provider`. `POINT_MODULES` em
`decisions.py` é o mapa.

O arquivo é **só-anexação**: um resultado é seu próprio registro, ligado à sua decisão por
`decision_id` quando o relatório o lê, e nenhuma linha nunca é reescrita. `input` é o texto que o
hook julgou, limitado a 2 KiB; `input_sha256` é sobre o texto **sem limite**, então o limite perde
evidência e nunca identidade. Nenhuma saída de ferramenta e nenhuma prosa de assistente alcança
nenhum dos dois campos; o único campo que guarda prosa é
[a alegação de conclusão](#the-completion-claim), que está desligada.

| ponto | o julgamento | o resultado, quando há um |
| --- | --- | --- |
| `grade-bash` | a resposta de permissão, `ask` ou `deny` | `ran` quando o PostToolUse do comando chega, `not_run` quando a sessão termina sem um |
| `stop-gate` | `blocked`, `released` ou `skipped` | o próprio resultado do gate: `passed`, `failed`, `timeout`, `unverified`, `untrusted` |
| `tier-agent-spawns` | o worker de banda para o qual um spawn sem nome foi roteado | ainda não rotulado |
| `brief-guard` | o que foi anexado: `cap`, `budget` ou `cap+budget` | ainda não rotulado |
| `evasion-deny` | `deny`, em um re-spawn de trabalho já recusado | ainda não rotulado |
| `role-confinement` | `deny`, em um spawn nativo nomeando um papel restrito, por `subagent_type` ou uma linha `harness-role:`; `input` começa com o papel e qual dos dois o nomeou | ainda não rotulado |
| `workflow-launch` | `allow` ou `deny`, em todo lançamento de ferramenta `Workflow` | ainda não rotulado |

Um comando Bash aprovado não é *classificado*. O harness responde à pergunta de permissão em uma
pequena minoria das chamadas, e "rodou" não diz nada sobre se recusar interromper estava certo;
um prompt ou uma recusa é o julgamento que um rótulo consegue avaliar. Uma amostra das aprovações
é mantida mesmo assim, como [allows amostrados](#sampled-allows) abaixo, que não carregam nenhum
resultado. `not_run` deliberadamente não é chamado de "negado": um usuário que recusou, um
usuário que interrompeu o turno e uma sessão que travou parecem todos iguais de um hook, e nomear
um deles colocaria um rótulo no arquivo que ninguém mediu.

Os dois runtimes escrevem, para os eventos que ambos disparam. O roteamento de banda acontece só
no Claude Code, então o Codex não registra nenhuma linha `tier-agent-spawns`;
`adapters/codex/capabilities.json` nomeia essa lacuna.

Uma escrita que falha é contada e engolida — um log que consegue mudar uma resposta de permissão
é pior que nenhum log — e `telemetry.decisions: false` em `config.json` desliga a coisa toda,
depois do que nenhuma linha, nenhum arquivo e nenhum diretório é escrito. Veja
[telemetry.md](telemetry.md#the-decision-log-switch).

### Allows amostrados

Um comando Bash em vinte que o harness **permitiu** é escrito como uma linha `grade-bash` própria:

```json
{"kind": "decision", "point": "grade-bash", "deterministic_answer": "allow", "sampled": true,
 "sample_rate": 20, "input": "cargo test --release", "outcome": null}
```

Existem porque as linhas classificadas são todas prompts: uma verificação que só pode apertar um
allow em um ask não tem nada para medir seus falsos alarmes sem os comandos sobre os quais
ninguém foi perguntado. São **negativos, não julgamentos** — `sampled: true`, nunca um resultado,
passados como concluídos em SessionEnd em vez de fechados como `not_run`, e contados por
`usage --by decision` em uma linha `grade-bash (sampled)` própria para que não consigam diluir as
taxas de resultado das linhas classificadas.

Só um allow que o harness de fato deu é amostrado. Um comando sobre o qual não respondeu nada é do
próprio runtime decidir e ainda pode ser perguntado ou recusado, então não é evidência de um
allow e nenhuma linha: isso cobre um comando de classe 1 sob a postura `execute`, e todo comando
no Codex, onde uma aprovação simples é descartada da saída do hook e o padrão do próprio cliente
prevalece. Um comando confirmado — um rerodado com o marcador de confirmação depois de um prompt —
também não é amostrado; pertence à linha `ask` que o solicitou.

Quais comandos são amostrados é o **próprio hash do texto do comando**, não um sorteio aleatório,
então o mesmo corpus amostra os mesmos comandos e uma medição sobre essas linhas é reproduzível.
Isso torna a amostra uma de **comandos distintos, não de invocações**: um comando na amostra é
registrado toda vez que roda e um fora dela nunca é, então a contagem de linhas diz o quanto
esses comandos específicos rodaram e multiplicá-la por `sample_rate` não estima nada. Leia-a como
um corpus para reproduzir uma verificação candidata, que é para o que serve.

O `input` de uma linha amostrada é **redigido**, ao contrário do texto de um prompt que o
usuário viu: o valor de toda atribuição e toda flag de credencial, entre aspas ou não (`FOO=…`,
`--password=…`, `--token …`, `-p…`), todo formato de segredo que os [detectores de regra](#rule-telemetry)
combinam, e o diretório home escrito como `~` para que nenhum nome de usuário alcance a linha.
`input_sha256` é sobre o texto **redigido** nessas linhas e sobre o original em toda outra linha:
o hash de um original ao lado do texto redigido colocaria um segredo curto ao alcance de um
ataque de dicionário.

`telemetry.allow_sample_rate` define a taxa e `0` a interrompe;
[telemetry.md](telemetry.md#the-allowed-command-sample) tem o switch, e `decisions: false` o
desliga junto com o resto.

### A alegação de conclusão

Um par opcional de campos é a exceção, só em uma linha `stop-gate`:

```json
{"kind": "decision", "point": "stop-gate", "deterministic_answer": "blocked",
 "completion_claim": "…the suite is green and the change is ready to land.",
 "completion_claim_sha256": "9f21…"}
```

`completion_claim` são os **últimos 2 KiB da mensagem final de assistente do turno**, em bytes e
cortados de volta a um limite de caractere, lidos da transcrição que o evento Stop nomeia porque
um payload de Stop não carrega nenhum texto de assistente próprio. É a própria mensagem do turno: a
varredura para no prompt de usuário que abriu o turno, então um turno que terminou em uma chamada
de ferramenta em vez de uma resposta não alega nada em vez de tomar emprestadas as palavras do
turno anterior. `completion_claim_sha256` é sobre a mensagem sem limite, na mesma regra que
`input_sha256`. Os dois campos existem para que uma alegação de parada possa ser lida contra a
evidência de gate sentada na mesma linha.

Está **desligado por padrão** — `telemetry.completion_claim` em `config.json`,
[telemetry.md](telemetry.md#the-completion-claim-switch) — e com ele desligado a linha é
exatamente a linha acima, sem nenhum desses campos presente.

Com ele ligado, a linha sempre diz algo. Onde não há nenhuma alegação para registrar, ela carrega
`"completion_claim": null` e um `completion_claim_miss` nomeando o porquê, e nenhum hash:

| `completion_claim_miss` | o que aconteceu |
| --- | --- |
| `no_transcript_path` | o evento Stop não nomeou nenhum arquivo — a lacuna do runtime, não da sessão |
| `unreadable` | o arquivo foi nomeado e não pôde ser aberto |
| `oversized` | o arquivo passa de 256 MiB, no qual este hook não vai buscar |
| `no_claim` | o turno foi lido e terminou sem prosa de assistente |
| `error` | o leitor levantou uma exceção; a decisão ainda é registrada |

A leitura é dos últimos 256 KiB do arquivo, então custa o mesmo em uma transcrição de qualquer
tamanho — uma alegação mais antiga que essa janela é lida como `no_claim` em vez de como as
palavras do turno errado.

```sh
bin/harness usage --by decision        # contagens, taxas de resultado e a fração não rotulada por ponto
```

A **fração não rotulada** é a coluna a ler primeiro: uma taxa de resultado sobre as duas decisões
que por acaso foram rotuladas não é evidência sobre o ponto.

`citizen decisions eval` reproduz as linhas rotuladas deste arquivo através de um pacote de
perguntas e relata quão de perto o julgamento as acompanhou, com um limiar ajustado por ponto de
decisão. O que ele mede, o que escreve e o que seus rótulos não provam estão em
[controles de runtime](runtime-controls.md).

## O que um provedor de decisão custou

Um provedor que sai da máquina gasta tokens e tempo de relógio, então cada chamada que faz
escreve uma linha `kind: "decision"` no ledger de uso ao lado das linhas de sessão, e o relatório
a precifica pela mesma tabela:

```sh
bin/harness usage --by provider        # chamadas, status, tokens, dólares e latência por ponto
```

A linha nomeia o ponto de decisão, o modo sob o qual rodou, o status, os ids de modelo
requisitado e retornado, os hashes de pacote e requisição, as contagens de token, a latência em
`ms` e a sessão que perguntou. Nunca carrega o estado enviado, a prosa de uma resposta, um
prompt, um caminho de arquivo ou um valor de ambiente:
`lib/harness_core/decisions/ledger.py` a constrói chave por chave a partir dessa lista e não lê
mais nada. A contraparte é mantida só quando combina com o slug `repo:<name>/<branch>` que o
ledger já deriva, dentro de um comprimento limitado, e como um resumo curto caso contrário — é uma
string de quem chamou e parte do que saiu, então um caminho não pode sobreviver em uma linha
mantida por meses. Uma linha que não pôde ser escrita de forma alguma é registrada em
`usage.errors.jsonl` ao lado do ledger, pelo tipo de exceção e nunca pela mensagem. O que pode
sair da máquina de qualquer forma é uma pergunta separada, respondida em
[controles de runtime](runtime-controls.md).

Quatro coisas valem a pena ler dela:

- **Os status são colunas separadas, não uma taxa de sucesso.** `unknown` é uma resposta que o
  provedor deu e da qual se absteve; `unavailable` é nenhuma resposta de forma alguma. Uma taxa
  que os misturasse diria que o provedor estava funcionando quando estava inalcançável.
- **Uma chamada cujo uso ninguém relatou é `partial`**, contada no rodapé `unpriced` e não
  contribuindo nada à coluna de dólar. Não foi de graça; nada sabe o que custou.
- **Um modelo que a tabela de preços não nomeia também é não precificado.** Nenhum preço para os
  modelos Jev foi lido de uma página de preços de fornecedor, então a coluna de dólar fica vazia
  até que um seja adicionado a `policy/prices.json` ou sobrescrito sob `prices` em `config.json`.
- **O id de modelo retornado pode diferir do requisitado,** que é por que os dois estão na linha:
  um relatório precificado no modelo que o harness pediu seria precificado na taxa errada.
  `citizen doctor` imprime o modelo fixado e o que respondeu por último.

Essas linhas são contadas só neste relatório. Seus tokens foram gastos pelo harness fazendo uma
pergunta em vez de pela sessão, então adicioná-las a um agrupamento por dia, repositório ou
modelo cobraria de uma sessão uma conta que ela não fez.

## Lendo

```sh
bin/harness usage                      # últimos 30 dias, agrupado por dia
bin/harness usage --days 7 --by repo
bin/harness usage --by model           # uma sessão usando dois modelos se agrupa sob os dois, ligada
bin/harness usage --by role            # por tipo de agente: execuções, p50/p75/p90 de saída, p50/p75 usd
bin/harness usage --by stance --stance cost   # tokens por variante de uma dimensão de postura
bin/harness usage --by profile         # tokens por impressão digital de perfil; linhas antigas não atribuídas
bin/harness usage --by decision        # decisões de hook e seus resultados, acima
bin/harness usage --by provider        # chamadas de provedor de decisão, precificadas, acima
bin/harness usage --rescan             # relê transcrições na janela primeiro, depois relata
```

`--by role` lê as linhas de subagente e worker. Uma linha com um diretório `workflow` é agrupada
sob `(workflow)`, impressa por último e nomeada no rodapé, em vez de sob seu `agent_type`,
incluindo uma linha escrita antes de o ledger marcar tais linhas como `unconfined`. Gasto por
tarefa delegada é uma distribuição, não uma média, então imprime três pontos na curva;
`unmeasured` conta as execuções cujo runtime não relatou nenhum número de chamada de ferramenta,
que são nomeadas ali em vez de calculadas na média como zero. Um papel com menos de 30 execuções
é marcado `n<30` na coluna `sample`: um p90 sobre oito execuções é o segundo maior de oito, e um
orçamento re-semeado a partir dele é um chute vestindo um número.

`path` e `over` são os próprios retornos: dos retornos que nomearam um caminho, a fração cujo
caminho resolveu; e dos retornos medidos contra um limite, a fração que passou dele. Um retorno
que não nomeou nenhum caminho não está em nenhum dos dois números, então um papel cujos retornos
são todos vereditos de uma linha imprime `-` para `path` em vez de `0%`, o que leria como um papel
que escreveu caminhos e errou todos. Uma linha escrita antes de a medição existir, uma linha do
Codex e um retorno ao qual nada pôde ser ligado também imprimem `-`.

`--by day` lê as fatias `days` de uma linha quando ela as carrega e recorre à sua data de término
quando não, então uma sessão que rodou por duas semanas é espalhada pelos dias em que gastou. A
janela `--days` então se aplica à data da **fatia**, e uma sessão longa contribui só com seus dias
dentro da janela. A coluna `runs` ainda conta sessões, não sessão-dias: uma linha é contada uma
vez, no dia em que terminou, então uma sessão cuja data de término está fora da janela contribui
com seus tokens dentro da janela e nenhuma execução.

`--by stance --stance <dimension>` agrupa tokens pela variante dessa dimensão — `cost=balanced`
contra `cost=frugal`. Uma linha sem nenhuma postura registrada, e uma linha cujas posturas uma
reescaneada carimbou, se agrupam sob `(unknown)` e são **contadas ali** em vez de descartadas:
deixá-las de fora faria uma variante recém-carimbada parecer todo o histórico do ledger.
`--rules --by stance` é o relatório de acerto abaixo e não muda. `--by stance` sem nenhum dos
dois é recusado, já que nomeia dois relatórios diferentes e adivinhar entre eles seria pior que
perguntar.

`--by profile` agrupa tokens por `profile_fingerprint`, então dois perfis são distinguidos só por
suas linhas. Uma linha que não carrega nenhum se agrupa sob `(unattributed)` e é contada ali. A
impressão digital tem 64 caracteres e a coluna de rótulo 34, o que ainda distingue perfis.

Os agrupamentos de token — `day`, `repo`, `model`, `stance`, `profile` — somam linhas de sessão e
worker e nunca as de um subagente. Os tokens de um subagente já estão dentro do total de sua
sessão; um worker de role-run não tem nenhuma linha de sessão de forma alguma, então deixá-lo de
fora esconderia seu gasto de todo relatório existente.

Uma sessão que trava ou é morta nunca dispara `SessionEnd` e então nunca é registrada ao vivo;
`--rescan` percorre toda transcrição tocada dentro de `--days` e a upserta, que é como você
preenche essas lacunas.

## O que custou

Tokens enganam como medida de gasto. Leituras de cache dominam a contagem e custam uma fração do
input base, e uma mudança que roteia trabalho para um modelo mais barato pode gastar mais tokens e
menos dólares. Então todo agrupamento de token carrega uma coluna `usd`, e `--by role` carrega p50
e p75 em dólares ao lado de seus percentis de saída.

Esses números são equivalentes de preço de tabela de API calculados a partir de contagens de
token, não uma fatura: um plano de assinatura paga de forma diferente, e multiplicadores de modo
rápido e residência de dados não são modelados.

As taxas estão em [`policy/prices.json`](../policy/prices.json): USD por milhão de tokens para
input, output, leitura de cache e escrita de cache, por id de modelo, cada entrada carregando a
data `as_of` em que foi lida e a página de preços do provedor de onde foi lida. Nada no arquivo é
escrito de memória, e um modelo cujo preço não pôde ser confirmado de uma fonte primária está
ausente em vez de adivinhado. Sobrescreva ou estenda-o sob `prices` em `config.json` — veja
[preferences.md](preferences.md).

- **Ids resolvem por correspondência exata** depois da normalização, que coloca em minúsculas,
  remove um prefixo de fornecedor de nuvem, remove um sufixo de janela de contexto e remove um
  sufixo de lançamento — um carimbo de data, um `-v1:0` de revendedor, um `@date`. Então
  `claude-haiku-4-5`, `anthropic.claude-haiku-4-5-20251001-v1:0` e `claude-opus-5[1m]` todos
  alcançam uma entrada de família. Contexto longo não é uma taxa separada: a Anthropic precifica a
  janela completa de 1M tokens na taxa padrão para o Claude 4.6 e posterior. Nada resolve por
  prefixo: uma variante que a tabela não nomeia não é precificada, não cobrada na taxa da sua
  família — `gpt-5.5-pro` é $30/$180 onde `gpt-5.5` é $5/$30. Para precificar uma, adicione-a a
  [`policy/prices.json`](../policy/prices.json) ou sobrescreva sob `prices` em `config.json`.
- **Escritas de cache são precificadas por TTL.** A Anthropic cobra 1,25x do input base para uma
  escrita de 5 minutos e 2x para uma de 1 hora, e o Claude Code relata a divisão sob
  `cache_creation`, então uma linha registra `cache_write_5m` e `cache_write_1h` ao lado do seu
  total de `cache_write` e cada camada é cobrada na sua própria taxa. As duas chaves são aditivas:
  uma linha escrita antes delas existirem não carrega nenhuma e é cobrada por inteiro na taxa de
  5 minutos, o que a **subestima** onde quer que as escritas da sessão fossem de 1 hora — que são
  as do fio principal.
- **O Codex é contado uma vez.** `input_tokens` inclui `cached_input_tokens`, então a linha do
  ledger já guarda a diferença e a parte em cache é cobrada só na taxa de cache;
  `reasoning_output_tokens` está dentro de `output_tokens` em vez de ao lado dele, então nunca é
  adicionado de novo. A OpenAI não publica nenhuma taxa de escrita de cache, então essa coluna
  precifica em zero para uma entrada `gpt`.
- **Um subagente é precificado no próprio modelo.** Os totais de uma sessão do Claude Code já
  incluem os de seus subagentes, que rodaram em outros modelos a outras taxas, então seus tokens
  são retirados dos totais do pai, cada um é precificado no próprio modelo e os dois são somados.
  Uma sessão cujos totais não cobrem seus filhos — uma linha escrita antes de a captura de
  subagente chegar — é precificada sozinha, exatamente como seus tokens são relatados sozinhos.
- **Uma sessão que trocou de modelo carrega um detalhamento.** As maiores sessões são as que
  mudaram de modelo, e seus totais sozinhos nomeiam várias taxas sem nenhuma divisão entre elas,
  então uma linha registra `by_model`: contagens de token por id de modelo, cortadas do mesmo mapa
  sobre o qual os totais são somados para o Claude Code e das diferenças de snapshot sob cada
  `turn_context.model` para o Codex, e descartadas por inteiro se não somarem até a linha. Uma
  linha que carrega uma é precificada a partir dela e de nada mais; uma linha multimodelo escrita
  antes de o mapa existir permanece não precificada. Uma parte nomeada para um turno gerado pelo
  harness — `<synthetic>` — é pulada quando não gastou nada e deixa a linha não precificada
  quando gastou.
- **Não precificado não é grátis.** Uma linha com um modelo desconhecido, uma linha multimodelo
  sem detalhamento, e uma linha marcada `partial` são todas contadas no rodapé `unpriced` e não
  contribuem nada à coluna. Um número em dólar subestimado é pior que um ausente, porque nada na
  linha diz que está incompleto. Um worker de role-run cuja linha nomeia um alias de modelo em vez
  de um id — `opus`, `fable` — não é precificado pela mesma razão, assim como uma variante de uma
  família listada que a tabela de preços não nomeia.
- **Uma fatia de dia guarda tokens e nenhum modelo**, então o custo de uma sessão de vários dias é
  alocado através de seus dias pela fração de tokens de cada dia. Para uma sessão de um único dia,
  que é quase todas elas, a fração é um e a alocação é exata; para uma longa é uma alocação e não
  uma medição.

A tabela foi verificada contra um runtime que relata seu próprio número: uma sessão do Claude
Code registrada e seu subagente, cujo `total_cost_usd` relatado pela CLI foi $0,60097775,
precifica em $0,60097775 — um desvio de 0,000%, contra os 2% aos quais o relatório é sujeito.
`tests/test_usage_prices.py` guarda a forma de token dessa sessão como uma fixture.

Os mesmos números viajam em uma linha exportada como `harness.usd`, calculados pelo mesmo
código — a CLI e o hook de exportação ambos carregam `policy/hooks/pricing.py` em vez de um dos
dois manter uma segunda cópia das taxas. O que um número de dólar exportado significa está em
[telemetry.md](telemetry.md).

Preços ficam obsoletos silenciosamente enquanto o relatório continua imprimindo dólares, então
`citizen doctor` nomeia o `as_of` mais novo na tabela e avisa quando tem mais de 90 dias. Releia
o `source` de cada entrada e atualize o arquivo; esse é todo o custo de manutenção, e nomeia um
modo de falha real.

### Re-semeando orçamentos

Os orçamentos por papel de uma variante de custo são medidos, não adivinhados, então ficam
obsoletos conforme os papéis mudam. Rode `bin/harness usage --rescan --by role` sobre uma janela
larga o bastante para conter algumas dezenas de execuções, leia a coluna p75 para o papel — os
números distribuídos são esse ponto na curva — e escreva-o na linha da sua variante como
`budget_output_tokens` e `budget_tool_calls`. Um papel ainda marcado `n<30` não ganhou uma
re-semeadura; alargue a janela ou deixe o número onde está.

## O que a taxa de acerto diz

`hit` é `cache_read / (input + cache_read + cache_write)` — a fração do prompt servida a partir
do cache em vez de paga à taxa de input base. `claude/skills/delegation-tiering/SKILL.md` coloca
o cache no Gate 0: é uma alavanca de orquestrador, não de subagente, porque um subagente começa
um prefixo novo que não compartilha nenhum cache com seu pai e fan-outs paralelos com prefixos
idênticos cada um paga preço cheio. Então um repositório cuja taxa de acerto cai conforme sua
contagem de `subagents` sobe está pagando pela delegação duas vezes; verifique os limites de
retorno antes de recorrer a uma camada diferente. Essa queda não apareceu no único corpus contra
o qual foi medida: através de 137 sessões em uma máquina, a taxa de acerto foi 97,0% com zero
subagentes, 97,2% com 1–6, 97,3% com 7–50 e 97,1% com 51 ou mais — então trate a frase acima como
algo a verificar nos seus próprios dados em vez de como uma expectativa.

### Se o prefixo se manteve

`hit` diz o quanto do prompt foi servido a partir do cache. Não diz se o prefixo em cache
sobreviveu à sessão, e isso é o que `primitives/rules/cache-hygiene.md` de fato pede: uma mudança
no meio da tarefa no conjunto de ferramentas, na lista de servidores MCP, no modelo ou no controle
de esforço transforma as leituras de cache do próximo turno em escritas de cache, e o único
sintoma visível é uma conta maior. `bin/harness usage --by prefix` relata a razão de erro por
sessão:

```
miss = cache_write / (cache_read + cache_write)
```

A fração do prefixo que o provedor teve que reescrever em vez de servir, calculada a partir dos
dois campos que toda linha já carrega. Nenhum hook novo, nenhum evento novo, nada registrado que
não fosse registrado antes. Uma razão baixa é uma sessão que manteve um prefixo; uma alta é uma
sessão que recomprou seu contexto.

**O que o número exclui: seus subagentes.** Uma linha de sessão do Claude Code dobra os tokens de
seus subagentes nos próprios, e todo spawn escreve um prefixo novo que não compartilha nada com
seu pai, então uma sessão que manteve seu contexto perfeitamente através de seis fan-outs seria
lida como uma que recomprou um quarto dele. Os próprios `cache_read` e `cache_write` das linhas de
subagente são subtraídos dos da sessão antes de a razão ser tomada, e as colunas do relatório são
tituladas `own_read` e `own_write` por essa razão. Uma sessão cuja contagem de `subagents` é maior
que as linhas de subagente encontradas para ela, ou cuja subtração fica negativa, relata
`unknown`: o restante não seria o seu prefixo. Uma sessão do Codex não dobra nada e nada é
subtraído.

O relatório também nomeia onde a razão deu um salto. As fatias `days` de uma linha carregam os
mesmos campos de cache e a contagem de turno daquele dia, então a razão é recalculada por fatia e
o primeiro turno de uma fatia que subiu vinte pontos ou mais é impresso como
`turn 7 (2026-09-19): 2% -> 80%`. Uma sessão que deu dois saltos relata a subida mais aguda, não a
primeira. Uma fatia que não consegue afirmar uma razão quebra a cadeia em vez de ser comparada
através, então `before -> after` é sempre uma fatia contra a fatia anterior a ela. Esse é o
índice mais fino que o ledger consegue sustentar honestamente: números de cache por turno não são
registrados, e inventar um evento para registrá-los estava fora de escopo. Uma sessão com um
único dia de fatias, ou nenhum, relata sua razão e nenhum salto.

**Uma sessão que fez qualquer spawn não relata nenhum salto de forma alguma**, impresso como
`not measurable (subagents)`. Suas fatias dobram os mesmos tokens de subagente por dia, uma linha
de subagente não carrega nenhum mapa `days` para subtrair, e o único salto que essas fatias
poderiam mostrar é o dia do fan-out.

**Ele mede, não aplica.** Nada nega, avisa sobre ou bloqueia uma mudança de prefixo, aqui ou em
qualquer outro lugar no harness; o número é retrospectivo e somente-leitura, e o que fazer sobre um
salto é decisão da sessão.

Uma sessão cujas linhas não carregam nenhum campo de cache relata `unknown`, nunca zero, e o
mesmo vale para toda sessão do Codex: esse runtime relata um número de leitura em cache e nenhum
número de escrita de cache de forma alguma (`adapters/codex/capabilities.json`), então nenhuma
razão sobre seu par significa nada. Em um runtime que de fato relata escritas, leituras em cache
contra zero escritas não são desconhecidas mas o melhor caso que existe: um dia que serviu seu
prefixo inteiro. O rodapé conta as sessões desconhecidas separadamente.

## Telemetria de regra

O motor por baixo — o schema de evento, a decomposição de shell, o registro e os seis detectores
genéricos — é o [ruleprobe](https://github.com/JakeSelby/ruleprobe), empacotado como um wheel em
`lib/vendor` ao lado do `tomlkit`; `claude/hooks/rule-detectors.py` é o pacote de regras deste
repositório sobre ele, guardando os detectores que são sobre estas regras e os opt-outs.

A mesma passagem que soma os tokens constrói a lista de eventos que
`claude/hooks/rule-detectors.py` documenta e roda todo detector sobre ela, então o registro
carrega três campos a mais:

- `rules` — `{detector id: hits}`, detectores sem nenhum acerto omitidos. Um acerto é uma
  contagem, nunca um trecho: `usage.jsonl` não guarda texto de comando nem texto de mensagem.
- `counts` — chamadas de ferramenta `web_search`, `agent` e `ask_user`, registradas quer um
  detector dispare ou não, porque as limitadas valem a pena observar abaixo do seu limite.
- `stances` — o mapa `dimension: variant` resolvido, para que um acerto possa ser lido contra a
  postura que estava em vigor. A escada é a da CLI: padrões embutidos, depois
  `~/.config/agent-harness/config.json`, depois `HARNESS_STANCE_<DIMENSION>`, que todo hook
  herda da sessão.

Um registro que está ausente, quebrado ou uma versão de distância custa ao registro seu `rules` e
`counts` e nada mais: o registro é escrito com `rules_error` nomeando a falha. Um registro sem
nenhum mapa `rules` é uma lacuna, não uma sessão sem acertos — é deixado de fora de toda contagem
e do denominador da fração, e o relatório diz quantas havia.

Uma reescaneada não consegue saber as posturas sob as quais uma sessão passada rodou, só as
deste minuto. Ela deixa `stances` de um registro intacto quando os tem e caso contrário carimba
as atuais com `"stances_source": "rescan"`, o que `--rules --by stance` então exclui pelo nome e
o relatório de token agrupa sob `(unknown)`. As posturas carimbadas ainda dirigem os detectores,
então contagens de acerto de fato são preenchidas retroativamente.

### O que cada detector procura

| Detector | Regra | Acerta em |
| --- | --- | --- |
| `transcript-hygiene/whole-file-cat` | transcript-hygiene | um `cat <caminho único>` solitário: sem pipe, sem filtro, sem heredoc, sem redirecionamento |
| `transcript-hygiene/unfiltered-find` | transcript-hygiene | `find <dir>` sem nenhum predicado de filtragem e nada consumindo sua saída |
| `transcript-hygiene/model-wrote-no-cap` | transcript-hygiene | um brief de `Agent` que o modelo escreveu sem limite de palavra, para um agente cuja definição não carrega nenhum |
| `delegation/executed-from-summary` | delegation | um comando Bash cuja primeira aparição na sessão foi dentro de um retorno de `Agent` |
| `verification/no-verify` | verification | um commit ou push que passa por cima dos próprios hooks do repositório |
| `secrets/secret-in-write` | secrets | uma string em formato de segredo escrita em um arquivo ou em um corpo de heredoc |
| `secrets/git-add-secret-file` | secrets | `git add` de um caminho cujo nome diz que guarda uma credencial |
| `research/search-over-cap` | research-and-verification | a busca web que leva a sessão além do limite por sessão |
| `cache-hygiene/model-switch` | cache-hygiene | uma mudança de modelo no meio da sessão, que reconstrói o prefixo em cache |
| `cache-hygiene/compact` | cache-hygiene | cada limite de compactação na transcrição, exceto sob uma variante `cost` que permite compactação (`max`) |
| `voice/banned-opener` | voice-and-format | uma mensagem final abrindo com uma frase que o estilo de saída proíbe, ou fechando com uma |
| `voice/second-table` | voice-and-format | dois ou mais blocos de tabela em uma mensagem final |
| `voice/scaffold-leak` | voice-and-format | sob a voz `concise`, uma mensagem final vestindo rótulos de seção de um template de resposta |
| `voice/heading-first` | voice-and-format | sob a voz `concise`, uma mensagem final cuja primeira linha é um cabeçalho markdown |
| `decisions/no-alternatives` | decisions-and-plans | uma mensagem final cuja linha de recomendação não nomeia nenhum outro caminho |
| `autonomy/confirmed-irreversible` | autonomy | um comando rerodado atrás do marcador `HARNESS_CONFIRMED=1` |
| `autonomy/denied-by-grade` | autonomy | um resultado de Bash carregando a assinatura de negação do hook de classificação |
| `commits/non-conventional` | commits | um assunto de commit que não é uma linha Conventional Commit |
| `commits/missing-trailer` | commits | uma mensagem de commit sem nenhuma linha `Co-Authored-By:` |

Uma regra sem nada que uma transcrição consiga decidir opta por sair pelo nome em `OPT_OUT`, com
o motivo; `citizen lint` falha em um arquivo de regra que não tem nem detector nem opt-out.

Todo detector lê uma chamada de ferramenta como o modelo a escreveu. Uma transcrição registra a
entrada `tool_use` do modelo, enquanto o `updatedInput` de um hook `PreToolUse` é escrito em uma
linha `attachment` separada que a varredura não lê, então nenhum detector consegue ver o que um
hook entregou. `transcript-hygiene/model-wrote-no-cap` é nomeado por isso: conta briefs que
`brief-guard` depois limitou, e um acerto é a omissão do orquestrador e não um brief sem limite
chegando a um subagente. Era chamado `transcript-hygiene/brief-without-cap`, que lia como a
segunda coisa; `rule-detectors.RENAMED` mapeia o id antigo para o novo. O arquivo do ledger nunca
é reescrito por uma renomeação — `--rules` dobra esse mapa enquanto lê, nos três agrupamentos —
então um registro escrito sob o id antigo relata sob o novo e a série não se divide.

### Lendo o relatório

```sh
bin/harness usage --rules                      # acertos por detector nos últimos 30 dias
bin/harness usage --rules --by repo            # sessões, acertos e os três principais por repositório
bin/harness usage --rules --by stance          # o mesmo, por dimension=variant
bin/harness usage --rescan --days 30 --rules   # preenche retroativamente das transcrições, depois relata
```

Os agrupamentos e as duas anotações estão em [quais regras dispararam](#which-rules-fired) acima.
Todo id de registro ganha uma linha, incluindo os sem nenhum acerto, então uma regra não
observada é visível em vez de ausente.

Duas funcionalidades distribuídas que este ciclo capturou — uma postura medida como nunca
disparando e um hook cuja métrica não se moveu — estão escritas com seus números e comandos em
[pego em flagrante](caught-in-the-act.md).

Essas duas são as pontas de uma escada. Uma regra que dispara na maioria das sessões é prosa que
falhou: o agente a leu e passou por cima mesmo assim, então quer ser um hook, onde a decisão é
tomada por ele em vez de pedida a ele. Uma regra não observada por um mês é ou mantida
honestamente pelo modelo ou impossível de observar daqui, e de qualquer forma pode deixar as 200
linhas sempre carregadas e viver na skill que a explica.
