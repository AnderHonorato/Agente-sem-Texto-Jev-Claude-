# BMad no agent-harness e em repositórios downstream

O harness é agnóstico de framework. Esta página registra um padrão que mantém um framework de
planejamento autogerenciado (o [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD), MIT)
instalado em um repositório de código sem poluí-lo, e sem o harness redistribuir nenhum dos
arquivos do framework. O próprio Model Citizen segue o mesmo limite de runtime mas
deliberadamente publica seu corpus BMad autoral neste repositório.

## O sistema de planejamento público deste repositório

O Model Citizen fixa o BMad Method 6.12.0 com o módulo `bmm`, projeções para Claude Code e Codex,
e ajustes de compatibilidade. Reproduza o aparato local a partir do checkout compartilhado:

```sh
BMAD_VERSION=6.12.0
npx --yes bmad-method@"$BMAD_VERSION" install --directory . --modules bmm \
  --tools claude-code,codex --user-name Jake --communication-language English \
  --document-output-language English --output-folder _bmad-output --shims --yes
```

Depois rode `python3 bin/harness integration check bmad .`. Workflows de planejamento rodam a
partir do checkout compartilhado; a implementação ainda acontece em worktrees gerenciadas.

O limite de controle de versão é intencional:

### Commitar

- `_bmad/custom/**`: configuração de repositório, customizações de workflow, templates e
  extensões de política.
- `_bmad-output/planning-artifacts/**`: brief de produto, PRD, jornada de desenvolvedor,
  arquitetura, épicos, decisões, ledger de origem e relatórios de prontidão.
- `_bmad-output/implementation-artifacts/**`: histórias, estado de sprint público, retrospectivas
  e reconstruções históricas claramente marcadas.
- As instruções de instalação fixadas, código de validação/sincronização possuído pelo
  repositório e fixtures de teste deliberadas.

### Não commitar

- O runtime `_bmad` instalado fora de `_bmad/custom`.
- Projeções geradas de `.agents/skills`, `.claude/skills` ou `.github/agents`.
- Caches de instalador, renderizações temporárias, backups locais, logs ou estado de sessão.
- Conversas brutas, exportações de memória ou despejos de ingestão de fonte.
- Segredos, caminhos absolutos privados, configuração específica de máquina ou dados pessoais não
  higienizados.

Todo artefato publicado precisa ser escrito ou intencionalmente reconstruído, higienizado, e útil
para um contribuidor público. `_bmad/custom/config.user.toml` e todo `*.user.toml` permanecem
locais. Uma reinstalação limpa e a resolução de customização precisam deixar os arquivos
rastreados inalterados.

## Rastreabilidade no GitHub

O GitHub possui o estado de entrega, a discussão, o resumo e a evidência de aceitação. O BMad
fornece IDs tipados imutáveis e os arquivos de história que carregam o design.
`_bmad-output/issue-map.json` registra cada mapeamento, pai primário e próximo ID;
`_bmad-output/implementation-artifacts/AH-*.md` é o arquivo de história e linka de volta para a
issue. Um bloco Planning gerado na issue linka para o artefato na `main`.

```sh
python3 scripts/bmad_issue_sync.py audit
python3 scripts/bmad_issue_sync.py plan
python3 scripts/bmad_issue_sync.py apply
```

