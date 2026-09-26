# O que é suportado

A arquitetura é agnóstica de provedor de modelo: suas regras, skills, papéis, workflows e posturas
pessoais têm uma única fonte. Isso não significa que todo runtime implementa toda capacidade.
`compatibility/catalog.json` é a autoridade versionada; `citizen compatibility --json` a emite. Uma
[política de compatibilidade e lançamento](compatibility-policy.md) separada define as interfaces
v1 estáveis, o limite de prévia, versionamento, depreciação e regras de migração.
Uma entrada **qualified** (qualificada) exige evidência nativa para seu runtime, cliente e
plataforma exatos. **Unqualified** (não qualificada) significa nenhuma evidência completa
aprovada, **planned** (planejada) significa nenhuma integração atual, e **unsupported** (não
suportada) significa uma combinação explicitamente fora do contrato de integração.

O Claude Code e o Codex são os alvos de integração deste lançamento. O piso de suporte estável da
v0.13.1 qualifica o CLI do Claude Code no macOS e no Linux; contra a v0.13.0 ele só muda o texto
da página inicial. O CLI do Codex está fora desse contrato até que uma rodada de qualificação com
script concorde com uma conduzida manualmente, então o piso estável da v0.11.1 continua sendo o
último a qualificar o CLI do Codex no macOS e no Linux. As superfícies do Claude Code e do Codex
no VS Code, o Codex Desktop no macOS e a instalação via marketplace de plugins do Claude Code
permanecem como prévias não qualificadas. Uma instalação de marketplace carrega apenas as skills,
papéis, comandos e estilo de saída; o diário de posse, a seleção de postura, a projeção do Codex e
os hooks vêm de `bin/harness install`, e [instalação de runtime](runtime-installation.md) declara
a diferença. Não leia geração de fonte bem-sucedida ou testes determinísticos como qualificação de
cliente nativo.

## O que "qualificado" significa em cada nível

A qualificação de cliente e a qualificação de capacidade são alegações separadas, e esta é a regra
padrão que as reconcilia; uma decisão de mantenedor pode substituí-la, nesta seção:

> Um cliente é qualificado quando seus casos de aceitação obrigatórios passam nativamente. Uma
> capacidade é qualificada para um cliente somente quando esse cliente é qualificado E um caso de
> aceitação nativa que exercita essa capacidade existe e passou; caso contrário, a capacidade é
> `unqualified` e não herda nada do cliente. O catálogo é a autoridade única: o estado por
> capacidade é derivado dos arquivos de capacidade dos adaptadores no momento de `citizen compatibility`
> e renderizado ao lado da linha do cliente, nunca editado à mão em dois lugares.

