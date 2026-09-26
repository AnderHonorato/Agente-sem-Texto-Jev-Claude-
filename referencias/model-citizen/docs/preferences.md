# Preferências

Existem dois tipos de preferência, e são configuradas de formas diferentes porque o Claude Code lê
o texto de regra literalmente: não há substituição de variável dentro de uma regra ou do
CLAUDE.md.

Nove eixos de postura são distribuídos, e só três deles se ligam a mecanismos de aplicação hoje:
`autonomy` define qual grau de comando de shell para e pergunta, `delegation` muda como um spawn é
roteado, e `cost` resolve uma classe, um esforço e um orçamento flexível por papel. Os outros seis
são prosa que troca de forma limpa e não adquire nenhum controle aplicado por ser trocada.
`citizen usage --rules --by stance` agrupa acertos de regra pela variante em vigor, então um
switch pode ser verificado em vez de suposto.

## Identidade

O bloco `identity` de `~/.config/agent-harness/config.json` (`name`, `pronouns`, `role`,
`github`, `timezone`) é renderizado em `~/.claude/CLAUDE.personal.md` a cada sincronização. Tudo
que você escreve abaixo do marcador `<!-- harness:personal-below -->` nesse arquivo sobrevive a
uma nova renderização; é também ali que pertence um perfil pessoal de voz de escrita.
Regras rastreadas nunca carregam um nome; são escritas em segunda pessoa.

Sobrescritas de ambiente: `HARNESS_IDENTITY_NAME`, `HARNESS_IDENTITY_PRONOUNS`, e assim por diante.

`expertise` é `expert` (o padrão, e para o que toda configuração anterior a esse campo resolve) ou
`beginner`. Ele seleciona um parágrafo do arquivo pessoal: `expert` pula fundamentos, `beginner`
diz o que cada passo e comando faz, define termos no primeiro uso, e não assume nenhum
conhecimento prévio de programação, controle de versão ou linha de comando. É o único campo de
identidade que muda comportamento em vez de descrever você.

`citizen init` escreve o arquivo inteiro perguntando, e `citizen config set identity.name "…"`
muda um único campo. Nenhum dos dois precisa de um editor. Até que `name`, `role` e `github`
difiram do arquivo de exemplo, `sync` e `doctor` dizem isso: o que eles guardam é o que o agente
acredita sobre você, então uma configuração deixada sem edição faz com que ele se dirija a você
pelo placeholder. `pronouns` e `timezone` nunca são relatados, porque `they/them` e `UTC` são
respostas que alguém poderia querer dizer de verdade.

## O documento de seleção

Toda unidade instalada é selecionável a partir de uma única forma JSON: `mode`, depois um objeto
por tipo. Um tipo é `stances`, cujas dimensões escolhem uma variante nomeada, ou um dos tipos de
switch `rules`, `hooks`, `skills`, `workflows` e `roles`, cujas unidades são `on` ou `off` e têm
`on` como padrão.

```json
{"mode": "minimal",
 "stances": {"testing": "required"},
 "rules": {"decisions-and-plans": "off"},
 "hooks": {"validate-plan-card": "off"},
 "skills": {}, "workflows": {}, "roles": {}}
```

A mesma forma é lida de cinco lugares e resolvida por uma única função, `posture.selection()`,
nesta precedência, a mais baixa primeiro:

1. **`default`** — as variantes de postura embutidas, e `on` para todo switch.
2. **`mode:<name>`** — `modes/<name>.json` em uma raiz de primitivo, para o modo que a camada mais
   alta nomeia. Fica acima de uma postura que `citizen init` escreveu como padrão (`init`); como, e
   o que os modos distribuídos mudam, está em [modes.md](modes.md).
3. **`user`** — `~/.config/agent-harness/config.json`.
4. **`project`** — o arquivo que `HARNESS_PROJECT_CONFIG` nomeia.
5. **`session`** — o arquivo que `HARNESS_SESSION_CONFIG` nomeia, depois `HARNESS_MODE` e
   `HARNESS_STANCE_*`, que são atalhos para a mesma camada.

