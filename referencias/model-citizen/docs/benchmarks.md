# Benchmarks de custo

O que o harness custa a você, medido contra o Claude Code sem harness nenhum. O número estático
abaixo existe hoje. A reprodução ao vivo que compara tarefas inteiras tem um executor e ainda
nenhum resultado publicado, então nada aqui alega uma economia.

Um resultado publicado a partir dessas execuções precisa atender ao [padrão de evidência](evidence-standard.md),
e seu plano é um [modelo de pré-registro](pre-registration-template.md) preenchido e commitado
antes do primeiro trial.

## Número estático de contexto

Toda sessão que o harness gerencia começa com suas instruções globais, regras, posturas
selecionadas e estilo de saída já no contexto, mais uma descrição listada para cada agente, skill
e comando. Uma sessão nua do Claude Code não carrega nada disso, então a contagem inteira é o
overhead permanente do harness.

```sh
python3 scripts/cost_bench.py static            # imprime o número para este checkout
python3 scripts/cost_bench.py static --check    # o que a CI roda
python3 scripts/cost_bench.py static --write    # atualiza benchmarks/static.json em um lançamento
```

`benchmarks/static.json` é o número commitado para o último lançamento. Ele registra arquivos,
linhas, caracteres, uma contagem estimada de tokens para a seleção de postura padrão e para a
variante mais longa de cada dimensão, os cinco maiores arquivos, e quanto essa quantidade de
tokens custa por modelo. Seu bloco `scopes` nomeia o conjunto sobre o qual cada contagem é feita,
porque os limites que `citizen lint` imprime são sobre um conjunto mais estreito.

- **Tokens são uma estimativa:** caracteres divididos por quatro. Ela existe para mostrar a
  tendência entre versões sem tokenizador, chamada de rede ou chave de API. Não é um número de
  cobrança.
- **Os valores em dólar vêm de `policy/prices.json`.** `session_start` precifica a camada como uma
  escrita de cache, `later_turn` como uma leitura de cache. Uma sessão que ultrapassa a duração do
  cache paga a escrita de novo.
- **A CI falha quando a estimativa cresce mais de 5% acima do número commitado.** Reduza o
  crescimento, ou adicione uma entrada a `benchmarks/allow.json` nomeando `harness_version`, o novo
  `est_tokens` e um `reason`. A entrada para de valer assim que o número se move de novo.
- **Todo arquivo contado é precificado por conta própria.** O mapa `files` dá os caracteres,
  tokens estimados e dólares de cada arquivo, e soma para os totais dentro do arredondamento.
  `--check` imprime uma linha por arquivo cuja estimativa se moveu desde o número commitado,
  precificada no modelo com a maior taxa de leitura de cache, para que uma mudança em uma regra
  leia como o delta daquele arquivo em vez de um total deslocado. O gate de 5% permanece sobre o
  total.
