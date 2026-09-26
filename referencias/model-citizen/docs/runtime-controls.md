# Controles de runtime

Um único motor de política compartilhado (`lib/harness_core/lifecycle.py`) consome eventos
normalizados. Adaptadores nativos registram um coordenador por evento de ciclo de vida e traduzem
decisões. Uma negação vence sobre uma permissão ou reescrita; reescritas independentes se compõem.
O Codex não consegue pausar com a decisão de hook `ask` do Claude, então uma requisição que exige
confirmação é negada com seu motivo. A filtragem de saída nunca concede um comando de shell não
aprovado só para reescrevê-lo.

O registro de hook não é ativação. O Codex exige confiança nativa para o conteúdo atual de hooks;
aceite-a no cliente. `citizen trust` autoriza separadamente rodar o gate de um repositório e não
fabrica confiança de hook nativa. Restrições nativas de permissão sempre têm precedência. Busca
hospedada e continuação através de um shell já em execução não são universalmente interceptadas.
Hooks auxiliam a política de fluxo de trabalho; não são um substituto para o sandbox de runtime.

O gate de parada faz hash do HEAD, das diferenças binárias preparadas e não preparadas, do conteúdo
de arquivos não rastreados, da identidade do repositório e da definição do gate. Comandos
compartilham um shell, então `cd` e `export` persistem. Um gate que muda a árvore, expira, ou
esgota seu orçamento de novas tentativas fica não verificado, nunca verde. O orçamento de novas
tentativas é contado por sessão, então sessões compartilhando um checkout não se resetam
mutuamente. Erros inesperados de gate bloqueiam. Escritas de estado são atômicas.

Papéis restritos usam [workers de CLI isolados](role-workers.md), com resolução de papel/postura
compartilhada e controles de ferramenta nativa fixos. O harness valida e publica conteúdo de
planner em um novo caminho de artefato aprovado. Padrões diretos de papel nativo não são
confinamento: o Codex consegue reaplicar sobrescritas de permissão do pai. Hooks de ciclo de vida
ativos roteiam lançamentos de papel restrito para o comando de worker. Qualificação nativa ainda é
exigida; não trate uma projeção ou teste unitário como certificação.

Definições de agente nativas são resolvidas na sincronização a partir da variante de custo em
vigor. Um papel que a postura selecionada não move continua como um symlink para a projeção
commitada, exatamente como antes; um papel que ela move é renderizado no diretório home do Claude,
então a classe e o esforço com que roda são escritos no arquivo em disco em vez de decididos por
sessão. Um `HARNESS_STANCE_COST` com escopo de sessão, como qualquer `HARNESS_STANCE_*`, fica
naquela sessão e não os move até o próximo `citizen sync`; um [worker de papel](role-workers.md)
isolado resolve sua classe, esforço e orçamento flexível por execução, a partir da mesma tabela e
da mesma precedência, então ele segue essa seleção de sessão e um papel restrito não consegue
rodar de um jeito como worker e de outro como definição. Uma entrada de
`role_bindings.<runtime>.<role>` ainda vence sobre a linha da variante. O roteamento de spawns que
não nomeiam nenhuma definição de agente se desliga sozinho em um workspace que distribui seus
próprios `.claude/agents/worker-*.md`, já que uma definição de projeto supera a do usuário e rotear
para ela colocaria as instruções desse repositório em todo spawn sem nome; o spawn roda como
escrito e o hook diz isso.
Antes de rebaixar para um lançamento que só linka essas definições, ou selecione `balanced` sem
nenhuma vinculação de papel e sincronize uma vez, o que restaura os links, ou rode
`citizen uninstall`. Sincronizar um diretório home de volta com o lançamento mais antigo não é
suficiente por si só: arquivos de papel que o lançamento mais antigo não distribui permanecem em
`~/.claude/agents` e `~/.codex/agents`, e seu `citizen diff` não relata nenhum desvio, porque
código que nunca conheceu esses papéis não consegue sentir falta deles. `citizen uninstall` antes
do rebaixamento é o remédio; ele remove o que o lançamento mais novo escreveu.

