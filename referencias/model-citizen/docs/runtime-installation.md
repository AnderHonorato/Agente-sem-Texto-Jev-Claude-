# Instalando primitivos compartilhados em runtimes de agente

Selecione os alvos de forma independente na sua configuração de usuário:

```json
{"claude": {"manage": false}, "codex": {"manage": true}, "vscode": {"manage": false}}
```

`bin/harness config set claude.manage false` faz a mesma mudança. Uma sincronização só para o
Codex cria seu diretório de configuração mesmo em uma máquina nova; ela não exige uma instalação
do Claude. `CLAUDE_CONFIG_DIR` e `CODEX_HOME` selecionam diretórios de runtime não padrão.
`HARNESS_HOME` isola a própria configuração e estado do harness para fixtures. Não é uma
configuração de runtime nativa.

O Codex recebe instruções e identidade compartilhadas, o catálogo de skills sob
`~/.agents/skills`, sete configurações de papel geradas, e cinco skills de workflow `harness-*`. A
geração de fonte e a instalação não estabelecem ativação de hook nativo, confinamento de papel ou
suporte de cliente. A qualificação de runtime é relatada separadamente.

As escolhas de permissão expressam intenção através de controles nativos diferentes. O `manual`
do Codex usa `on-request`, `read-only`, e o revisor de usuário. O `auto` usa `on-request`,
`workspace-write`, e revisão de aprovação automática. O `bypass` usa `never` com acesso completo e
exige a confirmação explícita já existente. O `inherit` preserva as escolhas nativas. O Codex
renomeou o campo de revisor para `approvals_reviewer`, e um cliente descarta uma grafia que não
conhece sem aviso nenhum, então a sincronização pergunta ao cliente instalado qual nome ele aceita
— a partir do próprio schema de protocolo dele, ou de `--strict-config`, nenhum dos dois inicia um
turno de modelo — escreve esse, e remove o outro. Um cliente que não aceita nenhum dos dois fica
sem chave de revisor, um aviso de sincronização e um achado do `citizen doctor`. Requisitos
nativos e sobrescritas de permissão ao vivo podem restringir ou substituir os padrões; esses
mapeamentos não são uma afirmação de que os modos de permissão do Claude e do Codex são
equivalentes.

Mudanças de configuração possuem campos, não arquivos inteiros. Um livro-razão de posse protegido
registra os valores anterior e o último aplicado antes da substituição. A edição de TOML preserva
tabelas/comentários não relacionados; o TOMLKit vem empacotado sem modificações com seu aviso MIT,
então nenhuma instalação global de pacote Python é necessária. Arquivos de editor JSON-com-
comentários são deixados intactos com um diagnóstico explícito.

`citizen diff` detecta conteúdo gerado modificado e configurações possuídas. A desinstalação
restaura valores anteriores somente quando ainda combinam com a última escrita do harness;
mudanças do usuário no meio tempo permanecem, com um relatório de conflito e estado de posse
recuperável. Ela nunca apaga um link redirecionado. Operações concorrentes de
sincronização/desinstalação recusam um segundo escritor. Escritas geradas/de configuração
interrompidas mantêm um registro de intenção que a próxima sincronização consegue reconciliar.

Instruções e skills não gerenciadas exigem adoção explícita. O texto de instrução do Codex
adotado é incluído em projeções subsequentes e restaurado na desinstalação. Arquivos já possuídos
pelo usuário, configurações de MCP/plugin, modelo selecionado e credenciais não são substituídos
por uma configuração padrão.

`sync` instala apenas os padrões do usuário. Sobrescritas de postura de projeto e sessão são
resolvidas pelo adaptador de ciclo de vida naquela invocação; elas nunca redirecionam links
globais usados por outra sessão. `HARNESS_PERMISSIONS` não é uma forma de conceder permissões
nativas a um cliente em execução. Defina uma postura durável através da configuração de usuário e
sincronização, ou use os próprios controles de permissão daquele cliente. Diretórios de
configuração do Claude personalizados recebem um arquivo de instrução importando seu próprio
arquivo pessoal.

A intenção de link e adoção é registrada em diário antes das mudanças de sistema de arquivos,
então uma sincronização interrompida mantém seu caminho de recuperação. JSON/TOML nativo malformado
é rejeitado no preflight. A desinstalação preserva links redirecionados e destinos de restauração
ocupados, retornando um status de conflito e mantendo o manifesto de recuperação. Ela não
sobrescreve nem mesmo um symlink de usuário pendurado para restaurar um backup.

## O instalador de uma linha

`scripts/install.sh` é `sh` POSIX, condensa os oito primeiros comandos do caminho de clonagem em
um só, e é seguro rodar duas vezes. Sua forma é emprestada do `install.sh` do pmstack.

```sh
curl -fsSL https://raw.githubusercontent.com/JakeSelby/agent-harness/stable/scripts/install.sh | sh
```

1. **Requisitos.** `git`, `python3` 3.9 ou mais novo, macOS ou Linux. Um faltando é uma única
   linha nomeando o que instalar, e nada mais roda.
