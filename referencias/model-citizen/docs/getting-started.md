# Comece pela sua forma de trabalhar

Anteriormente Agent Harness.

Model Citizen é um harness de primitivos personalizados compartilhados para os dois runtimes que
suporta hoje, Claude Code e Codex. Suas posturas pessoais são switches de comportamento:
comunicação, delegação, testes, autonomia e tomada de decisão. A mesma seleção se resolve em
ambos os runtimes, e três dos nove eixos — autonomy, delegation e cost — se ligam a mecanismos de
aplicação em vez de a prosa.

## Escolha um runtime e inspecione o suporte

Claude Code e Codex são alvos de integração. Revise a [compatibilidade](compatibility.md) antes de
escolher um cliente; projeções candidatas não são prova de suporte nativo. Cursor e Grok estão
planejados. Você precisa da sua própria conta e cobrança de runtime, Git e Python 3.9+. O Windows
nativo não é suportado; o WSL2 não é qualificado. O harness não vende nem fornece acesso a modelo.

## Instalar

Um único comando clona a branch `stable` para `~/repos/agent-harness`, escreve uma configuração
padrão e mostra uma prévia da instalação sem executá-la:

```sh
curl -fsSL https://raw.githubusercontent.com/JakeSelby/agent-harness/stable/scripts/install.sh | sh
```

Leia a prévia impressa, depois selecione quais runtimes gerenciar e instalar:

```sh
cd ~/repos/agent-harness
bin/harness config set claude.manage true
bin/harness config set codex.manage true
bin/harness install --dry-run
bin/harness install
```

Para clonar manualmente, ou para ver o que cada passo do script faz, leia
[posse da instalação](runtime-installation.md#the-one-line-installer).

Você pode definir qualquer um dos runtimes como false; uma configuração só para o Codex não
precisa de configuração do Claude. A instalação adiciona as ferramentas do runtime selecionado que
faltam e sincroniza sua configuração. No macOS também pode instalar pacotes do Homebrew e o VS
Code; revise `install --help` para pular essas operações. Quando as ferramentas já estão
instaladas, use `sync --dry-run` e depois `sync` em vez disso.

Complete o login de cada cliente selecionado. `citizen doctor` relata arquivos e configuração, não
prova de que um login ou hook nativo está ativo. Inicie uma nova sessão e aceite a confiança de
hook nativa onde o cliente exigir. Use `citizen trust <repo>` separadamente para o gate do
repositório.

## Faça seu primeiro switch

```sh
bin/harness config set stances.voice answer-card
bin/harness stances --json
bin/harness sync
```

A mesma política selecionada alcança os dois adaptadores. Reinicie o cliente para carregar
instruções globais alteradas. [Veja o comportamento resolvido antes e depois de um switch](stance-demo.md),
depois [crie sua própria postura](primitive-authoring.md). Sobrescritas de projeto/sessão ficam
restritas àquela invocação; sincronizar não as torna persistentes nos arquivos globais de todo
mundo.

## Use workflows e continue trabalho

Workflows compartilhados compõem papéis e skills. O Claude expõe projeções de comando; o Codex
expõe projeções de skill `harness-<workflow>`. Ambos usam a mesma fonte. O workflow de handoff
escreve dados de tarefa compartilhados; [continuação de tarefa](task-continuation.md) explica as
verificações de revisão e a verificação em si.

Rode `citizen diff` para desvios, `citizen usage` para medições registradas, e
`citizen compatibility` para qualificação. [Posse da instalação](runtime-installation.md) cobre
diretórios de configuração personalizados, adoção, desinstalação e conflitos. Nunca substitua um
arquivo não gerenciado só para deixar a sincronização silenciosa.

## Sua primeira sessão

A partir do repositório em que você quer trabalhar, inicie qualquer um dos runtimes instalados:

```sh
cd ~/some-folder
claude
# Ou inicie o Codex nessa pasta:
codex
```

Peça ao agente para explicar suas escolhas de postura em vigor, depois tente uma pequena tarefa.
Pesquisa e planejamento podem funcionar sem um repositório de código. Os workflows de build e
review precisam de contexto de repositório; abrir um pull request também precisa de um remoto e de
uma conta do GitHub logada.

Depois feche o ciclo e pergunte quais das suas regras de fato dispararam:

```sh
citizen usage --rules
```

Ele imprime uma linha por detector nos últimos 30 dias — acertos, as sessões que os viram e a
fração — com `--by repo` e `--by stance` reagrupando os mesmos acertos por repositório e pela
variante de preferência em vigor. Em um diretório home novo, ele diz
`no measured sessions in the last 30 day(s)` até que uma ou duas sessões tenham sido registradas;
`--rescan` preenche retroativamente a partir de transcrições que você já tem. [Uso](usage.md)
explica as anotações e o que os números ainda não sustentam.

## O que custa

O acesso ao modelo é cobrado pelo seu provedor ou coberto pela sua assinatura; janelas de limite de
taxa e uso de contexto ainda importam. O harness fornece política, não um modelo de IA nem acesso
pago. [Uso](usage.md) mostra medições observadas sem inventar valores ausentes. O
[guia de preferências](preferences.md) explica a postura de custo. [Como funciona](how-it-works.md)
e [sandboxing](sandboxing.md) explicam os controles. `citizen uninstall` restaura as configurações
possuídas quando possível e relata conflitos em vez de sobrescrever suas edições.