O roteamento tem escopo de sessão pela mesma razão que o esforço tem escopo de sincronização: o que
um agente nativo é vem de arquivos lidos em um momento, não de uma busca ao vivo. O início de
sessão registra quais definições o registro da sessão continha, e um spawn sem nome só é roteado
para um worker que essa sessão consegue resolver. Um `startup` escreve o registro, um `resume`
só pode estreitar um existente, e `clear` e `compact` o deixam intacto. Uma sessão que recarrega
uma definição instalada depois de ela ter começado é informada disso pelo runtime, na própria
transcrição, e roteia para esse worker a partir do turno em que ouve isso; uma sessão que não é
informada de nada — uma headless nunca recarrega — mantém o comportamento anterior e é pedida uma
vez para iniciar uma nova sessão, que continua sendo o remédio certo depois de uma sincronização.
Qualquer falha em responder à pergunta de roteamento deixa o spawn sem rota e silencioso, nunca
recusado.

Registros de uso identificam o runtime e a versão de runtime disponível. Snapshots cumulativos de
token do Codex são contados uma vez; medições ausentes permanecem nulas e relatórios rotulam
totais parciais. Falhas de detector são relatadas separadamente e excluídas dos denominadores de
sessão limpa. Contenção de lock recusa uma sobrescrita; falhas de worker desacoplado vão para
`usage.errors.jsonl` ao lado do ledger de uso. Adaptadores de transcrição não conseguem observar
chamadas de ferramenta aninhadas ausentes da transcrição e não provam que uma postura causou um
comportamento.

Um limite em uma leitura de vários itens é um orçamento: peça à fonte para do mais novo ao mais
antigo onde puder ser pedido, verifique a ordem que de fato chega, recuse a página quando não
estiver decrescente, e registre na declaração qual extremidade é descartada — quando várias fontes
competem por um orçamento, descarte a menos autoritativa primeiro. A página de sessões do Remote
Control (`remote_control.fetch_sessions`) e o `OPEN_TAIL` do feed de uso ambos mantêm o mais novo,
porque uma correção que chega por último é a que um histórico aparado não pode perder. O endpoint
de sessões não recebe parâmetro de ordenação e é ordenado por `last_event_at`, então essa leitura
afirma a ordem em vez de pedi-la, e uma recusa é relatada como não verificada, nunca como nada
encontrado. Uma contagem sobre uma página que carrega um cursor nomeia a página que contou, não a
conta.

## IDs de hook

