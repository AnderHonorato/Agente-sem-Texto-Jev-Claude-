# Seus primitivos, sua forma de trabalhar

Posturas pessoais são switches definidos pelo harness para como seus agentes trabalham. Não são
uma funcionalidade nativa do Claude Code ou do Codex. Uma variante selecionada fornece política
para os dois adaptadores de runtime; restrições nativas ainda se aplicam. Orientação não é prova
de que um runtime aplica uma preferência.

## Selecione e inspecione uma postura

```sh
bin/harness config set stances.voice answer-card
bin/harness stances
bin/harness sync --dry-run
```

Depois de revisar as mudanças, `bin/harness sync` instala a seleção. O Claude Code lê a postura
selecionada através de suas regras linkadas; o Codex lê o mesmo texto em instruções geradas. Use
`HARNESS_STANCE_VOICE=scannable bin/harness stances --json` para inspecionar uma seleção de
sessão. Definir uma variável de ambiente em um agente em execução não reescreve por si só seu
contexto carregado.

Uma seleção de projeto ou sessão que difere da sincronizada alcança o modelo no próximo início de
sessão: o hook de sessão injeta o texto da variante selecionada, dentro do orçamento sempre
carregado, e nomeia seu arquivo em vez disso quando o texto não cabe. Mantenha curta uma variante
que você espera selecionar por projeto ou por sessão, para que chegue como texto em vez de como um
ponteiro. [Sincronização](sync-model.md#project-and-session-stance-selections) traz o orçamento.

A ordem de resolução, e o que um arquivo de projeto ou sessão pode carregar, é o documento de
seleção em [preferências](preferences.md#the-selection-document).

## Defina uma postura pessoal

Crie um diretório fora do checkout, como `~/.config/agent-harness/primitives`, e adicione seu
caminho absoluto expandido ao array `primitive_roots` na sua configuração de usuário. Crie
`stances/feedback/direct.md` ali com este conteúdo:

```markdown
# Feedback stance: direct

Lead with the conclusion. Name the specific evidence and the next useful action.
```

Adicione `stances/feedback/gentle.md` com sua política alternativa, depois a selecione com
`bin/harness config set stances.feedback gentle`. `bin/harness stances --json` mostra sua fonte e
o comportamento resolvido completo. Dimensões personalizadas são opcionais até serem
selecionadas. Identificadores usam letras minúsculas, dígitos e hífens. Definições duplicadas de
dimensão/variante, seleções desconhecidas e travessia de caminho são erros, não comportamento de
fallback.

Um nome de skill, papel ou workflow definido em duas raízes também é um erro. `citizen lint`
nomeia as duas fontes e `citizen sync` recusa antes de escrever qualquer coisa, porque um runtime
resolve um nome duplicado silenciosamente, o primeiro vence. O nome de `.claude/agents/` ou
`.claude/skills/` de um projeto próprio não é uma duplicata: a definição do projeto deve vencer,
então a sincronização relata a sombra como um aviso e continua.

Um `constraints.json` opcional ao lado de `stances/` pode rejeitar escolhas incompatíveis:

```json
{"stances": [{"when": {"feedback": "direct"}, "excludes": {"voice": "off"},
  "reason": "Direct feedback requires an active voice policy"}]}
```

Cada regra tem uma seleção `when` não vazia, um `reason` de uma frase, e pelo menos um de
`requires`, `excludes` e `excludes_roles`. Todas as entradas de `when` precisam combinar para
ativar a regra; todo requisito precisa combinar e nenhuma escolha excluída pode ser selecionada.
Qualquer outro campo é um erro de autoria, não uma chave que uma versão futura poderia ler.

`excludes_roles` é a única condição que lê algo além da seleção: o frontmatter dos contratos de
papel distribuídos, com `allow` nomeando os papéis que uma skill isenta pelo nome. É como o harness
afirma em dados que `delegation: tiered` recusa a classe frontier enquanto `designer` e
`design-judge` têm permissão para declará-la:

```json
{"stances": [{"when": {"delegation": "tiered"},
  "excludes_roles": {"tier": "frontier", "allow": ["designer", "design-judge"]},
  "reason": "Only the design roles the delegation-tiering skill exempts may declare frontier"}]}
```

Uma restrição violada é um achado em `citizen stances --json` (um array `conflicts`) e em
`citizen lint`, que avalia as restrições distribuídas contra `config.example.json`. Continua sendo
um erro rígido no resolvedor, então `citizen sync` recusa a seleção em vez de projetar uma
contradição; a validação roda antes de a sincronização mudar arquivos.

## Uma variante de custo com números nela

Uma variante `cost` é prosa em `<variant>.md` e, opcionalmente, dados em `<variant>.json` ao lado.
O sidecar é o que o harness resolve; a prosa é o que seu agente lê. Na sua raiz de primitivo —
`~/.config/agent-harness/primitives`, digamos — escreva `stances/cost/careful.md` com sua
política, depois `stances/cost/careful.json`:

```json
{"schema_version": 1, "extends": "balanced",
 "switches": {"session_effort": "high", "budget_multiplier": 1.4},
 "rows": {"gatherer": {"effort": "medium"}}}
```

`extends` nomeia outra variante de custo e pode encadear até cinco níveis de profundidade; ciclos
param a resolução com um aviso. Cada camada é mesclada sobre a que estende, switch por switch e
célula por célula da linha, então o exemplo acima muda três valores e herda todos os outros. Um
link que não pode ser seguido — sem sidecar, JSON ilegível, um `schema_version` que o lançamento
instalado não lê, um nome que não é um identificador de primitivo — resolve para a tabela do
`balanced` com um aviso, então uma variante nunca fica silenciosamente vazia.

`default_band` nomeia a banda para a qual um spawn sem nome é roteado, e omiti-la em toda a cadeia
não roteia nada.

Uma linha é indexada por um nome de papel ou por uma banda — `A`, `B` ou `C` — e pode definir
`class`, `effort`, `budget_output_tokens` e `budget_tool_calls`; qualquer uma delas pode ser
omitida, e um orçamento nulo significa sem orçamento. `budget_multiplier` escala os dois
orçamentos, e `citizen stances --json` relata o número base e o escalado. `class` nunca nomeia a
classe mais alta: alcançá-la por solicitação é exatamente o que a postura `delegation` proíbe, e
ela só se aplica quando essa postura resolve para `tiered`. Um papel cujo frontmatter diz
`posture: fixed` — os verificadores — mantém sua própria classe e esforço seja o que for que uma
linha diga, e recebe os orçamentos da linha.

Chaves desconhecidas são ignoradas com um aviso em vez de um erro, então um switch adicionado em
um lançamento posterior nunca quebra uma variante que você escreveu. Rode `bin/harness stances --json`
para ver a tabela resolvida, sua `extends_chain`, o caminho de cada sidecar, e quaisquer avisos.

## Importe instruções que você já tem

`bin/harness import path/to/CLAUDE.md` transforma um arquivo de instrução existente em regras sob
uma raiz de primitivo externa, então adotar o harness não significa descartar o que um
repositório já diz aos seus agentes. Ele lê `CLAUDE.md`, `AGENTS.md`, `.cursorrules` e
`.cursor/rules/*.mdc`; o `import` do rulesync é a referência para o comportamento.

Cada seção `##` de nível superior vira `rules/<slug>.md` carregando o caminho de origem, a data de
importação e o cabeçalho original como frontmatter. A prosa acima da primeira seção vira
`rules/<name>-preamble.md`, um `@`-import em um `CLAUDE.md` é seguido um nível e importado como
sua própria regra com seu próprio `source:`, e o `description`, `globs` e `alwaysApply` de um
arquivo `.mdc` são carregados sem alteração. Um `##` dentro de um bloco cercado é texto, não um
cabeçalho. Nada é descartado: um cabeçalho que não gera nenhum identificador, uma segunda seção
reivindicando um nome já ocupado e uma linha de frontmatter que não é um campo, todos caem em um
único `rules/<name>-unsorted.md` com uma nota dizendo isso.

```sh
bin/harness import ~/code/project/CLAUDE.md --dry-run   # o plano, depois `citizen sync --dry-run` para a projeção
bin/harness import ~/code/project/CLAUDE.md             # escreve exatamente esse plano
```

A primeira execução só imprime — as regras que escreveria, depois `citizen sync --dry-run` para a
raiz que as carregaria — e uma segunda execução aplica o plano que imprimiu; uma fonte que mudou
nesse meio tempo é impressa de novo em vez de escrita. As regras caem sob
`~/.config/agent-harness/imported/<name>/`, a menos que `--root` nomeie outro diretório absoluto,
nunca sob o `primitives/` deste repositório, e a raiz é adicionada a `primitive_roots` somente
depois que os arquivos existem. Uma raiz que não carrega nenhum `stances/` está tudo bem. Importar
um arquivo que o diário de posse diz que o harness gerou é recusado com seu registro, e o mesmo
vale para um nome de skill, papel ou workflow que a nova raiz definiria duas vezes, nas próprias
palavras da sincronização e antes de qualquer escrita.

Uma vez que a raiz é registrada, `citizen sync` a projeta como qualquer outra: as regras
importadas são linkadas em `~/.claude/rules/harness-roots/<root>/` e renderizadas no `AGENTS.md`
do Codex depois das próprias regras deste repositório, e quaisquer skills que a raiz carrega são
linkadas ao lado das compartilhadas. [O modelo de sincronização](sync-model.md) cobre a ordenação,
o relato de desvio e o que a desinstalação retira.

## Declare o manifesto de um módulo

Um switch diz se uma regra, skill, papel, workflow ou hook está ligado. Seu manifesto diz para que
o módulo serve e como seu efeito poderia ser distinguido do resto, então um switch invertido pode
ser atribuído e pontuado. Módulos distribuídos declaram os seus em `primitives/manifests.json`, e
hooks em `policy/hooks/manifests.json`. Uma raiz em `primitive_roots` pode carregar um
`manifests.json` da mesma forma em seu nível superior. Variantes de postura são escolhidas, não
ligadas por switch, e não carregam nenhum.

```json
{"schema_version": 1,
 "rules": {"secrets": {"claims": ["Keeps credentials out of every tracked file."],
                       "surface": ["resident-context"],
                       "instruments": ["detector:secrets/secret-in-write"],
                       "slot": null, "dependencies": [], "conflicts": []}}}
```

| Campo | Guarda |
| --- | --- |
| `claims` | Para que o módulo serve, uma ou mais frases. |
| `surface` | Onde alcança o modelo: `resident-context` (carregado toda sessão, listagem de skill ou papel incluída), `on-demand-context` (carregado quando invocado) e `hook-events` (roda em eventos de runtime). |
| `instruments` | O que o mede, como `detector:<id>` de `policy/hooks/rule-detectors.py`. Vazio significa não medido, e todo relatório diz `unmeasured`, nunca que o módulo não tem efeito. |
| `slot` | `null`, ou `{"id": <identifier>, "cedes": true or false}` para uma posição exclusiva. |
| `dependencies` | Módulos `kind/unit` que precisam estar ligados enquanto este estiver. |
| `conflicts` | Módulos `kind/unit` que não podem estar ligados junto com este. |

O resolvedor, `posture.selection()`, os aplica sempre que roda em modo estrito, então
`harness selection` e todo comando que lê uma seleção recusa, nomeando cada módulo envolvido,
quando:

- um módulo distribuído não tem manifesto, ou um manifesto carece de um campo ou tem um malformado;
- um módulo ligado depende de um que está desligado ou não instalado;
- dois módulos ligados entram em conflito;
- dois módulos ligados reivindicam um mesmo slot e nenhum o cede;
- um módulo é declarado em dois arquivos de manifesto.

Um módulo desligado não pede nada às suas dependências e não ocupa nenhum slot. Um módulo da sua
própria raiz pode omitir seu manifesto: resolve e relata como não medido, e uma raiz escrita antes
de manifestos existirem continua funcionando. Uma dependência é um módulo cuja ausência quebra
este. Um ponteiro para leitura adicional não é uma dependência. `citizen selection` mostra os
instrumentos de cada unidade de switch, ou `unmeasured`, ao lado do seu valor.

## Contribua com primitivos compartilhados

Escreva regras, posturas, skills, papéis, workflows e apresentação sob `primitives/`. Instruções e
autoridade de papel são compartilhadas; configurações nativas de modelo/ferramenta pertencem a
`adapters/<runtime>/bindings.json`. Corpos de workflow usam `{{arguments}}`; a projeção de comando
do Claude traduz isso para sua sintaxe de argumento nativa. Os caminhos de fonte existentes em
`claude/` são links de compatibilidade ou visões geradas, não outro lar de autoria. Uma nova
regra, skill, papel ou workflow também precisa de sua entrada em `primitives/manifests.json`
([acima](#declare-a-modules-manifest)).

Rode `bin/harness generate` depois de editar papéis, workflows ou templates de instrução base.
`bin/harness generate --check` e o lint rejeitam desvio de projeção. `bin/harness catalog` emite
registros estáveis de tipo/ID/fonte/digest para documentação e leitores de integração. A cobertura
de instalação e a aplicação em runtime são separadas da geração de fonte bem-sucedida.