2. **Checkout.** Clona `--branch stable` em `~/repos/agent-harness`. Um checkout já existente ali
   é atualizado (fetch) e avançado (fast-forward) em vez de clonado de novo; um que não consegue
   avançar, e um destino ocupado por algo que não é um checkout git, ambos param o script em vez
   de serem reconciliados por você.
3. **Configuração.** `bin/harness init --yes` escreve `~/.config/agent-harness/config.json` a
   partir do exemplo, tirando o nome de `git config user.name`, o identificador de um `gh` logado
   e o fuso horário do sistema. Qualquer campo que não consiga responder mantém seu valor de
   exemplo e é listado ao final para `citizen config set`. Uma configuração já existente nunca é
   reescrita.
4. **Prévia.** `bin/harness install --dry-run`, que não escreve nada.
5. **Próximo comando.** Ele imprime `bin/harness install` e `bin/harness uninstall` e para. O
   script nunca roda `install` sem `--dry-run`.

Qualquer falha sai com código não-zero e uma linha nomeando o passo. `HARNESS_CHECKOUT` move o
checkout, `HARNESS_BRANCH` acompanha outra branch, `HARNESS_INSTALL_NO_HOMEBREW=1` e
`HARNESS_INSTALL_NO_APPS=1` passam `--no-brew` e `--no-apps` para a prévia, e qualquer coisa
depois de `sh -s --` também é passada a ela.

Não existe pacote PyPI, e nenhum está planejado. O harness roda *a partir do seu checkout*: todo
hook em `~/.claude/settings.json` roda um script sob `~/.claude/hooks/harness`, que é um link para
dentro do checkout; as regras, posturas e skills em `~/.claude` também são links para lá; e o
parser TOML empacotado é importado relativo a ele. Uma cópia instalada em um diretório
`site-packages` teria que se tornar esse checkout, então o script clona um em vez disso.
[O modelo de sincronização](sync-model.md) tem o detalhe.

## Instalar a partir do marketplace de plugins

O Claude Code consegue carregar os primitivos projetados sem um checkout. Em uma sessão:

```
/plugin marketplace add JakeSelby/agent-harness
/plugin install model-citizen@model-citizen
```

`.claude-plugin/marketplace.json` lista um plugin cuja fonte é a raiz do repositório, então a
instalação lê `.claude-plugin/plugin.json` e nada é duplicado entre os dois manifestos. Esse
manifesto carrega as skills, os onze papéis de subagente, os comandos de barra e o estilo de
saída. O Claude Code os coloca em namespace: uma skill de plugin é `/model-citizen:<name>`.

### Movendo uma instalação de plugin `agent-harness` para `model-citizen`

O plugin foi publicado como `agent-harness@agent-harness` antes da renomeação. O Claude Code
mantém esse ID quando sua cópia do marketplace se atualiza, e o plugin então falha ao carregar,
porque o marketplace não lista mais um plugin com esse nome. Adicionar o mesmo repositório de
novo não faz nada enquanto o marketplace antigo está registrado, então o plugin e o marketplace
antigos saem primeiro.

Com um checkout instalado, rode:

```sh
citizen upgrade --dry-run   # imprime os quatro comandos `claude plugin`
citizen upgrade             # os executa
```

Ele lê o escopo da instalação antiga e a fonte registrada do marketplace a partir do estado de
plugin do Claude Code, depois desinstala `agent-harness@agent-harness`, remove o marketplace
`agent-harness`, adiciona o marketplace de novo a partir da mesma fonte e instala
`model-citizen@model-citizen`, nessa ordem. Um passo que falha para a execução e imprime os passos
que não rodaram. Sem a CLI `claude` no seu PATH, ele imprime os passos de sessão em vez disso.

Uma instalação só de plugin não tem comando `citizen`, então rode os passos em uma sessão. A linha
`add` usa a fonte de onde você adicionou o marketplace pela primeira vez; se foi um fork ou um
caminho local, adicione esse em vez de `JakeSelby/agent-harness`:

```
/plugin uninstall agent-harness@agent-harness
/plugin marketplace remove agent-harness
/plugin marketplace add JakeSelby/agent-harness
/plugin install model-citizen@model-citizen
```

As skills se movem de `/agent-harness:<name>` para `/model-citizen:<name>`. `citizen doctor`
reconhece qualquer um dos dois IDs, nomeia `citizen upgrade` enquanto o antigo está habilitado, e
avisa enquanto os dois estão habilitados, porque toda skill carregaria em dobro. `citizen sync`
imprime o mesmo aviso. O diretório sincronizado em si não é afetado pela renomeação do plugin.

Uma instalação de marketplace é um subconjunto estrito de `bin/harness install`. Ela não te dá:

- o diário de posse, `citizen diff`, ou uma `citizen uninstall` que restaura;
- seleção de postura — nenhuma regra, nenhuma projeção de `CLAUDE.md`, nenhum arquivo pessoal;
- a projeção do Codex sob `~/.agents/skills` e `~/.codex`;
- hooks, então a avaliação de comando, o gate de parada e o feed de uso ficam todos desligados.

O caminho de marketplace é sua própria superfície de cliente no
[catálogo de compatibilidade](compatibility.md) e é **não qualificado**: nenhuma evidência nativa
foi registrada para ele. `citizen doctor` relata qual dos dois caminhos está ativo.