Todo módulo de política que responde a um evento de ciclo de vida tem um id, seu nome-base sob
`policy/hooks/`, e cada id é uma unidade do tipo de switch `hooks` no
[documento de seleção](preferences.md#the-selection-document):

| Id | Responde |
| --- | --- |
| `allow-plan-webfetch` | PreToolUse em WebFetch no modo plano |
| `allow-readonly-bash` | a permissão de Bash somente-leitura, as permissões do modo plano e `plan_allow_tools` |
| `approvals` | UserPromptSubmit: registra um prompt que é só tokens `approve <code>`, para `grade-bash` em modo auto, só Claude Code |
| `brief-guard` (core) | PreToolUse em um spawn |
| `filter-output` | PreToolUse em Bash |
| `grade-bash` (core) | classificação de Bash, seu ask ou deny, consumindo uma aprovação em modo auto, guardando o armazenamento de aprovações, e as linhas de Bash no log de decisões |
| `harness-session` | SessionStart |
| `neutralize-tool-output` (core) | PostToolUse |
| `stage-user-files` | PreToolUse em SendUserFile, só Claude Code |
| `stop-gate` (core) | Stop |
| `tier-agent-spawns` | roteamento de banda de um spawn, e o aviso de descritor de integração |
| `usage-feed` | UserPromptSubmit, SubagentStart, SubagentStop e PostToolUse em um spawn, só Claude Code |
| `usage-log` | SessionEnd |
| `validate-plan-card` | PostToolUse em um arquivo de plano |

`citizen config set hooks.<id> off` desliga um, e se aplica a partir do próximo evento sem
sincronização: o dispatcher resolve a seleção a cada evento e não carrega nem roda um módulo cujo
id é `off`. As bibliotecas que esses módulos carregam (`decisions`, `posture`, `pricing`,
`telemetry`, `rule-detectors`, `otel-headers`, `filter-lines`) não têm id nem switch. Negar todo
spawn sob `delegation: off` é a própria resposta da postura e permanece com qualquer id
desligado. O confinamento de papel também não tem id: as recusas de papel restrito,
`harness-role:`, framework e evasão, e a guarda de lançamento de Workflow rodam com todo hook
desligado, então desligar `tier-agent-spawns` para o roteamento de banda e nunca deixa um papel
restrito rodar na sessão.

Os quatro ids centrais aplicam em vez de auxiliar. Uma camada só pode desligar um quando a
configuração de usuário define `"core_switches_acknowledged": true`; `config set`, `sync` e
`citizen selection` o recusam caso contrário, antes de qualquer escrita, e o mesmo vale para
retirar o reconhecimento enquanto um hook central está desligado. O reconhecimento é lido só da
configuração de usuário, porque um arquivo de projeto, sessão ou modo só pode carregar chaves de
seleção. Um hook que encontra um `off` não reconhecido continua rodando, e o mesmo vale para todo
hook quando a seleção não resolver.

O adaptador do Codex despacha através do mesmo `lifecycle.py` e lê o mesmo mapa de id. Não há
nenhum id só do Codex; um id cujo evento o Codex não dispara, como `usage-feed`, simplesmente
nunca roda ali. `citizen catalog` lista cada id com o tipo `hooks`, sua fonte e se é central.

## Provedores de decisão

`lib/harness_core/decision.py` guarda um contrato agnóstico de transporte para a pergunta "esta
ação pode prosseguir, e como": `decide(action, counterparty, context)` retorna uma `Decision`
carregando um resultado de `allow`, `ask` ou `deny`, um nível de autonomia de 1 a 3, o nome do
provedor, um motivo, e um bloco `injected_cognition` de correspondências de regra e mensagens
opcionais de agente e usuário; `record(action_outcome)` anota como uma ação se resolveu;
`learn(approval_stream)` recebe aprovações passadas e pode ser um no-op. A forma
deliberadamente espelha a superfície `decide`/`record`/`learn` de um plano de controle externo,
para que um provedor hospedado possa ser adicionado depois sem um segundo contrato. Uma ação
nomeia uma classe — `coding.shell_exec`, `coding.git_commit`, `coding.git_push`, `coding.deploy`,
`coding.file_write`, `coding.pr_merge` — e a classe de comando onde uma é conhecida. Uma
contraparte é um slug `repo:<name>/<branch>`. `<name>` é o do repositório, lido do seu diretório
git comum, então uma worktree linkada em um diretório nomeado por sua tarefa nomeia o repositório
ao qual pertence; o campo `repo` do ledger de uso mantém o nome do diretório da worktree.

Dois provedores são distribuídos. `none` é o padrão: toda ação é permitida no nível 3 com o motivo
`governance: none`, e nenhum arquivo de política é lido. `local` lê dois arquivos de política em
um schema (`defaults`, `pairs`, `caps`): um `governance.json` em nível de usuário ao lado de
`config.json` (`~/.config/agent-harness/governance.json`, sob `HARNESS_HOME` quando definido), e
`.agent-harness/governance.json` no repositório. Ele os mescla antes de resolver qualquer coisa.
O arquivo do repositório vence para um padrão de classe e para cada classe dentro de um par;
limites (caps) se combinam pelo valor menor, então nenhum dos dois arquivos consegue levantar um
teto que o outro definiu. O arquivo do usuário guarda níveis que se aplicam em toda parte, e
níveis para repositórios que não carregam nenhum arquivo próprio.

```json
{"defaults": {"coding.git_push": 2},
 "pairs": {"repo:agent-harness": {"coding.pr_merge": 3},
           "repo:agent-harness/main": {"coding.git_push": 1}},
 "caps": {"coding.deploy": 2}}
```

Um nível é então resolvido nesta ordem: o par exato `repo:<name>/<branch>`, depois o par de
repositório inteiro `repo:<name>`, depois o padrão da classe de ação, depois o nível que a postura
autonomy implica (`execute` 3, `confirm-writes` 2, `ask` 1, e 1 quando nada resolve). O nome de
repositório em um slug termina no primeiro `/`, então uma branch como `feat/x` ainda alcança
`repo:<name>`. Um limite é um teto que o nível resolvido nunca ultrapassa; `coding.deploy` carrega
um limite embutido de 2 que um arquivo de política pode baixar e não pode levantar, e
`coding.pr_merge` não tem nenhum limite embutido. O motivo e cada correspondência de regra nomeiam
o arquivo que forneceu o nível ou o limite, ou dizem `autonomy stance` ou `built-in`. O nível 3
permite toda classe, o nível 2 pergunta na classe 2 e acima, o nível 1 pergunta na classe 1 e
acima, e uma classe desconhecida é julgada como 1. Um arquivo de política em qualquer nível que
não possa ser honrado como escrito é um erro nomeando esse arquivo, nunca uma "sem política"
silenciosa. Ambos os provedores escrevem no ledger `decisions.jsonl` existente e nenhum alcança a
rede.

Um terceiro provedor, `jev`, vive em `lib/harness_core/decisions/jev.py` e responde pela rede. Ele
pergunta um pacote de perguntas validado — um julgamento de `choice` e uma severidade de `score` —
sobre a classe de ação, a contraparte, a classe de comando e no máximo uma string de comando e um
resumo, e carrega o provedor determinístico `local` por baixo. O serviço não tem nenhum resultado
de abstenção, então toda pergunta de `choice` precisa oferecer uma opção `unknown` explícita e um
pacote sem uma é recusado antes de qualquer coisa ser enviada; `unknown` e uma resposta abaixo do
limiar de confiança significam ambos "use a resposta determinística". Um julgamento pode
transformar um `allow` em um `ask` e nunca pode ampliar uma decisão ou produzir um `deny`. Todo
outro resultado falha aberto para a decisão determinística: nenhuma chave, um timeout, um
orçamento esgotado, uma resposta malformada, uma exceção inesperada. Cada chamada escreve uma
linha `event` carregando o status, os ids de modelo requisitado e retornado, os hashes de pacote e
requisição, o uso e a latência, e nunca o estado; `citizen decide` suprime essa linha, porque um
comando de relatório não muda nada. O endpoint precisa ser `https` e o que o abre não consegue
alcançar nenhum outro esquema, já que uma chave bearer vai com toda requisição, e uma requisição é
cobrada contra seu orçamento assim que é enviada em vez de quando tem sucesso, então um endpoint
que falha não pode ter novas tentativas sem limite. Os tetos de token, o endpoint, o formato de
resposta e o mapeamento de status vêm da documentação do fornecedor e não foram verificados contra
o serviço ao vivo a partir deste repositório. Respostas não são determinísticas entre requisições
idênticas, então nada promete que uma requisição repetida responde da mesma forma — só que a mesma
requisição faz o mesmo hash. Credenciais vêm de `TYPESAFE_API_KEY` ou `JEV_API_KEY` no ambiente;
nenhum arquivo de chave é lido.

## O que um provedor que sai da máquina pode fazer, e enviar

Selecionar `jev` não é consentimento para uma requisição. `lib/harness_core/decisions/controls.py`
resolve três perguntas separadas por decisão, e as três precisam concordar antes de qualquer coisa
ser enviada.

**Até onde este ponto pode ser julgado.** `governance.jev.mode` define o padrão e
`governance.jev.modes.<point>` o sobrescreve para um dos pontos de decisão que o ledger já nomeia
— `grade-bash`, `stop-gate`, `tier-agent-spawns`, `brief-guard`, `evasion-deny`. `off` não chama
nada. `shadow` chama, escreve a linha do ledger e retorna a decisão determinística intocada, então
uma resposta pode ser medida antes de ser confiada: nada alcança o modelo ou o usuário. `advise`
coloca o julgamento em `rule_matches`, diz o que `act` teria feito, e não muda nenhum resultado.
`act` deixa um julgamento transformar um `allow` em um `ask`, e nada mais. Todo modo tem `off` como
padrão, então uma configuração escrita antes de isso existir não faz nenhuma requisição; um modo,
um ponto ou um campo que o harness não conhece falha em `citizen config set`, não na primeira
chamada, e um nome de ponto que este harness não conhece lê `off` em vez do padrão. Cada chamada
escreve uma linha de ledger carregando o modo, o rótulo de julgamento, o nível de severidade, o
resultado determinístico e o resultado que agir sobre o julgamento teria alcançado, então uma
resposta `shadow` pode ser comparada contra a decisão que não mudou. Só rótulos: nunca o estado.

**Se algo pode sair de qualquer forma.** `~/.local/state/agent-harness/jev-disabled` é o
interruptor de emergência: enquanto esse arquivo existir, todo modo lê `off`, sem nenhuma mudança
de configuração e nenhuma reinicialização, porque a sentinela é lida por decisão em vez de na
construção. `governance.jev.sentinel` a move, absoluta ou resolvida contra o diretório de estado,
nunca contra o diretório de trabalho. Uma sessão que estava rodando quando o arquivo apareceu para
de chamar, e começa de novo quando é removido, sem reinicialização e sem edição. Uma requisição ao
vivo também precisa de uma chave no ambiente; sem uma, a chamada falha aberta para a resposta
determinística como qualquer outra falha.

**O que pode sair.** `governance.jev.state_fields` é uma lista de permissões, vazia por padrão,
sobre exatamente dois campos: `command` e `summary`. Tudo mais no contexto de quem chama — um
caminho de arquivo, um prompt, um valor de ambiente, saída de ferramenta, prosa de assistente —
não tem nenhum campo em que viajar e nunca é construído na requisição, que carrega a classe de
ação, a contraparte, a classe e a escala de classe além disso. Um campo listado cujo texto combina
com um dos formatos de segredo compartilhados é descartado por inteiro em vez de mascarado, e se
essa lista de padrões não puder ser carregada, nenhum texto livre é enviado de forma alguma. A
redação reconhece os formatos que conhece; uma credencial que se parece com prosa comum ainda
viaja, e é por isso que a lista de permissões é de dois campos e não um vocabulário livre.

`governance.jev.timeout` (2 segundos por padrão, dentro do orçamento do hook),
`governance.jev.max_requests` e `governance.jev.max_tokens` limitam o resto, e limitam uma sessão
em vez de um processo: um hook é um processo novo por evento, então os contadores vivem em
`~/.local/state/agent-harness/jev-spend.json` indexados pelo id de sessão, sob o lock, lidos antes
de cada verificação e acrescidos conforme cada requisição é cobrada. Um arquivo de gasto que não
consegue ser lido ou escrito deixa a contagem em processo intacta em vez de falhar uma decisão.
`citizen doctor` imprime o modo por ponto, a lista de permissões, onde vive o interruptor de
emergência, o modelo que toda requisição fixa, o que a última chamada retornou, e se uma variável
de credencial está definida — pelo nome, nunca pelo valor.

**O que cada chamada custou.** Toda chamada também escreve uma linha `kind: "decision"` no ledger
de uso: o ponto, o modo, o status, os ids de modelo, os hashes de pacote e requisição, os rótulos
de julgamento e severidade, o resultado determinístico e o que um modo `act` teria alcançado, os
tokens, a latência e a sessão que perguntou — e nada do estado que enviou.
`citizen usage --by provider` precifica essas linhas a partir de `policy/prices.json` como
qualquer outra. Um modo de `shadow` é mensurável exatamente por essa razão: a linha existe,
precificada e rotulada, antes de qualquer coisa que o provedor diga poder mudar uma resposta. As
duas linhas param quando `telemetry.decisions` é `false`; veja [telemetria de uso](usage.md).

## Medindo um provedor antes de confiar nele

Uma resposta tipada não é evidência de que era a correta. `citizen decisions eval` reproduz as
linhas rotuladas do [log de decisões](usage.md) — entradas reais, a resposta que o hook
determinístico deu, e o resultado que a sessão mostrou depois — através de um pacote de perguntas
em modo `shadow`, e escreve um relatório em `~/.local/state/agent-harness/jev-eval.json` ou onde
`--out` disser.

```sh
bin/harness decisions eval --replay tests/fixtures/jev/eval/responses.json   # sem socket
bin/harness decisions eval --point grade-bash --split heldout --out report.json
bin/harness decisions eval --live --max-requests 50 --usd-per-mtok 3 --budget-usd 2
```

Um **pacote é versionado**. `lib/harness_core/decisions/packs.py` guarda cada um como um id, uma
versão `major.minor.patch` e o hash do seu conteúdo, congelado na construção para que nada que
guarde um pacote consiga reescrever um critério entre o hash ser tirado e a requisição ser
construída. O provedor coloca o id e a versão em toda linha de ledger ao lado do hash de
requisição, então uma linha resolve para as palavras que foram perguntadas. Um limiar ajustado
contra uma versão não diz nada sobre outra, e `Pack.verify` recusa a discrepância em vez de
carregar o número adiante.

A **divisão é semeada por conteúdo**: um caso cai em `dev` ou `heldout` pelo hash do ponto de
decisão e da entrada limitada que uma requisição de fato carregaria — não o `input_sha256` da
linha, que é sobre o texto sem limite e colocaria uma requisição idêntica nos dois lados — nunca
por `random` e nunca por posição, então uma nova execução reproduz a divisão e adicionar linhas
não reembaralha as antigas. Um hash de requisição encontrado nos dois lados é uma recusa, não um
aviso. Limiares são ajustados só em `dev`; **só o bloco separado (heldout) é evidência**, e o
bloco dev está no arquivo para que um leitor veja o quanto a divisão ajustada lisonjeia o ajuste.
`--split dev` o imprime com uma linha dizendo isso. Não há padrão global, e um ponto sem nenhum
caso dev rotulado é relatado como **não ajustado** em vez de receber o 0,8 distribuído como se
tivesse sido medido.

O ajuste é pontuado sob a própria semântica do provedor: abaixo do limiar, e para `unknown` ou
nenhuma resposta, a resposta determinística é o que é comparado contra o rótulo, porque é isso que
o harness teria feito. Pontuar uma abstenção como um erro empurraria todo ajuste para a confiança
mais baixa do conjunto. O relatório carrega, por ponto e por divisão: acurácia, a mesma taxa para
a resposta determinística sozinha como o alvo a bater, quantos casos o provedor poderia ter mudado
(ele pode apertar um allow em um ask e nunca ampliar um), a confusão por rótulo, a concordância com
a resposta determinística sobre os casos rotulados, uma tabela de calibração sobre a confiança com
seu erro de calibração esperado e um intervalo de bootstrap tirado de índices com hash em vez de um
gerador congruencial linear, tokens de entrada e saída, custo por 1.000 decisões onde um preço foi
dado, os ids de modelo retornados, e um bloco `unusable` contando chamadas indisponíveis, erros e
abstenções — nenhum dos quais nunca é contado como uma aprovação. O relatório não tem relógio nem
caminho absoluto, e nenhum texto de entrada, então duas execuções sobre um log são idênticas byte a
byte e o arquivo pode ser enviado adiante.

O que os rótulos **não** provam está no próprio bloco `caveats` do relatório, e é a primeira coisa
a ler. `grade-bash` registra uma linha só onde o harness disse `ask` ou `deny`, então o conjunto é
os prompts e nunca os comandos permitidos sem um; `ran` é um usuário aprovando algo sobre o qual
foi perguntado, que é evidência de que o prompt era desnecessário e não prova; `not_run` não
separa uma recusa de um turno interrompido. Uma taxa de inversão sobre passagens de `--repeat` é
zero por construção sob `--replay`, porque uma resposta gravada não pode discordar de si mesma, e a
latência sob `--replay` é a do executor e é relatada como não medida em vez de como um número cujo
nome alega que o serviço a produziu.

Execuções comuns precisam de `--replay` e não abrem nenhum socket, o que também é por que uma
reprodução ignora o interruptor de emergência: o interruptor controla requisições e uma reprodução
não faz nenhuma. `--replay` e `--live` juntos são recusados em vez de silenciosamente ordenados.
`--live` precisa de `--max-requests`; `--budget-usd` precisa de `--usd-per-mtok` ao lado, porque
nenhum preço para este provedor é publicado aqui e um teto em dólar que ninguém consegue converter
não é um teto; e uma execução ao vivo com um `governance.jev.state_fields` vazio é recusada como
sem sentido, já que toda requisição carregaria os mesmos quatro campos base e não diferiria em
nada. Uma execução ao vivo envia sob a própria lista de permissões do usuário, então uma avaliação
não consegue enviar um campo que um hook não tem permissão de enviar.

`governance.provider` seleciona um; o padrão é `none`. `citizen decide --action <class>
[--grade N] [--counterparty <slug>] [--json]` imprime a decisão para o repositório atual e os
arquivos de política que leu, cada um marcado presente ou ausente; `citizen doctor` lista os mesmos
arquivos sob o provedor de governança.

### Como a classificação de comando consulta o provedor

`grade-bash` consulta o provedor selecionado para todo comando Bash que a postura autonomy deixa
passar, e só quando `governance.provider` não é `none`. Sob `none` ele não importa nada e sua
saída é exatamente o que a postura sozinha dá.

- **Classificação.** Cada comando simples na linha é classificado: `git push` é
  `coding.git_push`, `git commit` é `coding.git_commit`, `gh pr merge` é `coding.pr_merge`, um
  verbo de deploy que o classificador conhece (sua família `deploy`, `vercel deploy`,
  `netlify deploy`, `cdk deploy`) é `coding.deploy`, e qualquer outra coisa é `coding.shell_exec`.
  Wrappers, executores, `sudo` e o texto `-c` de um shell são vistos através, como o classificador
  os vê através. Um comando somente-leitura, classe 0, não é colocado no provedor, já que nenhum
  nível pergunta na classe 0.
- **Contraparte.** A contraparte de cada comando é o repositório e a branch do diretório em que
  roda: um `git -C <dir>` a move para esse comando, e um `cd <dir>` ou `pushd <dir>` mais cedo na
  linha a move para os comandos depois dele, substituições incluídas. A política de repositório
  lida é o próprio `.agent-harness/governance.json` desse repositório. Um diretório só é
  confiável quando toda mudança antes do comando é um caminho literal; depois de `cd -`,
  `cd "$X"`, `popd`, um `cd` em um subshell, substituição, pipeline ou job em segundo plano,
  `env -C` ou `--git-dir`, a contraparte é `repo:unknown/local`, que nenhum par nomeia, então o
  padrão da classe governa.
- **Só aperta.** O provedor é consultado com a classe do comando, e a resposta mais restrita entre
  os segmentos prevalece. Ele nunca é consultado sobre um comando que a postura já controla, então
  só pode adicionar um prompt e nunca remover um. Um `ask` é um ask em um modo de prompt e, em
  `auto` e `bypassPermissions`, um deny através do mesmo canal que o classificador usa: um código
  de aprovação em `auto`, que a resposta `approve <code>` do usuário deixa passar uma vez, e o
  marcador de confirmação em `bypassPermissions`. Um `deny` do provedor é um deny em todo modo. O
  motivo nomeia a classe, a contraparte, o nível e a regra ou arquivo que o forneceu.
- **Falha fechado.** Um provedor configurado que não consegue responder — um nome de provedor
  desconhecido, um arquivo de política que levanta `PolicyError`, qualquer outra exceção — faz o
  comando perguntar, nomeando o erro. Nunca recorre a permitir.
- **Arquivos de política.** Uma escrita de agente no `governance.json` em nível de usuário ou em
  qualquer `.agent-harness/governance.json` é uma ação de nível 1: sempre perguntada. Um comando
  Bash que não é somente-leitura e nomeia qualquer um dos dois arquivos, ou escreve um através de
  um redirecionamento, `tee`, `sed -i`, `cp`, `mv` ou um escritor de caminho semelhante, pergunta;
  um `Write`, `Edit`, `MultiEdit`, `NotebookEdit` ou `apply_patch` em um deles também pergunta, e
  em modo `auto` é recusado com um código de aprovação cobrindo exatamente essa edição uma vez. O
  `config.json` do usuário é guardado da mesma forma, por alvo de escrita de Bash e por ferramenta
  de arquivo, e o mesmo vale para qualquer comando `harness config set governance...`: a
  configuração seleciona o provedor, então sem a guarda um agente poderia desligar a governança em
  vez de editar uma política.
- **Linhas.** Cada decisão que o hook pede é uma linha `governance` em `decisions.jsonl`, possuída
  por `hooks/grade-bash`, cujo `input` registra a classe de ação, contraparte, nível, classe,
  resultado e provedor, e nunca o texto do comando. `telemetry.decisions: false` para essas junto
  com o resto.

O início de sessão verifica a configuração de uma integração declarada sem instalá-la. A
instalação continua explícita. Veja [continuação de tarefa](task-continuation.md), a
[integração com o BMad](bmad.md), [posse da instalação](runtime-installation.md), e o catálogo de
compatibilidade para evidência de qualificação.