`audit` é local e não mutante. `plan` compara o manifesto com o estado ao vivo do GitHub. `apply`
recusa rodar até que todo artefato exista na `main`, depois mantém idempotentemente o bloco
Planning, o rótulo `type::*` exato e o pai primário. Ele nunca muda um título, estado ou
comentário. Tipos de issue nativos do GitHub são
[gerenciados pela organização](https://docs.github.com/issues/tracking-your-work-with-issues/using-issues/managing-issue-types-in-an-organization)
e não podem ser atribuídos neste repositório de conta pessoal, então o manifesto registra a
projeção `labels-only` explicitamente em vez de relatar um desvio falso permanente.
Registre trabalho de mantenedor já mapeado, a partir da worktree que vai entregá-lo, e reserve um
ID para uma issue da comunidade durante a triagem antes da posse da implementação:

```sh
python3 scripts/bmad_issue_sync.py new --title TITLE --kind story --body-file BODY.md --parent PARENT_NUMBER
python3 scripts/bmad_issue_sync.py reserve --issue N --kind story --parent PARENT_NUMBER
```

Os dois escrevem o mapa e um novo artefato no checkout atual; faça commit deles no pull request
que entrega a issue. O check obrigatório `issue-ownership` recusa um pull request cuja issue de
entrega está ausente do mapa, e `apply` adiciona o bloco Planning assim que o artefato está na
`main`.

### Arquivos de história

`new`, `reserve` e `bootstrap` escrevem cada arquivo de história a partir do template do seu tipo
em `scripts/bmad_story_templates/`: story, bug, spike, decision, epic, e um compartilhado por task
e chore. O arquivo abre com os nove campos de ligação e `updated` como frontmatter, depois o H1,
depois um bloco gerenciado entre `<!-- bmad-sync:begin -->` e `<!-- bmad-sync:end -->` guardando o
link da issue, o pai, o estado e a linha que divide a autoridade: a issue carrega o resumo,
discussão e evidência de aceitação, e o arquivo carrega o design. Essas três partes pertencem à
ferramenta. Tudo depois do marcador final pertence às pessoas e agentes que escrevem a história, e
a ferramenta nunca a reescreve. O bloco só conta onde abre, na primeira linha não vazia depois do
H1, e fecha no primeiro marcador final depois disso. Os marcadores citados em qualquer outro
lugar, em prosa ou em um bloco de código, são texto comum. Linhas em branco e comentários HTML de
linha inteira entre o frontmatter e o H1 são mantidos como estão; qualquer outra coisa ali torna o
arquivo malformado. Uma marca de ordem de byte no início e finais de linha CRLF são mantidos em
toda reescrita.

Cada seção do template guarda um placeholder, `<!-- fill: what goes here -->`. Uma seção conta
como preenchida quando resta texto depois que comentários HTML, um não fechado incluído, e
subcabeçalhos de `###` a `######` são retirados; qualquer cabeçalho de nível 1 ou 2, ATX ou
setext, fora de um comentário ou bloco, encerra uma seção, e um cabeçalho obrigatório que aparece
duas vezes é um achado. Estas seções precisam estar preenchidas:

- **story:** Story, Acceptance criteria, Design, Tasks, Dev notes
- **bug:** Reproduction, Root cause, Acceptance criteria, Design, Dev notes
- **spike:** Question, Experiment, Exit criterion, Result
- **decision:** Context, Options, Decision, Consequences
- **epic:** Goal, Scope and requirement coverage, Exit criteria
- **task e chore:** Goal, Acceptance criteria, Tasks

```sh
python3 scripts/bmad_issue_sync.py audit --delivery N
python3 scripts/bmad_issue_sync.py upgrade --check
python3 scripts/bmad_issue_sync.py upgrade --id AH-S123
```

`audit --delivery N` verifica só a história da issue N, e falha enquanto qualquer seção que seu
tipo exige estiver ausente ou não preenchida. O check obrigatório `issue-ownership` o roda para a
própria issue de entrega do pull request tanto em execuções de pull request quanto de fila de
merge, então uma história não enriquecida em outro lugar do corpus nunca bloqueia um pull request
não relacionado.

Um stub legado é um arquivo de antes dos templates tipados que abre com exatamente o stub que a
ferramenta renderizou para seu item, ignorando `updated` e finais de linha; qualquer coisa depois
desse stub é texto de emenda carregado. Qualquer outro arquivo sem um bloco gerenciado bem
formado é malformado: `audit` o relata, `refresh` o recusa, e `audit --delivery` o falha, então
apagar um marcador nunca pula a verificação de profundidade. A verificação de profundidade aprova
um stub legado com um aviso, e `refresh` continua renderizando-o da forma antiga. `upgrade`
converte stubs para o esqueleto do seu tipo, carregando cada byte depois do stub antigo, como
seções `## Amendment`, ao final do arquivo sem alteração, nos próprios finais de linha do arquivo.
Ele recusa um stub que difere do que a ferramenta renderizou, converte todos os arquivos
selecionados ou nenhum, restaurando qualquer um que já tenha escrito quando uma escrita falha,
deixa um arquivo já no formato tipado intacto, e com `--check` relata sem escrever. É aplicado
lote por lote, junto com o enriquecimento, para que um esqueleto cheio de placeholders nunca
aterrisse na `main` sozinho.

Como `next_ids` vive no mapa, ele só sabe o que este checkout já viu. Antes de alocar, os dois
comandos pesquisam todo mapa de issue que este clone consegue alcançar — a cópia de trabalho de
cada worktree linkada, então uma reserva não commitada conta, e toda branch local e de
rastreamento remoto — e recusam quando o contador não passou de todo ID desse tipo já em uso,
nomeando cada um e onde foi encontrado. Fazer rebase sobre a branch que os tomou é a resposta
usual; `--advance` os pula em vez disso e diz quais IDs deixa permanentemente não usados. Heads que
`git ls-remote` anuncia e para os quais este clone não guarda nenhum objeto são relatados, então
uma pesquisa incompleta nunca é lida como uma limpa.

### Status de sprint

Os workflows de sprint e build do BMad leem
`_bmad-output/implementation-artifacts/sprint-status.yaml`. Aqui ele é renderizado a partir do
mapa e dos arquivos de história, nunca editado, então não pode se desviar do GitHub:

```sh
python3 scripts/bmad_issue_sync.py sprint-status
python3 scripts/bmad_issue_sync.py sprint-status --check
```

Cada épico é listado pelo ID BMad, seguido pelos itens cujo ancestral de épico mais próximo é ele,
em ordem de ID BMad; itens sem nenhum épico fecham o arquivo. Uma chave é o ID em minúsculas e um
slug do título. O status segue o ciclo de vida que o mapa registra, não o GitHub diretamente;
`refresh` é o que copia o estado aberto ou fechado do GitHub para o mapa. Um item que o mapa
registra como completo é `done`; um item ativo cuja história é tipada e passa na verificação de
profundidade é `ready-for-dev`; qualquer outro item ativo é `backlog`. Épicos seguem a mesma regra
para `done`; um épico aberto é `in-progress` quando qualquer filho, épicos filhos incluídos, está
done, ready ou in progress, e caso contrário `backlog`. `generated` é a data `YYYY-MM-DD` mais
nova que o mapa ou uma história registra, não o relógio, então um corpus inalterado renderiza byte
a byte o mesmo. A comparação ignora finais de linha CRLF.

`new`, `reserve`, `refresh`, `bootstrap` e `upgrade` regeneram o arquivo sempre que escrevem, e
`audit` falha enquanto ele difere de uma renderização nova. Preencher uma história pode movê-la
para `ready-for-dev`, então rode `sprint-status` na mesma mudança. Duas branches que ambas o
regeneram entram em conflito no merge; resolva rodando o comando de novo em vez de editar qualquer
um dos lados.

### Verificação ao vivo

```sh
python3 scripts/bmad_issue_sync.py audit --live
python3 scripts/bmad_issue_sync.py refresh
```

`audit --live` é somente leitura. Ele falha quando o título ou estado aberto/fechado de uma issue
mapeada difere do manifesto, quando uma issue mapeada está ausente ou carece de seu bloco
Planning, rótulo ou pai, e quando uma issue que um mantenedor aceitou — registrada por um
mantenedor, ou carregando um marco ou um rótulo `type::*` — não tem nenhum ID BMad. Uma issue da
comunidade ainda esperando triagem é um aviso, não um achado, e o mesmo vale para uma issue não
mapeada fechada como não planejada ou como duplicata.

O manifesto possui o pai primário e `apply` o projeta, então `audit --live` nunca diz para você
aplicar um pai que o GitHub já registra: ele relata um pai mapeado que o manifesto não tem como
"rode refresh", um não mapeado como "rode reserve para ele primeiro", e um pai que difere nos dois
lados como um conflito para você resolver.

`refresh` copia o título e o estado do GitHub para o manifesto e seus arquivos de história, e
adota um pai mapeado que o manifesto registra como nenhum. Em um arquivo de história tipado, ele
reescreve só o frontmatter, o H1 e o bloco gerenciado, e mantém o resto byte a byte. Ele verifica
todo artefato desviado antes de escrever qualquer um deles, e recusa a execução inteira quando os
marcadores de um arquivo tipado estão ausentes ou duplicados, ou quando um stub legado carrega
emendas; rode `upgrade` em tal stub primeiro. Ele nunca toca no GitHub, e deixa uma issue que o
GitHub não retorna mais para a auditoria relatar como ausente.

Rode a auditoria ao vivo completa antes de um lançamento e depois de qualquer passagem de
triagem. O workflow `bmad traceability` a roda diariamente, em eventos de issue e quando o mapa
muda, com `--ignore-lifecycle` e `--grace-days 2`: uma issue fecha antes que sua entrada de mapa
consiga acompanhá-la através de um pull request, e uma issue nova ganha dois dias para receber seu
ID. Esse workflow não é um check obrigatório.

IDs nunca são reaproveitados e nunca codificam hierarquia. Reparenteie os metadados em vez de
renomear o ID. Issues históricas completas são marcadas `reconstructed`; o registro nunca alega
que esses artefatos existiam durante a entrega original.

## O padrão

- **Instale no repositório, faça commit só das suas sobrescritas.** `.gitignore` carrega
  `/_bmad/*`, `!/_bmad/custom/`, `/.claude/skills/`, `/.agents/skills/`. O runtime e as projeções
  de skill são regeneráveis pelo instalador; só `_bmad/custom/` é seu.
- **Escolha a autoridade de artefato explicitamente.** Em `_bmad/custom/config.toml`, aponte
  `planning_artifacts`, `implementation_artifacts`, `project_knowledge` e `output_folder` para o
  repositório pretendido usando caminhos relativos a `{project-root}`. Um repositório de
  planejamento separado pode manter um corpus privado muito grande fora de toda worktree; projetos
  públicos como agent-harness podem em vez disso commitar um corpus local higienizado.
- **Fixe a instalação.** Um único comando, com versões, no `AGENTS.md` do repositório, por
  exemplo `npx bmad-method@<version> install --directory <repo> --modules <list> --tools claude-code,codex --yes`.
- **Registre reparos pós-instalação em um único lugar.** Qualquer coisa que você corrija no
  runtime instalado precisa ser reaplicada depois de toda reinstalação; liste cada patch no final
  de `_bmad/custom/config.toml` com a data e o motivo, e o registre a montante para que possa
  desaparecer.
- **Rode-o só a partir do checkout compartilhado.** O framework resolve seus scripts contra o
  diretório de trabalho; uma worktree não tem `_bmad/scripts/`, para, e essa parada é a guarda
  pretendida. Faça o trabalho de implementação em worktrees; rode as skills de planejamento a
  partir do checkout.
- **Mantenha instalações irmãs na mesma versão.** Dois repositórios em um workspace ambos
  projetam skills em `.claude/skills/`; uma colisão de nome resolve silenciosamente, o primeiro
  vence. Enquanto as cópias forem idênticas byte a byte, é inofensivo; no momento em que se
  desviam, a skill de uma versão chama os scripts da outra.
- **Higiene pós-sprint.** Atualize o status do documento de arquitetura, o ledger de decisões e o
  changelog antes de seguir adiante; o framework não fará isso por você.
- **Mantenha a saída de entrega nativa.** Não adicione rodapés de atribuição gerados nem
  caminhos de runtime internos a issues e PRs comuns. Documentação pública e artefatos de
  planejamento podem identificar o BMad deliberadamente, e issues podem linkar para seus artefatos
  de história públicos.

## O confinamento de spawn é aplicado, não solicitado

Os templates de sobrescrita pedem a cada camada de review que rode a si mesma através de
`citizen role run`. Isso é uma solicitação num prompt: um cliente que parafraseia o brief e não
nomeia nenhum papel costumava passar por uma guarda de spawn que só lia o nome que o modelo
escreveu (#291).

Então o framework se declara, em `policy/integrations/bmad.json`, e o hook de spawn classifica
contra esse descritor em vez disso. Um descritor nomeia o framework, o lançamento do qual foi
lido, o mapeamento de camada para papel, as raízes de entrada que um worker confinado precisa, e
como um spawn é reconhecido:

- **agents** — o `subagent_type` do spawn é um dos próprios nomes de camada do framework. Nada
  mais coloca esse nome ali, então é suficiente por si só.
- **identifiers** — um literal que só o texto roteado do próprio framework carrega, como o
  caminho de um dos seus arquivos de prompt. Nunca suficiente sozinho, porque um brief que edita
  os templates de sobrescrita cita o mesmo caminho; um identificador só conta com uma frase ao
  lado, ou quando uma sentença diz ao subagente para seguir ou aplicá-lo. Um cliente que escreve o
  brief ele mesmo mantém o arquivo de prompt, porque o subagente precisa lê-lo, e descarta as
  frases do framework, então a diretiva é o que separa o trabalho da camada de um brief que edita
  o arquivo ou o lê por outro motivo (#739).
- **phrases** — frases inteiras do próprio texto de prompt do framework. Uma é coincidência; a
  `corroboration` delas, duas por padrão, não é.

Substantivos genéricos não são frases. "unified diff" e "list of findings" são o que o brief comum
de correção depois de uma review diz, e um descritor que os declarasse recusaria o próprio
trabalho que a review pediu. O carregador aplica isso: um sinal abaixo do comprimento e contagem
de palavra mínimos, um identificador que é uma raiz de entrada ou um diretório simples sob uma, um
spawn sem nenhuma frase, ou um papel que a guarda de spawn não restringiria, e o descritor é
recusado por inteiro. Um descritor que não analisa ou não valida é anunciado uma vez por sessão e
registrado no log de decisões, nunca descartado em silêncio.

Um spawn reconhecido é recusado com a mesma instrução de worker isolado que o spawn de um papel
nomeado recebe, e a recusa nomeia o framework, a camada e as raízes de entrada que o worker precisa
receber como raízes de leitura. Ao contrário de uma recusa que o spawn declarou por nome de papel
ou linha `harness-role:`, ela não é escrita na memória de trabalho recusado da sessão: essa
memória combina briefs posteriores por prefixo e semelhança, então uma classificação errada
continuaria recusando o brief corrigido pelo resto da sessão. Cada spawn é respondido com base na
sua própria evidência.

A linha `harness-role:` que os templates carregam é uma otimização em cima disso: ela é lida pela
guarda de marcador, que a exige em uma linha própria, e um descritor não pode reafirmá-la como
texto solto.

Outro framework se torna um inquilino adicionando seu próprio arquivo de descritor; nada no hook é
específico do BMad. Mantenha `version.pinned` igual ao lançamento que o repositório instala — um
mapeamento lido de outro lançamento nomeia camadas que não estão lá.

## Papéis compartilhados e instalação explícita

`templates/bmad/custom/` nomeia papéis do harness: `builder`, `reviewer`, e `spec-reviewer`. O
adaptador de runtime ativo fornece seu modelo e esforço; o próprio texto de skill do framework não
fornece, e o hook de spawn classifica um repositório de framework como qualquer outro.

Um spawn de framework que nomeia um desses papéis é precificado a partir da linha desse papel na
variante de custo ativa. Um spawn de framework que não nomeia nenhum papel de forma alguma — o
"lance um subagente" que um arquivo de passo escreve, que nenhum template de sobrescrita alcança —
é roteado para o worker de banda padrão da variante e precificado a partir da linha dessa banda em
vez disso, então sua classe, esforço e orçamento flexível vêm da postura em vez da receita. Nada
nos próprios templates do framework muda. Papéis de review restritos usam `citizen role run` com
raízes de entrada explícitas; builders mantêm seu workflow normal. Veja
[workers de papel isolados](role-workers.md). Cada camada de review é pedida para lançar somente
depois que o worker da camada anterior saiu, porque um worker ainda em execução não relata nenhuma
contagem de token e uma rodada cujo gasto é invisível não pode ser mantida sob seu teto. Rodar
quatro camadas uma depois da outra é acessível porque cada uma agora tem cerca de 30.800 tokens
estimados montados em vez do checkout inteiro; esse número é o que é montado, não o que uma camada
lê. Receitas mantêm registros completos de camada de review indexados para que o merge de
substituição do BMad não descarte campos obrigatórios. A worktree de implementação atribuída, o
checkout do framework, a raiz de artefato, o commit de base e o diff de review precisam ser
entradas explícitas separadas; rode scripts de framework a partir do checkout do framework.

Rode `citizen integration check bmad <framework-root>` antes de
`citizen integration apply bmad <framework-root>`; `citizen bmad check|apply` é mantido como um
alias para os dois. O comando lê `policy/integrations/bmad.json` para o diretório de template, o
destino de instalação e a superfície de skill, então o CLI não nomeia nenhum framework próprio.
`check` resolve `.agents/skills` ou `.claude/skills`, recusa espelhos conflitantes, e analisa TOML
de customização estruturalmente. Também compara fontes espelhadas de Markdown/TOML e verifica
dependências literais de `Invoke via the … skill` em workflows instalados; outras formas de
roteamento dinâmico de skill ainda exigem aceitação de workflow. `apply` escreve só chaves
declaradas e ids de camada existentes; preserva sobrescritas de usuário divergentes a menos que
você passe explicitamente `--force`. O início de sessão só verifica. Nunca instala configuração
silenciosamente.

O BMad usa dois mecanismos de entrada: skills de build renderizam `workflow.md`, enquanto a
review de código resolve o bloco de customização `workflow` com `resolve_customization.py`. Um
`workflow.md` ausente em uma skill baseada em resolvedor não é um defeito de instalação. Teste o
mecanismo de entrada que o `SKILL.md` dela nomeia.

O renderizador BMad 6.12.0 inspecionado suporta `--project-root` e `--skill`. Não invente uma flag
`--overrides` ou `--set` de documentação mais nova. Use sua costura `_bmad/custom/`. Patches de
renderizador e shims GDS de review ausentes são achados de integração, não motivos para
reinstalar um framework dentro de uma worktree de implementação. Skills de review ausentes
precisam ser restauradas através da instalação de shim suportada do framework ou uma correção
upstream antes que esse workflow seja qualificado.

O BMad 6.12.0 fornece `--shims` em seu instalador. O GDS v0.7.2 ainda invoca os nomes legados
`bmad-review-adversarial-general` e `bmad-review-edge-case-hunter`; instalações sem seus shims de
compatibilidade falham `citizen integration check bmad`. Rode de novo seu comando de instalação
registrado e fixado por versão com `--shims`, mantendo os mesmos módulos, ferramentas e fixações
de módulo. Faça backup da instalação primeiro, restaure quaisquer patches de runtime documentados
e YAMLs de roteamento de artefato, depois verifique as duas projeções de skill e confirme que
customizações existentes não mudaram. Mantenha `--shims` no comando de reinstalação registrado
enquanto esses workflows exigirem os nomes legados. Isso repara a descoberta de dependência; uma
verificação aprovada ainda não qualifica a execução de workflow.

## Continue uma tarefa em qualquer um dos dois runtimes

A continuação de tarefa compartilhada é uma capacidade do harness e não nomeia nenhum framework de
planejamento, então tem sua própria página:
[continue uma tarefa em qualquer um dos dois runtimes](task-continuation.md). Um handoff carrega
o checkout do framework e o commit de base quando um framework possui os artefatos.

## A suíte de integração opcional

O próprio workflow deste framework não é rodado em uma rodada de qualificação de lançamento.
`required_cases` carrega o caso genérico `framework-spawn-routing` em vez disso, que conduz o hook
de spawn contra uma receita fixa e custa um turno barato; o que ele prova e o que não prova está
em [compatibility](compatibility.md).

O que permanece na CI é barato e offline: `tests/test_bmad_templates.py` e
`tests/test_bmad_repository.py` fixam a superfície upstream contra um repositório fixo sem
nenhum framework instalado, e são o que de fato captura uma chave ou id de camada renomeados.

A execução nativa é uma suíte opcional, não bloqueante, rodada uma vez por lançamento minor em um
alvo antes da tag:

```sh
BMAD_VERSION=6.12.0
npx --yes bmad-method@"$BMAD_VERSION" install --directory <framework-root> --modules bmm \
  --tools claude-code,codex --output-folder _bmad-output --shims --yes
python3 bin/harness integration apply bmad <framework-root>
# depois rode a review de código de quatro camadas a partir do checkout compartilhado contra uma
# worktree atribuída, e confirme que cada camada rodou como um worker isolado em vez de um
# subagente nativo.
```

Registre o resultado no pull request do lançamento com a versão do harness, a versão do framework
e o cliente em que rodou. Não bloqueia nada: um resultado vermelho é uma issue, não um lançamento
bloqueado, e a alegação de lançamento diz só que a versão fixada é a que foi observada.