- **Os limites em `citizen lint` são separados.** Eles limitam o pior caso — a variante mais longa
  de cada postura — em tokens e em linhas, apenas sobre instruções, regras e posturas; isso
  rastreia a seleção padrão, incluindo estilos de saída e listagens, em tokens e dólares, versão
  por versão. Ambos usam a mesma estimativa de caracteres dividido por quatro. Qual limite vale, e
  por quê: [how-it-works](how-it-works.md#context-discipline).

### Reduções registradas

Uma linha por mudança que se propôs a encolher o número estático, antes e depois, a partir de
`scripts/cost_bench.py static` rodado na branch dessa mudança. `benchmarks/history.jsonl` não
consegue guardar essas linhas: as dela são razões de reprodução contra um braço nu em um modelo e
um dia, e uma redução estática não tem braço. Leia as linhas em ordem; nenhuma delas é uma medição
ao vivo.

| Mudança | Sempre carregado | Listagens | Total |
| --- | --- | --- | --- |
| Base na 0.12.0 | 5.198 | 2.326 | 7.524 |
| Depois de encurtar descrições de skill e agente (#430) | 5.198 | 1.980 | 7.185 |
| Depois de aparar o estilo de saída (#430) | 4.539 | 1.980 | 6.519 |

## Reprodução ao vivo

`scripts/cost_bench.py replay` roda as tarefas fixadas em `benchmarks/tasks.json` em modo headless,
uma vez contra um perfil do Claude Code logado mas por lo resto vazio e uma vez contra o harness
instalado, e pontua cada execução com uma verificação que o agente nunca vê. Ela chama um modelo e
gasta uso real, então é rodada manualmente em um candidato a lançamento e nunca na CI.

```sh
python3 scripts/cost_bench.py replay --verify-tasks              # prova toda verificação; não chama modelo
python3 scripts/cost_bench.py replay --model <id> --dry-run      # imprime o cronograma
python3 scripts/cost_bench.py replay --model <id>                # 7 tarefas x 2 braços x 2 repetições
python3 scripts/cost_bench.py replay --model <id> \
    --tag v0.12.0 --tag v0.13.0 --harness-config ~/.claude-bench-harness   # duas versões, uma execução
```

- **`--tag` é o que o braço do harness roda, e é repetível.** `candidate`, o padrão, é o harness
  instalado em `~/.claude` como está. Qualquer outro valor é uma referência git deste repositório:
  ela é feita checkout com seu histórico intacto, projetada pelo próprio `bin/harness sync` em um
  diretório de configuração próprio, rodada como um cronograma inteiro, e desmontada antes da
  próxima tag. Cada tag escreve seu próprio arquivo de resultados e sua própria linha de
  histórico, carimbada com a versão e o commit da referência que rodou. Toda referência é
  resolvida antes do primeiro lançamento, então um erro de digitação não custa nada, e
  `--spend-cap` se aplica ao cronograma de cada tag por conta própria.
- **Uma sincronização com tag não toca em nada seu.** Ela roda com um HOME temporário além de um
  `CLAUDE_CONFIG_DIR` explícito, então não lê nem escreve no perfil sob o qual você roda, e não
  renderiza nenhuma identidade ou seleção de postura a partir do seu
  `~/.config/agent-harness/config.json`: um braço com tag carrega os padrões dessa tag, que é a
  mesma pergunta feita a toda tag. Um alvo de sincronização que resolve para o seu perfil ao vivo,
  fica dentro dele, o contém (HOME ou qualquer ancestral) ou é o perfil nu é recusado. Como a
  credencial de um perfil é indexada pelo seu caminho absoluto, um diretório feito para a execução
  não está logado; nomeie um `--harness-config` logado como o diretório em que cada tag é
  sincronizada quando a execução deve gastar de fato. Esse perfil não pode conter nenhum arquivo do
  harness já (um link só conta quando leva a um checkout do harness ou fica em um nome que o
  harness gerencia; o próprio `debug/latest` da CLI não conta), e não pode servir a `candidate` na
  mesma execução, e nenhum dos nomes que a sincronização escreve (`rules`, `skills`, `commands`,
  `agents`, `hooks`, `output-styles`, `plans`, `CLAUDE.md`, `settings.json` e o resto) pode ser um
  link que leve para fora dele. Depois do cronograma de cada tag, exceção ou interrupção incluída,
  a sincronização é retirada de lá em vez de o perfil ser revertido: exatamente os links e arquivos
  que o próprio manifesto e registros de posse da sincronização nomeiam são removidos, um diretório
  que ela criou só some quando vazio, e o único arquivo que ela reescreve no lugar,
  `settings.json`, é devolvido a partir de uma cópia feita antes, por meio de uma escrita atômica.
  Nada mais é tocado: uma transcrição que outra sessão escreveu durante a execução permanece, e
  arquivos de credencial nunca são copiados, reescritos ou apagados, seja lá se já existiam antes
  ou a CLI os criou no meio da execução, então um token renovado continua renovado e um login
  recente continua logado. Nada no perfil é lido além de `settings.json`; um FIFO ou um arquivo
  ilegível é listado pelo seu stat e nunca aberto. Os registros são lidos de onde o harness no HEAD
  os escreve, então o próprio perfil é verificado depois: se qualquer coisa que a sincronização
  poderia ter escrito ainda está lá, ou os registros estavam vazios, a execução para naquela tag
  com os caminhos remanescentes nomeados, antes que outra tag seja lançada em um perfil que a
  recusaria. Se retirar a sincronização falhar, a cópia é mantida e seu caminho impresso. As
  recusas acima são todas decididas antes do primeiro lançamento de qualquer tag; a cópia à parte,
  o checkout e a sincronização rodam conforme chega a vez de cada tag. O checkout fixado é admitido
  na cerca do braço do harness só para leitura, e os resultados de uma tag fixada vão em uma pasta
  nomeada por ela.

- **Os braços diferem só pelo ambiente.** Ambos recebem uma linha de comando: o mesmo `--model`,
  `--strict-mcp-config`, `--max-budget-usd 2`, o próprio `max_turns` da tarefa como `--max-turns`, e
  as mesmas configurações de sandbox, com acesso de rede de comando desligado. O braço nu adiciona
  `CLAUDE_CONFIG_DIR`, apontando para o perfil vazio. A cerca admite o próprio diretório de
  configuração de cada braço e `/tmp` para leitura e escrita, porque a suíte do repositório
  escreve nos dois e uma cerca que admitisse só o padrão da CLI falharia o gate para qualquer braço
  que fosse movido para um perfil de bancada.
- **Nenhum braço tem a web.** `WebFetch` e `WebSearch` rodam no próprio processo da CLI, fora do
  sandbox de comando, então a lista de rede vazia da cerca não os alcança; as regras de permissão
  de um perfil alcançam, e o perfil do harness permite ambos em domínios de documentação. As
  configurações com que todo braço é lançado, portanto, negam as duas ferramentas, e uma negação
  vence qualquer permissão de perfil.
- **O gate de parada pode disparar.** O hook stop-gate roda um gate somente em uma pasta que o
  usuário confiou, e ninguém confia em um snapshot novo. Pela duração de cada execução pontuada,
  seu snapshot é listado em `~/.config/agent-harness/trusted.txt`, onde `citizen trust` lista
  raízes, e exatamente essa linha é removida depois. O snapshot de todo braço é listado; o braço nu
  não tem hook para lê-lo.
- **Toda execução é capturada como `stream-json` com eventos de hook**, o único formato que carrega
  as decisões do hook Stop, então cada linha registra `stop_hooks`, quantas vezes o hook rodou, e
  `hook_blocks`, quantas vezes ele recusou a parada. Um arquivo bruto mantido na forma antiga de
  documento único ainda é lido, com os dois campos `null`.
- **A cerca de cada braço é provada antes de qualquer pontuação.** Uma execução `-p` limitada por
  braço roda `bin/harness lint` sob a cerca e o perfil próprios daquele braço; um braço cujo lint
  não está limpo, ou cuja execução tem uma leitura recusada, recusa toda a reprodução com saída 2
  antes de qualquer execução pontuada ser lançada, e seu custo conta contra `--spend-cap`. A barra
  é o lint em vez da suíte completa porque a suíte depende do perfil em commits de snapshot mais
  antigos. Toda linha pontuada registra `preflight`. `--skip-preflight` contorna a verificação e
  marca as linhas como `skipped`.
- **Toda execução começa em um snapshot descartável fora do diretório home**, lançada com um
  ambiente limpo. Uma pasta sob o diretório home herda os arquivos de instrução do usuário através
  da travessia de pasta-pai, o que colocaria o harness no braço nu. O snapshot guarda um commit,
  então a mudança que resolveu uma tarefa não é alcançável a partir dele, e ele é removido depois da
  pontuação.
- **O custo é o próprio `total_cost_usd` da CLI**, um equivalente de preço de tabela e não dinheiro
  cobrado sob um login de plano. A ordem de execução o muda, porque uma execução posterior encontra
  seu prefixo já em cache, então cada linha também carrega um custo normalizado por cache que
  reprecifica as leituras de cache do primeiro turno de todo fio como escritas de cache. Fica vazio
  quando a saída da CLI não carrega uso por turno.
- **Ao lado, `cache_miss_ratio`: quanto do seu prefixo a execução recomprou.**
  `cache_write / (cache_read + cache_write)` somado sobre todo turno que a execução abriu, threads
  de subagente incluídas, porque o prefixo novo de um fan-out é parte do que a execução custou. A
  aritmética é a de `citizen usage --by prefix`, importada desse módulo em vez de reafirmada, mas
  os dois não são o mesmo número: o número de sessão subtrai os tokens de um subagente, então uma
  execução que fez fan-out lê mais alto aqui, por design. Uma execução cujo output não carrega
  nenhuma cifra de cache por turno, qualquer um de cujos turnos relata uso sem elas, ou cujos
  turnos não relatam nem leituras nem escritas, é `null` e é deixada de fora da média do braço;
  assim também uma execução com erro, cujos turnos não são o gasto que teria tido. Nunca zero:
  zero é uma execução que serviu o prefixo inteiro.
- **Uma execução com erro é um erro, nunca uma falha.** Ela fica fora tanto do custo por tarefa
  aprovada quanto da contagem de aprovações, e é contada ao lado delas. O teto por execução é
  flexível, então o executor também para antes de qualquer lançamento que pudesse levar o gasto
  relatado além de `--spend-cap`.
- **`benchmarks/history.jsonl` guarda uma linha por versão do harness por dia de execução**,
  armazenada como uma razão contra o nu no mesmo dia e modelo; `benchmarks/history.md` é
  renderizado a partir dela. Compare razões entre dias, nunca dólares. O limiar publicável é fixo
  no script: o harness custa no máximo 85% do nu por tarefa aprovada, aprovando não menos que o nu
  menos um, média das repetições.
- **O que é simulado:** prompts de disparo único substituem sessões interativas, 2 das 7 tarefas
  são sintéticas, e uma execução com tag mede a configuração padrão da tag em vez de uma
  configurada.
- **Uma tarefa que não pode ser aprovada honestamente sai do conjunto** e vai para a lista
  `retired` do manifesto com seu motivo e data. `usage-prices` saiu em 2026-09-25: seus testes
  retidos fixam preços ao vivo e nomes de helper que seu prompt nunca dá, e nenhum braço consegue
  alcançar a web para confirmar um preço.

**Status.** A camada ao vivo produziu um resultado não contaminado: 1,052 em um conjunto de quatro
tarefas, acima do limiar de 0,85, então nenhuma alegação de custo é publicada. Duas cifras
anteriores em qualquer direção eram artefatos do sandbox do executor e de um defeito de suíte de
teste, ambos corrigidos desde então. Uma revisão em 2026-09-24 encontrou mais seis formas em que os
braços eram desiguais ou uma tarefa injusta: a contagem de tarefas acima, o teto de turnos, o gate
de parada, o acesso à web, `usage-prices` e a captura de hook. Cada uma é corrigida como descrito
acima, e nenhum resultado foi coletado desde então. Trate esta camada como um instrumento cuja
metodologia está sob revisão, não como um resultado; a camada estática acima é o número em que
confiar hoje.

## Limites

- Só Claude Code. Instruções do Codex são renderizadas no momento da sincronização e não são
  contadas.
- Seu próprio `CLAUDE.personal.md`, arquivos de memória, servidores MCP e saída de hook não são
  contados. São seus, não do harness, e definições de ferramenta MCP sozinhas podem superar tudo
  que é medido aqui.
- Corpos completos de agente e skill só carregam quando usados, então só suas descrições são
  contadas.