Um adaptador nomeia os casos que exercitam uma capacidade com uma lista opcional
`acceptance_cases` em uma entrada de postura ou em `role_execution` em
`adapters/<runtime>/capabilities.json`; todo nome nela precisa ser um dos `required_cases` do
catálogo. Listar casos sob uma capacidade que não é `qualified`, ou alegar `qualified` sem eles, é
uma contradição entre os dois arquivos: `citizen compatibility --release-check` bloqueia o
lançamento e a suíte de teste falha. Hoje nenhum adaptador nomeia um caso e nenhum cliente é
qualificado, então toda célula abaixo lê `unqualified`, que é o que a tabela diz.
`citizen compatibility --json` emite os dois níveis, cada linha de cliente carregando suas
`capabilities` derivadas. O layout de capacidade-por-cliente segue a matriz gerada em
[`docs/harnesses.md` do wshobson/agents](https://github.com/wshobson/agents/blob/main/docs/harnesses.md).

A última linha da tabela responde a uma pergunta diferente: não se uma capacidade carrega
evidência nativa, mas se o teto de camada de modelo da postura `delegation` se aplica nessa
superfície. `tier_restriction` em `adapters/<runtime>/capabilities.json` a declara por runtime,
com uma entrada `without_hooks` para um cliente que não instala nenhum hook —
`"installs_hooks": false` em um cliente do catálogo, que hoje é a instalação via marketplace de
plugins. As superfícies CLI e VS Code do Claude Code leem `enforced`, porque
`claude/hooks/tier-agent-spawns.py` reescreve uma chamada `Agent` que pede a classe mais forte por
`model:` para a classe abaixo, a menos que o papel que ela nomeia declare essa classe ele mesmo.
Toda superfície do Codex lê `advisory`: o coordenador de fato roda ali, e uma chamada `Agent` do
Codex ainda passa pelas verificações de papel, marcador, evasão e brief, mas a reescrita de camada
está atrás de um portão `runtime == "claude-code"` em `lib/harness_core/lifecycle.py`, então o
teto alcança o Codex só como prosa projetada. A instalação de marketplace lê `advisory` pelo motivo
mais simples de que não instala nenhum hook.

<!-- harness:compatibility:start -->
**Qualificado:** `claude-code-cli-macos`, `claude-code-cli-linux`.

**Não qualificado:** `claude-code-vscode-macos`, `claude-code-plugin-marketplace`, `codex-cli-macos`, `codex-vscode-macos`, `codex-desktop-macos`, `codex-cli-linux`.

**Planejado:** `cursor`, `grok`.

O status de um cliente não é o status de uma capacidade. Cada célula é derivada do `adapters/<runtime>/capabilities.json` daquele runtime no momento da geração:

| Capacidade | `claude-code-cli-macos` | `claude-code-vscode-macos` | `claude-code-cli-linux` | `claude-code-plugin-marketplace` | `codex-cli-macos` | `codex-vscode-macos` | `codex-desktop-macos` | `codex-cli-linux` |
|---|---|---|---|---|---|---|---|---|
| `autonomy` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `build-vs-buy` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `commits` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `cost` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `delegation` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `licensing` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `plan-ceremony` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `role_execution` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `testing` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| `voice` | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified | unqualified |
| restrição de camada | enforced | enforced | enforced | advisory | advisory | advisory | advisory | advisory |

A última linha não é um estado de qualificação. Ela diz se o teto de camada de modelo da postura de delegação é **enforced** (um hook reescreve ou recusa o spawn), **advisory** (só texto de prompt) ou **none**, carregado como advisory por `primitives/skills/delegation-tiering/SKILL.md`, `primitives/stances/delegation/tiered.md`; enforced por `claude/hooks/tier-agent-spawns.py`. `enforced` é mais estreito do que parece. Nunca alcança o próprio modelo da sessão: a chave de configuração `model` é uma que este harness nunca escreve (`docs/settings-ownership.md`). Dentro de uma sessão, ele reescreve um spawn apenas enquanto a variante `delegation` selecionada é `tiered`. `off` para o spawn em vez disso, qualquer outra variante o deixa intacto, e ele só age enquanto a tabela de classes do adaptador mapear pelo menos dois modelos, já que uma classe não é uma escada para mover um spawn para baixo. Sob qualquer outra condição o teto é prosa, exatamente como `advisory` é em toda parte.
<!-- harness:compatibility:end -->

Agentes hospedados e mesclagem de memória nativa continuam adiados. A [ligação architecture-viewer](viewer-integrations.md)
é uma prévia para adaptadores personalizados instalados separadamente. Um candidato local de
protocolo 1 passou na aceitação do harness em nível de processo; nenhum visualizador é empacotado,
e a interação com visualizador nativo e a aprovação de distribuição/licença permanecem não
verificadas. O Windows nativo não é suportado; o WSL2 não foi qualificado.

Um provedor de modelo fornece o modelo. Um runtime de agente orquestra suas ferramentas e
contexto. Uma superfície de cliente é o CLI, integração de editor ou aplicativo desktop que expõe
esse runtime. O Cursor pertence ao catálogo de integração runtime/cliente, com provedores de
modelo descritos separadamente: selecionar o mesmo provedor subjacente não prova comportamento
equivalente do Cursor.

## Procedimento de qualificação

O [runbook de qualificação](qualification-runbook.md) cobre a mecânica de uma execução: a
invocação do executor de aceitação, seus diretórios home descartáveis e as credenciais que passa
adiante. Comece com um diretório home de usuário/configuração de teste isolado e um repositório
descartável. Registre versões exatas de runtime e cliente, sistema operacional, commit de origem,
data, configuração, comandos e resultados observados. Nunca faça commit de credenciais,
transcrições privadas completas ou configurações pessoais. No macOS, rode `citizen keychain <home>`
em qualquer diretório home que você construir manualmente antes de um cliente ser lançado sob ele;
um diretório home sem chaveiro padrão levanta uma caixa de diálogo do sistema, e um diretório home
cujo chaveiro não pode ser criado não lança um cliente. Nunca redirecione seu próprio chaveiro
padrão ou lista de busca. Para todo alvo listado no catálogo, verifique toda entrada de
`required_cases` nativamente:

1. Instale, reinicie, e inspecione as instruções efetivas, skills descobertas e papéis
   registrados.
2. Troque uma postura representativa de comunicação e delegação; observe tanto o texto de
   instrução quanto o comportamento de agente/ferramenta. Repita com uma dimensão personalizada,
   sobrescrita de projeto e escolha inválida.
3. Exercite posturas de manual, auto e bypass reconhecido contra restrições nativas. Leia cada
   postura duas vezes: o modo de permissão que a sincronização escreveu nas próprias configurações
   do cliente, e o que o cliente então fez com uma escrita de arquivo. Uma postura `bypass` precisa
   ser recusada pela sincronização até ser reconhecida, e a sincronização recusada precisa deixar
   o modo onde estava. Julgue o bypass reconhecido pelas próprias negações de permissão e modo do
   turno, nunca só pelo arquivo escrito: um turno que o modelo recusou por julgamento próprio não
   observou nenhum controle de permissão e é não verificado, não um bloqueio.
4. Verifique confiança de hook, composição, negações e patches multi-arquivo; tente escritas de
   papéis somente-leitura e fora do escopo de artefato do planner. Padrões de configuração são
   prova insuficiente.
5. Mude arquivos preparados (staged) e não rastreados depois de um gate verde; verifique
   reexecuções e falhas não verificadas.
6. Conduza o hook de spawn em um diretório home descartável contra uma receita fixa construída a
   partir de um descritor em `policy/integrations/`: confirme que um brief carregando o trabalho de
   um papel restrito é negado com a instrução de worker isolado, seja ele feito spawn sem nome, sob
   um tipo de subagente genérico ou sob o nome de um worker de banda; e que a recusa oferece
   exatamente as raízes de entrada declaradas por esse descritor, e nenhuma outra, como as raízes
   de leitura às quais o worker fica limitado. O spawn da receita é negado, então o roteamento é
   observado em um spawn simples separado que não carrega nenhum do texto da receita: confirme que
   ele roda como o worker de banda padrão da variante de custo, na classe e esforço dessa linha,
   com a frase de orçamento em seu brief, e que uma variante nula não reescreve nada. Nenhum
   workflow próprio de framework terceiro é rodado em uma rodada de qualificação; essa é a suíte
   opcional em [BMad](bmad.md).
7. Continue a mesma tarefa Claude→Codex e Codex→Claude, incluindo casos de árvore alterada e
   escritor desatualizado; estabeleça permissões de novo. Verifique que migração, desvio e
   desinstalação preservam dados do usuário.
8. Selecione uma variante de custo não padrão e sincronize; confirme que só os papéis que ela muda
   são reescritos e que todo outro papel mantém seu link. Em uma sessão iniciada depois dessa
   sincronização, faça spawn de um subagente que não nomeia nenhum papel, e confirme, a partir da
   própria transcrição do subagente, que ele rodou como o worker de banda padrão da variante, no
   modelo e esforço dessa linha, que seu brief termina com a frase de orçamento, que o feed de uso
   relatou seu gasto contra esse orçamento, e que `citizen usage --rescan --by role` registra a
   linha roteada. Confirme que uma sessão iniciada antes de os workers serem instalados os mantém
   fora do seu registro de sessão e que seu spawn ainda tem sucesso. Um cliente headless roda cada
   turno como seu próprio processo, então tal sessão é continuada retomando-a, e o processo
   retomado carrega os workers do disco e os anuncia; seu spawn pode então rotear para o worker de
   banda anunciado, mas nunca para um que nem seu registro nem esse anúncio nomearam. Depois
   selecione uma variante com o feed desligado, sem banda padrão e sem orçamentos, e confirme que
   nada disso ocorre. Em um runtime que não roteia spawns nativos, verifique a postura através do
   modelo e esforço de um worker de papel isolado e a frase de orçamento no brief de um papel
   nomeado, e registre o feed como não aplicável com esse motivo.
9. Rode uma camada de review de um framework nomeado por um descritor em `policy/integrations/`
   como um subagente nativo que não nomeia nenhum papel, com o brief carregando o próprio texto de
   spawn do framework do jeito que seu workflow o entrega ao cliente, e confirme que o spawn é
   recusado e que a recusa nomeia o framework, a camada e `citizen role run <role>`. Depois peça em
   palavras simples a mesma review de camada, nomeando o arquivo de prompt da camada e nenhum
   papel, para que o cliente escreva o brief sozinho, e confirme que esse brief é recusado da mesma
   forma: um brief direcionando o subagente a seguir ou aplicar um arquivo de prompt declarado é o
   trabalho da camada em qualquer formulação. Um modelo que não faz nenhuma chamada, ou cujo brief
   não nomeia nenhum dos arquivos de prompt declarados, deixa o caso não verificado. Confirme que
   a mesma camada, rodada da forma roteada, escreve estado de worker isolado e retorna achados, e
   que uma sessão sem estado de worker escrito é um caso falho, não uma review aprovada. Depois o
   falso positivo: faça spawn de trabalho comum cujo brief menciona review, um diff ou achados de
   passagem, e um que edita as próprias raízes de entrada do framework, e confirme que os dois
   rodam.

Guarde um artefato de evidência JSON redigido com `kind: native`, `client`, `harness_version`,
`source_commit`, `runtime_version`, `client_version`, `platform`, `observations`, `cases`,
`invalidation_scope` e `case_map`, com os valores de caso `passed`, `failed`, ou `unverified`. Cada
observação de caso abre com o nome do seu caso e dois-pontos, um por caso na ordem ordenada de
casos do registro, então o pareamento nunca depende de posição; uma nota de nível de rodada que o
executor de rodada anexa não carrega nenhum prefixo de caso. Adicione seu caminho e SHA256 à
entrada do cliente. A evidência não pode ser reaproveitada para outro cliente ou versão de harness.
Seu commit de origem completo precisa ser ancestral do lançamento, e o resultado de um caso só
conta enquanto nenhuma mudança subsequente estiver sob os caminhos que invalidam esse caso nesse
alvo; uma mudança sob um caminho que o mapa caso-para-caminho não atribui invalida todo caso no
registro. Defina versões exatas de runtime/cliente antes de mudar o status para qualified. Todo
registro linkado precisa combinar com a versão exata de runtime, versão de cliente e plataforma do
catálogo. Resultados falhos ou não verificados linkados bloqueiam a qualificação mesmo que outro
registro passe o mesmo caso. Quando uma nova execução substitui um registro, remova a referência
antiga da alegação ativa preservando o arquivo de evidência histórico. Casos e valores de resultado
desconhecidos são rejeitados.
O executor anexa cada caso terminado a um log durável conforme o caso é concluído, então uma
rodada morta custa o caso que estava rodando em vez da rodada; reconstrua os casos sobreviventes
em um registro com `--from-progress`, e linke esse registro parcial como o registro parcial que é.
O CLI verifica esses registros e `citizen compatibility --release-check` falha até que todo cliente
obrigatório esteja qualificado. Um revisor precisa avaliar as observações; um rótulo JSON sozinho
não é evidência empírica.

### Onde cada alvo roda, e o que ele precisa

Os alvos obrigatórios são as quatro linhas de CLI que o piso estável da v0.11.1 qualificou. Toda
rodada até hoje, da 0.9.0 até a 0.11.1 nas quatro, rodou em um único Mac de silício Apple possuído
por um mantenedor; não há outro host de qualificação e nenhum executor hospedado. O que cada alvo
precisa nesse host:

- **`codex-cli-macos`.** O binário é o empacotado no aplicativo desktop do ChatGPT,
  `/Applications/ChatGPT.app/Contents/Resources/codex`, ligado ao `PATH` como
  `~/.local/bin/codex`. O aplicativo o atualiza, então a versão é o que quer que
  `codex --version` relate no dia e o registro a nomeia (a 0.11.1 registrou
  `0.154.0-alpha.6.2`). Ele autentica com uma sessão de conta ChatGPT, `codex login`, que escreve
  `~/.codex/auth.json`; nenhuma chave de API é usada. O host é o próprio Mac.
- **`codex-cli-linux`.** O `@openai/codex` do npm na versão que a rodada fixa (a 0.11.1 registrou
  `0.155.1`), instalado por [`scripts/linux-target.Dockerfile`](../scripts/linux-target.Dockerfile).
  O host é um container linux/arm64 sob o Docker Desktop no mesmo Mac, com o clone congelado
  montado nele. Como ele autenticou não está registrado: os registros da 0.11.x dizem só que cada
  sondagem rodou com um diretório home descartável e diretório home do Codex. O `codex login`
  dentro do container do runbook é uma sugestão, não o que essas rodadas são conhecidas por ter
  feito.
- **`claude-code-cli-macos`.** A instalação nativa do Claude Code, versão de `claude --version`.
  Ele autentica com uma credencial que o executor de aceitação passa adiante pelo nome, uma chave
  de API Anthropic ou um perfil de nuvem; um `claude login` interativo não alcança o diretório home
  descartável do executor. O host é o próprio Mac.
- **`claude-code-cli-linux`.** O `@anthropic-ai/claude-code` do npm na versão fixada (a 0.11.1
  registrou `2.1.278`), no mesmo container e autenticado da mesma forma, a variável passada pelo
  nome com `docker run -e`.
- **O estilo de saída da voz `concise`.** `concise` seleciona pelo nome o estilo de saída
  embutido `Concise` do Claude Code. Foi verificado presente no Claude Code 2.1.280; versões
  anteriores, incluindo o cliente Linux fixado (`2.1.278`), não são verificadas, e o mesmo vale
  para se sessões de ponte e do Agent SDK aplicam `outputStyle`. Onde o estilo está ausente, o
  texto de postura ainda carrega os formatos de resposta.

O [runbook](qualification-runbook.md#target-hosts) tem os comandos que estabelecem cada um desses
antes de uma rodada, e `python3 scripts/smoke_tier.py --targets <ids>` recusa a rodada na hora
quando um cliente, um login do Codex ou o daemon do Docker está ausente. Um login do Codex é uma
sessão, não uma chave, e o `CODEX_HOME` descartável do executor de aceitação ainda não a carrega,
então a evidência de um alvo Codex só pode ser produzida manualmente até que carregue; nenhum alvo
Codex é qualificado para a origem atual.

Se um lançamento não conseguir qualificar os alvos Codex ou Linux, ele estreita o piso de suporte
que o último lançamento qualificado definiu. Esse estreitamento é declarado na seção de abertura
desta página como uma decisão, como é o da v0.12.0, e nunca é um alvo silenciosamente deixado fora
de uma rodada.

### Qual mudança de origem invalida qual evidência

A evidência é invalidada por alvo, não por repositório. O conjunto de caminhos de um alvo é a
origem de runtime compartilhada — `VERSION`, `bin`, `lib`, `adapters`, `primitives`, `policy`,
`templates`, `config.example.json` — menos o diretório de adaptador de todo *outro* runtime, como
o bloco `evidence_invalidation` do catálogo os mapeia, **exceto pelos arquivos dentro de tal
diretório que código compartilhado lê seja qual for o runtime em execução**. Esses são recortados
de volta para o conjunto compartilhado e invalidam todo alvo. O bloco os nomeia: hoje
`bindings.json` (`citizen tiers` verifica as tabelas de classe dos dois adaptadores em um único
comando), `capabilities.json` (a cobertura de postura e a reconciliação de catálogo leem as de
todo runtime) e `worker.py` (`citizen role run --runtime` escolhe o adaptador por flag, então o
worker de qualquer runtime é alcançável de qualquer sessão). Só `hook.py` e o ponto de entrada de
observação `observe.py` são privados ao seu runtime: um cliente executa os hooks do seu próprio
runtime, e `citizen sync` escreve o caminho de `hook.py` do outro runtime em um arquivo de
configuração sem lê-lo.

Então uma correção confinada a `adapters/codex/hook.py` deixa de pé os alvos Claude Code de uma
rodada, e o contrário também vale. Uma mudança à origem compartilhada, a um arquivo recortado em
qualquer diretório de adaptador, ou a um arquivo sob `adapters/` que nenhum runtime possui, ainda
invalida todo alvo.

O escopo falha fechado. Um runtime que o catálogo não mapeia não é excluído de nada e mantém a
regra de origem inteira; um caminho declarado que não é o próprio diretório
`adapters/<runtime>` desse runtime, ou que nomeia um runtime que nenhum cliente roda, é rejeitado;
uma declaração que não recorta nenhum arquivo compartilhado é rejeitada em vez de aceita sem
questionamento; exclusões são emitidas como pathspecs literais para que nenhum glob ou `..` possa
alargá-las; e um registro que não carrega nenhum `invalidation_scope`, ou cujo escopo é malformado
ou difere do que o catálogo concede, é verificado contra a origem inteira ou recusado. Cada
registro declara o escopo sob o qual foi validado, então um revisor lê a suposição do artefato em
vez de recalculá-la.

`tests/test_adapter_directory_isolation.py` guarda a declaração da origem: ele analisa todo
arquivo Python rastreado sob os caminhos compartilhados — falhando em um que não consegue
analisar, em vez de pulá-lo — afirma que ainda encontra os carregadores que deveria cobrir, e
falha quando código compartilhado constrói um caminho para um arquivo de adaptador que o bloco não
declara, nomeia o diretório de outro runtime de forma direta, ou alcança um adaptador através de
um symlink. O que ele não consegue provar é a metade de `runtime_files`: que `hook.py` só é
carregado para o runtime cuja sessão está rodando é uma leitura de mantenedor dos pontos de
chamada, e uma entrada errada ali é um acoplamento que este escopo deixaria passar.

#### Por caso, dentro do alvo

Dentro do conjunto de caminhos de um alvo, a evidência também é invalidada por caso de aceitação.
O mapa `case_paths` do bloco nomeia, para todo caso obrigatório, os caminhos de origem cuja
mudança pode alterar o que esse caso observa:

```json
"case_paths": {
  "version": 1,
  "cases": {
    "installation": [],
    "role-confinement": ["adapters/claude-code/worker.py", "adapters/codex/worker.py"]
  }
}
```

Um caminho é um arquivo ou diretório literal sob um dos caminhos de origem de runtime, sem glob,
sem segmento `.` ou `..` e sem barra inicial ou final; um diretório cobre todo arquivo sob ele.
Todo caso obrigatório é uma chave, então adicionar um caso força uma alegação sobre ele, e uma
lista vazia alega que o caso não depende de nenhum dos caminhos mapeados. Quando a origem muda
depois do commit de um registro, os arquivos mudados dentro do conjunto de caminhos do alvo
decidem o que sobrevive:

- um arquivo mudado sob um caminho que algum caso nomeia torna cada caso que o nomeia **stale**
  (obsoleto), e deixa os outros casos do registro de pé;
- um arquivo mudado sob nenhum caminho de nenhum caso invalida o registro inteiro, então o mapa
  falha fechado: origem compartilhada como `bin`, `lib`, `primitives` e `policy` não é mapeada
  para nenhum caso hoje, e qualquer mudança nela ainda custa a rodada.

Um resultado stale nem passa nem bloqueia. Ele descreve origem que não existe mais, então a
alegação precisa desse caso executado de novo, e um registro carregando apenas os casos
reexecutados, linkado ao lado do mais antigo, o completa. `citizen compatibility` nomeia um caso
stale que nada responde, com os arquivos que o tornaram stale.

Todo novo registro de evidência carrega `case_map`, a `version` do mapa e o SHA-256 dos seus
casos, do jeito que o executor de aceitação os encontrou no catálogo. Um registro cujo `case_map`
está ausente, ou difere do catálogo, é tratado como escopado ao alvo inteiro: qualquer mudança no
conjunto de caminhos do seu alvo o invalida por completo. Então a versão do mapa é o que um revisor
lê para ver o que um registro assumiu, e mudar o mapa, seja uma entrada nova ou uma mais estreita,
a incrementa; o digest faz uma edição que esquece o incremento falhar fechado em vez de
silenciosamente reescopar registros antigos.

O mapa é uma alegação de mantenedor sobre acoplamento, e o risco é declarado com clareza: uma
mudança que altera o que um caso observa através de um caminho que o mapa não atribui a ele passa
despercebida para esse caso. Uma entrada só é adicionada com seu argumento aqui, e o argumento
nomeia os pontos de chamada. Hoje há um:

- **`adapters/<runtime>/worker.py`** só é carregado por `citizen role run`, através de
  `harness_core.workers`, e nenhum hook ou início de sessão o carrega. O executor conduz
  `role run` em `role-confinement` e `spawn-confinement`; `cost-posture` verifica um runtime que
  não roteia spawns nativos através de um worker de papel, e `framework-spawn-routing` roda o
  turno de cost-posture. Esses quatro casos nomeiam os workers dos dois runtimes, já que qualquer
  um é alcançável de qualquer sessão; os outros oito ficam de pé quando só um worker muda.

`tests/test_evidence_case_scope.py` guarda o mecanismo desta regra, e verifica que todo caminho
mapeado existe. Veja [#582](https://github.com/JakeSelby/agent-harness/issues/582).

Um catálogo lançado fixa o commit de origem exato cuja evidência qualifica. Desenvolvimento
posterior não reescreve nem invalida esse registro histórico de lançamento, mas qualquer mudança
sob os caminhos de origem de runtime faz `citizen compatibility --release-check` falhar até que a
nova origem tenha seu próprio catálogo candidato e evidência nativa.

[Controles de runtime](runtime-controls.md) registra as lacunas de aplicação atuais. A cobertura
de adaptador em `citizen stances --json` distingue política de instrução, hooks e configurações,
incluindo posturas personalizadas, que são consultivas por padrão. Nenhuma preferência sobrescreve
uma restrição nativa.