`citizen selection --json` imprime o resultado: toda unidade de todo tipo com seu valor, mais um
objeto `sources` na mesma forma nomeando a camada que definiu cada uma. Essa saída é lida de volta
inalterada como um arquivo de sessão. `citizen stances` continua sendo a visão só de postura;
`citizen config set rules.<name> off` escreve um switch, e a mesma forma funciona para `skills`,
`workflows` e `roles`, e para os ids de `hooks` em [controles de runtime](runtime-controls.md#hook-ids).
Ele recusa um switch que deixaria um módulo `on` dependendo de um `off`, então desligue o
dependente primeiro. O que a sincronização faz com uma unidade `off` está em
[o modelo de sincronização](sync-model.md).
`sync` projeta só as camadas do usuário; uma camada de projeto ou sessão fica na sessão que a
definiu, e um worker isolado registra a seleção da sessão que o lançou.

Uma seleção carrega só seleções. Um arquivo de projeto, sessão ou modo que carrega qualquer outra
chave — `identity`, `permissions`, a flag `manage` de um runtime, `primitive_roots`, `telemetry` —
é recusado com uma mensagem nomeando a chave; essas ficam em nível superior na configuração de
usuário com sua própria validação. Os próprios tipos, com o diretório de origem, tipo de valor e
projeção de cada um, são as entradas de `catalog.KINDS` em `lib/harness_core/catalog.py`.

## Posturas

Cada postura é um diretório de variantes sob `primitives/stances/`; a configuração escolhe uma e
`sync` a projeta nos runtimes selecionados. O Claude recebe um link sob
`~/.claude/rules/harness-stances/<stance>.md`; o Codex recebe a mesma fonte resolvida em suas
instruções geradas. Uma variante `off` permanece explícita em vez de remover a dimensão
silenciosamente.

| Postura | Variantes | Padrão |
| --- | --- | --- |
| `licensing` | `permissive-commercial`, `open-source`, `off` | `permissive-commercial` |
| `build-vs-buy` | `capability-ceiling`, `off` | `capability-ceiling` |
| `commits` | `conventional-attributed`, `conventional`, `as-you-go`, `off` | `conventional-attributed` |
| `plan-ceremony` | `review-card`, `light` | `review-card` |
| `delegation` | `tiered`, `session-model`, `off` | `tiered` |
| `testing` | `required`, `pragmatic`, `off` | `required` |
| `autonomy` | `execute`, `confirm-writes`, `ask` | `execute` |
| `cost` | `frugal`, `balanced`, `max` | `balanced` |
| `voice` | `scannable`, `concise`, `answer-card`, `off` | `scannable` |

`citizen config set stances.testing off` verifica se a variante existe antes de escrever, e nomeia
as opções quando não existe.

### Predefinições

Os padrões acima são um fluxo de trabalho de software profissional, e escapar dele exigia
encontrar cinco opt-outs separados. `citizen init` pergunta qual é o trabalho e usa uma
predefinição como os padrões para as perguntas seguintes; toda postura ainda é perguntada, então
uma predefinição é um ponto de partida, não uma trava.

| Predefinição | Mudanças em relação aos padrões |
| --- | --- |
| `software` | nada; a tabela acima |
| `general` | `licensing: off`, `build-vs-buy: off`, `commits: off`, `testing: off`, `plan-ceremony: light` |

`general` é para trabalho que não é lançamento de software — escrita, pesquisa, organização de
arquivos, um script pessoal. Ela deixa `delegation`, `autonomy` e `cost` intactos, porque como o
trabalho se espalha, até onde roda sem supervisão e o que custa são as mesmas perguntas, seja qual
for o trabalho.

As regras de tópico não têm variantes ou predefinições, embora cada uma possa ser desligada na
seleção; uma regra sobre repositórios, testes ou pull requests simplesmente não se aplica quando a
tarefa não é trabalho de código, e o preâmbulo sempre carregado diz isso.

Sobrescritas de ambiente vencem sobre o arquivo: `HARNESS_STANCE_LICENSING=open-source`,
`HARNESS_STANCE_COMMITS=off`. Tal variável é uma seleção de sessão: `citizen stances` e os hooks a
resolvem, mas uma sincronização nunca a linka, e continua linkando sua variante em nível de
usuário com um aviso de que seleções de projeto e sessão ficam na sessão. No início da sessão, o
hook `harness-session.py` compara a seleção resolvida com a sincronizada e injeta o texto da
variante diferente, dentro do orçamento sempre carregado
([sincronização](sync-model.md#project-and-session-stance-selections)), então
`HARNESS_STANCE_TESTING=off claude` funciona para uma sessão sem uma nova sincronização. Pela
mesma razão, `citizen diff` compara os links contra sua seleção em nível de usuário, então uma
seleção de sessão não é desvio, e `citizen diff` pode relatar nenhum enquanto `citizen stances`
mostra a variante da sessão.

A postura `plan-ceremony` também decide se o validador de plan-card roda. O registro é
incondicional — um coordenador por evento de ciclo de vida, como em
[how it works](how-it-works.md) — então a postura é lida dentro do despacho, no momento em que um
arquivo de plano é escrito, e um switch tem efeito no próximo turno em vez de na próxima
sincronização.

## O que uma sessão custa

Todo turno gasta tokens contra o limite do seu plano, e os que espalham trabalho para vários
subagentes gastam várias vezes mais: `/research` e `/build` são os comandos caros, e uma review
ampla é o hábito caro.

A postura `cost` é o controle. Ela define quanto; a postura `delegation` define o que é delegado e
para qual camada de modelo.

Uma variante controla mais que os próprios hábitos da sessão. Seus switches definem o esforço de
raciocínio da sessão, a largura de fan-out, se o modo rápido e a compactação estão disponíveis, e
quanto o feed de uso diz sobre gasto; suas linhas definem uma classe de modelo, um esforço de
raciocínio e um orçamento flexível em tokens de saída e chamadas de ferramenta para cada papel e
para cada uma das bandas A, B e C, e nomeiam a banda para a qual um spawn sem nome é roteado. Tudo
isso são dados em um sidecar JSON ao lado do `.md` da variante, e `citizen stances --json` imprime
a tabela resolvida com o sidecar de onde cada camada veio.

- `frugal` roda a sessão em baixo esforço, mantém o fan-out estreito, nunca liga o modo rápido,
  termina uma tarefa com `/clear`, rebaixa as bandas mais baratas uma classe cada, e escala todo
  orçamento para baixo.
- `balanced` é o padrão distribuído: esforço médio, um fan-out moderado, modo rápido desligado a
  menos que você o peça, `/clear` no final da tarefa, e os orçamentos medidos sem escala.
- `max` deixa o esforço no padrão do modelo, faz fan-out tão amplo quanto a tarefa precisar,
  permite modo rápido e compactação, e não marca nada como acima do orçamento.

Selecione uma com `citizen config set stances.cost frugal`, ou para uma única sessão com
`HARNESS_STANCE_COST=frugal claude`. Para escrever a sua própria, coloque um `.md` e um sidecar na
sua raiz de primitivo, `extends` uma variante distribuída e mude só as células que importam;
[primitive-authoring.md](primitive-authoring.md) tem o exemplo trabalhado e o schema.

A compactação é o único lugar onde uma variante sobrescreve uma regra sempre carregada.
`cache-hygiene.md` diz para começar uma sessão nova em vez de compactar, a menos que a postura
`cost` selecionada permita compactação; o switch `compaction` da variante é o que decide. Sob
`max` (`compact-allowed`), uma compactação é a postura funcionando, então o detector
`cache-hygiene/compact` não a conta ali, e ainda conta uma sob `frugal`, `balanced`, `off` ou
nenhuma seleção, onde a regra vale. Uma sobrescrita de sessão (`HARNESS_STANCE_COST=max`) levanta
a regra só para essa sessão; `citizen sync` nunca a escreve na configuração de usuário ou nas
projeções globais.

Duas coisas contra as quais uma variante nunca vence. Uma entrada `role_bindings.<runtime>.<role>`
na sua configuração sempre vence sobre a linha, porque você nomeou o papel você mesmo. E um papel
cujo contrato diz `posture: fixed` — os verificadores — ignora a classe e o esforço de uma
variante por completo e recebe só seus orçamentos.

O orçamento de uma linha alcança o trabalho como uma frase que `brief-guard` anexa a um brief que
não declara nenhum gasto próprio. É flexível — termine se estiver perto, caso contrário retorne —
e uma variante que não precifica nada não muda nenhum brief. Os orçamentos por papel distribuídos
são o p75 de 90 dias de `citizen usage --by role`; os orçamentos de banda A/B/C são provisórios —
a distribuição de propósito geral em p50, p75 e p90 — até que spawns redirecionados tenham medido
cada banda, e as próprias bandas são um primeiro corte a ser semeado de novo da mesma forma.

`citizen usage` resume o que sessões de fato gastaram, a partir de um arquivo local sem nenhuma
chamada de rede a menos que você opte por [exportá-lo](telemetry.md) — veja [usage.md](usage.md).
Ele relata dólares assim como tokens, a partir de `policy/prices.json`.
Um bloco `prices` em `config.json` mescla sobre esse arquivo por id de modelo, então você pode
corrigir uma taxa que sua conta é cobrada de forma diferente, ou adicionar um modelo que a tabela
não lista:

```json
{ "prices": { "claude-opus-5": { "input": 4.0 }, "some-local-model": {
    "input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0 } } }
```

Uma sobrescrita que nomeia uma taxa mantém o resto da entrada distribuída; um modelo novo precisa
das quatro.

## Outras superfícies

`"claude": { "manage": true }`, `"codex": { "manage": true }` e
`"vscode": { "manage": true }` selecionam independentemente as superfícies de runtime e editor que
a sincronização pode gerenciar. Defina qualquer uma como `false` para deixar essa superfície
intacta; nem o Claude nem o Codex exige o outro.

## Postura de permissão

`permissions` na configuração é `inherit` (padrão: o harness nunca toca no modo de permissão),
`bypass`, `auto` ou `manual`. Quando definido, um único controle move
`permissions.defaultMode` no Claude Code, `claudeCode.initialPermissionMode` e
`claudeCode.allowDangerouslySkipPermissions` no VS Code, e `approval_policy` mais `sandbox_mode`
no Codex. Valores de ambiente de sessão não concedem permissões nativas nem alteram configuração
global.

**`bypass` é recusado a menos que `permissions_bypass_acknowledged` seja `true` no arquivo de
configuração** (a sobrescrita de ambiente não consegue concedê-lo). Ele desliga todo prompt de
permissão e coloca o Codex em `danger-full-access` sem nenhum sandbox. É uma postura para uma
máquina pessoal isolada. Nunca a selecione em uma máquina que toca dados regulados ou de cliente,
e nunca a carregue para o fork de uma organização deste harness: deixe `inherit` e deixe as
configurações gerenciadas da organização decidirem. `auto` é a escolha certa para uma configuração
supervisionada mas de baixo atrito.

### O que o modo plano pode fazer nessa postura

O modo plano existe para forçar um plano, suas perguntas e uma espera antes de qualquer coisa ser
construída. Não é motivo para investigar em uma autoridade menor que a que você selecionou para
todo outro modo, e nativamente é isso que acontece: as regras de permissão e o hook somente-leitura
cobrem os comandos que a gramática consegue provar, então rodar um script, um `python3 -c`, um
redirecionamento para um arquivo de rascunho ou uma execução de teste ainda pergunta.

Então sob `bypass` ou `auto`, no Claude Code, enquanto `permission_mode` é `plan`, o coordenador
PreToolUse responde ao que o fluxo nativo perguntaria:

- Classe 0 ou 1 — provado somente-leitura, ou escrevendo só nesta máquina — é aprovado como
  investigação.
- Classe 2 — um push, um lançamento, uma chamada de API que muta, qualquer coisa que um colega
  veria — é perguntado, porque isso é execução em vez de planejamento. Classe 3 não muda.
- `manual` e `inherit` mantêm o comportamento de hoje, e o Codex fica intocado: seu cliente
  rejeita de imediato uma decisão `allow`.
- A postura autonomy ainda vence onde é mais rígida. `confirm-writes` ou `ask` pergunta sobre as
  mesmas classes no modo plano que pergunta em todo lugar mais.

**`plan_allow_tools`** é uma lista de globs de nome de ferramenta (sintaxe `fnmatch`, por exemplo
`"mcp__notes__read_*"`) aprovados no modo plano sob o mesmo portão de postura. É vazia por padrão
e nada é inferido: um payload de PreToolUse não diz nada sobre se uma ferramenta MCP lê ou
escreve, então só você consegue dizer quais delas são pesquisa. Entradas que não são strings não
vazias são ignoradas, e um glob nunca reabre uma ferramenta que o coordenador já governa —
`Bash` mantém suas classes, `Agent` sua guarda de delegação, `WebFetch` seu próprio hook de modo
plano. Defina-o com `citizen config set plan_allow_tools '["mcp__notes__read_*"]'`.

## O raciocínio por trás de cada postura

Arquivos de postura carregam só a preferência e seus tópicos operativos, porque contam contra o
teto sempre carregado. Os argumentos vivem aqui.

**Licensing.** `permissive-commercial` existe para capturar o caso que não parece uma questão de
licenciamento, que é por que o gatilho é "antes de incorporar ou atualizar qualquer material de
terceiros" em vez de "quando uma licença parece incerta". Licenças de software preferidas: MIT,
BSD-2-Clause, BSD-3-Clause, ISC, Apache-2.0, 0BSD; licenças de conteúdo preferidas: CC0-1.0,
CC-BY-4.0 — candidatas, não um substituto para verificar a versão exata e qualquer material
empacotado junto. Excluídas sem exceção: GPL, AGPL, LGPL, MPL, CC BY-SA e ODbL, mais licenças de
ativo proprietário pago sem uso comercial, sem derivados, só editorial, só pesquisa, campo de uso,
crédito publicitário, tempo limitado, revogável a qualquer momento. Ferramentas de desenvolvimento
standalone podem usar licenças copyleft onde meramente usá-las não impõe obrigação nenhuma sobre
sua saída; verifique componentes de runtime empacotados separadamente, e nunca leia essa exceção
como permissão para incorporar código ou ativos copyleft. "Download grátis", "royalty-free",
"source available" e uma etiqueta de marketplace não são prova: a alegação de licença de quem fez
upload sozinha não estabelece propriedade, e nenhum rip de jogo, cópia não licenciada ou material
com direitos suspeitos se qualifica. Sob `open-source`, copyleft se qualifica quando a própria
licença do projeto é compatível e as obrigações estão registradas no manifesto.

**Testing.** Sob `required`, "construa a funcionalidade X" sempre significa construí-la, fazer todo
teste existente passar, e escrever testes cobrindo toda capacidade nova: testes são parte da
definição de pronto, não um passo separado. Não há circunstância em que lançar código sem testes
seja aceitável — não por velocidade, não por mudanças "simples", não por "eu adiciono depois",
porque depois nunca vem. `pragmatic` pede em vez disso que um teste compre algo, e que o relatório
diga claramente qual comportamento novo está sem teste e por quê.

**Commits.** `type(scope): summary`, com `feat`, `fix`, `docs`, `chore`, `refactor`, `test` e `ci`
como os tipos usuais. O gate de qualidade roda no `HEAD` do checkout exato que você está prestes a
enviar (push), porque um gate rodado em outro lugar não prova nada sobre o que aterrissa. Trailers
de atribuição são como um leitor sabe que um agente escreveu a mudança, que é por que
`conventional-attributed` os mantém e `conventional` os descarta. `as-you-go` existe para
repositórios onde estado local obsoleto é custo puro — repositórios de planejamento, bases de
conhecimento, dotfiles — e explicitamente não se aplica a repositórios de aplicação com um gate de
review.

**Autonomy.** Define padrões por reversibilidade e raio de impacto: um deploy nunca é autônomo,
uma edição local sempre é. Os antipadrões que `execute` descarta: terminar com "rode isto no seu
terminal:" para uma configuração que você consegue realizar, colar instruções de instalação ou
início em vez de rodá-las, e perguntar "diga a palavra e eu vou…" para trabalho que você consegue
fazer no mesmo turno. Um nível de autonomia concedido para um escopo não se estende para o
seguinte, então nunca amplie suas próprias permissões nem registre uma regra de governança para si
mesmo a menos que o usuário peça. O hook `grade-bash` aplica a postura: ele classifica todo comando
de shell de 0 a 3 e barra na classe 3 sob `execute`, 2 e acima sob `confirm-writes`, 1 e acima sob
`ask`; [`grade-bash.py`](../claude/hooks/grade-bash.py) documenta as classes e os modos.

**Plan ceremony.** `review-card` torna o modo plano a superfície de review: `/plan` pede para
entrar nele, escreve o cartão no arquivo que o modo plano designa, posta a abordagem no chat e
termina em `ExitPlanMode`, então o painel renderiza o plano e a aprovação nativa é o portão. A
aprovação também é quando a nomeação acontece: `/plan` renomeia o arquivo gerado pelo runtime para
um slug de tópico e entrega esse caminho a `/build` — que é por que `/build` nunca procura um
plano, e por que o builder é quem faz commit do arquivo, na worktree de onde vem o pull request.
Onde não há modo plano — Codex, e qualquer plano escrito fora de `/plan` — o arquivo é nomeado
pelo tópico, aberto para o revisor e fechado com a linha de build digitada em vez disso. De
qualquer forma, a implementação autônoma segue a aprovação. O cartão é um documento de review antes
de ser um documento de execução — comprimento abaixo dele é grátis, comprimento acima dele é o
defeito — e um hook o valida em toda escrita, seja qual for o nome que o runtime deu ao arquivo.
Pule a cerimônia só se o usuário pedir explicitamente um plano rápido ou disser para simplesmente
sair do modo plano. `light` descarta o arquivo e o validador mas mantém o aval explícito.

**Build versus buy.** O usuário já ouviu o argumento de fardo de manutenção e rejeita sua premissa:
código é barato agora, e uma pessoa assistida por agente consegue manter código customizado bem
daqui a três anos. Tetos de capacidade são a classe de argumento que decide.

**Cost.** `cost` governa quanto você gasta, nunca qual modelo: uma linha nomeia uma classe de
capacidade, a tabela do adaptador a resolve, e definições de agente carregam o resultado. Sob
`frugal`, subagentes são só coletores e equipes de agente estão desligadas, então um gatilho de
subir de classe é respondido elevando o esforço da própria sessão em vez de fazer spawn. O que
cada variante define está acima, sob [o que uma sessão custa](#what-a-session-costs); como isso
atende à decisão de camada está na skill `delegation-tiering`.

**Voice.** `voice` governa como uma resposta é organizada, e nada sobre o que é o trabalho.
`scannable` recorre ao estilo de saída Scannable: veredito primeiro, registros separados, no
máximo uma tabela. É a única variante que distribui material de apresentação próprio, em qualquer
um dos dois runtimes. `concise` escolhe a forma de cada resposta pelo seu propósito, entre seis
formas, e mantém toda resposta às mesmas poucas regras; no Claude Code também seleciona pelo nome
o estilo de saída embutido Concise, e no Codex só o texto de postura o carrega. Sob `answer-card` e
`off`, uma sincronização não instala nenhum estilo de saída e retira o que uma seleção anterior
deixou, enquanto um estilo de saída que você mesmo escolheu é deixado exatamente como está, seja
qual for seu nome.
`answer-card` é para leitura no celular — a resposta na primeira linha, depois o porquê, a
pegadinha, e as alternativas, cerca de 150 palavras, sem tabelas, com o raciocínio deixado no
arquivo que ela linka em vez de reargumentado na mensagem. Ele vence sobre o estilo de saída onde
os dois diferem. `off` não impõe nenhuma forma. Um perfil pessoal de voz é diferente: ele diz ao
agente como redigir em nome do usuário e fica no arquivo pessoal não rastreado. A regra mantém só
o que nenhuma variante muda: um subagente não herda nenhuma voz, então seu brief precisa carregar a
forma de saída ele mesmo.

**Delegation.** A evidência das bandas de camada, os números de custo por tarefa resolvida e os
limites onde param de valer estão na skill `delegation-tiering`, não aqui. O hook
`tier-agent-spawns` aplica a variante escolhida em spawns que não nomeiam nenhuma definição de
agente: roteado para o worker de banda padrão da variante de custo sob `tiered`, intocado sob
`session-model`, um prompt sob `off`.

**Band workers.** `worker-a`, `worker-b` e `worker-c` são os três papéis para os quais as bandas
A/B/C renderizam, e existem por uma razão: a ferramenta `Agent` não recebe nenhum esforço, então
só uma definição de agente consegue carregar o esforço da postura para um spawn que não nomeou
nada. Tal spawn é reescrito para o worker `default_band` da variante — `B` sob `balanced`, `A`
sob `frugal` — e um orquestrador que quer outra banda faz spawn desse worker pelo nome; suas
descrições carregam a regra de banda que a skill `delegation-tiering` argumenta. Uma variante sem
`default_band` não roteia nada; o mesmo vale para uma máquina que não sincronizou as definições, e
para uma sessão iniciada antes disso, que é por que uma sincronização que as instala quer uma
sessão nova depois.

## Propondo uma nova postura ou variante

Uma postura é certa quando um engenheiro competente poderia razoavelmente querer o oposto.
Adicione as variantes sob `primitives/stances/<name>/`, adicione o nome a `STANCE_NAMES` em
`bin/harness`, adicione o padrão a `config.example.json`, adicione uma linha aqui, e adicione uma
linha ao CHANGELOG.

## O que deliberadamente não é uma postura

As regras sempre carregadas em `primitives/rules/` não têm variantes. Você pode desligar uma na
seleção, mas nenhuma muda com uma postura: uma regra precisa valer seja qual for a forma como toda
postura é jogada, o que é o que permite ao harness se instalar para alguém cujas preferências
ninguém conhece. Aplique o mesmo teste ao contrário antes de adicionar uma: se um engenheiro
competente poderia razoavelmente querer o oposto, ela pertence a `primitives/stances/`, não a
`primitives/rules/`.

Duas regras ainda não passam nesse teste, rastreadas em vez de escondidas: `conciseness.md` é
estilo de comentário e documentação, e `cache-hygiene.md` é conteúdo da dimensão de custo para o
qual a postura `cost` já aponta. `voice-and-format.md` não fixa mais o template de resposta
Scannable (#811); mantém só a forma de retorno do brief de subagente, que nenhuma variante
consegue carregar.

## Estenda suas escolhas

Posturas são primitivos personalizados do harness, não funcionalidades nativas de provedor.
Adicione dimensões, variantes e restrições através do [contrato de autoria](primitive-authoring.md).
Inspecione seleções efetivas e cobertura de adaptador com `citizen stances --json`; restrições
nativas continuam sendo autoritativas.
