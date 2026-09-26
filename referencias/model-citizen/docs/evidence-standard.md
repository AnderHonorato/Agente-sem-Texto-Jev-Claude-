# Padrão de evidência para resultados publicados

Um resultado publicado é uma alegação sobre o que o harness faz, medida contra o Claude Code sem
harness nenhum. Esta página lista as doze coisas que todo conjunto de prova publicado carrega, e
para cada uma o que a satisfaz. Um conjunto de prova que perde um item não faz nenhuma alegação
sobre o terreno desse item. Um item que genuinamente não se aplica é marcado como não aplicável
com seu motivo; um espaço em branco é uma falta.

A comparação de custo é definida por SM-2 nos requisitos de produto. Onde SM-2 define um termo,
esta página o cita em vez de reafirmá-lo, e a citação vale. A reprodução que produz as linhas está
descrita em [benchmarks de custo](benchmarks.md). Spikes individuais seguem o registro mais leve em
[spikes](spikes/README.md); este padrão é para resultados publicados como alegações.

## Como um conjunto de prova é verificado

- Todo item abaixo está presente, ou marcado como não aplicável com um motivo que esta página
  permite.
- O pré-registro (item 1) foi commitado antes do primeiro trial, e o histórico mostra isso.
- Todo número publicado pode ser rederivado das próprias linhas do conjunto de prova sem chamar um
  modelo.

Um verificador que checa isso mecanicamente está planejado para o conjunto de prova 1 (#799). Até
que seja lançado, a verificação é feita por um revisor contra esta página.

## Os doze itens

### 1. Um plano pré-registrado

**O que é:** hipóteses, métrica primária, salvaguardas, tamanho de amostra, regra de parada e
multiplicidade, escritos antes da execução.

**Satisfeito por:** uma cópia preenchida do [modelo de pré-registro](pre-registration-template.md),
commitada neste repositório antes do primeiro trial da execução que governa. Toda seção do modelo
tem conteúdo ou um "none" explícito com um motivo. A ordem é verificável: a data de committer do
commit que adiciona o plano preenchido precede o horário de início do trial mais antigo nas linhas
do conjunto de prova, e esse commit é ancestral do commit em que a execução foi feita. Essas duas
verificações ordenam os commits, mas quem faz o commit define a data de committer, então elas não
provam que o plano era público antes da execução. Faça o merge do pull request do plano antes do
primeiro trial: a verificação também compara o horário de merge que o GitHub registra para esse
pull request com o início do trial mais antigo. Uma edição depois do primeiro trial não muda o
plano; é uma entrada anexada e datada no registro de desvios do plano, e o resultado publicado
lista todo desvio.

SM-2 fixa os padrões dos quais o plano parte. Sua hipótese:

> **Hipótese pré-registrada:** o harness reduz o Custo-por-Aprovação (Cost-of-Pass) em relação ao
> nu, com uma razão esperada de 0,85, e não reduz a taxa de aprovação em mais que a margem de
> não-inferioridade δ. δ é fixada em 0,125, a fração de uma tarefa do conjunto original de oito
> tarefas, e não encolhe conforme o conjunto cresce.

Sua afirmação de poder, que a seção de tamanho de amostra do plano responde:

> **Poder:** cinco ou mais trials por tarefa e braço, e α 0,05 bicaudal. O conjunto de tarefas e a
> contagem de trials são dimensionados para um poder conjunto de 0,8 nos dois testes da regra de
> decisão, assumindo uma razão verdadeira de 0,85 e taxas de aprovação iguais. O efeito mínimo
> detectável é declarado antes da execução e é no máximo 15%. O conjunto inclui tarefas longas de
> múltiplos turnos.

Sua regra de decisão:

> **Regra de decisão:** a hipótese é sustentada apenas quando ambas as condições valem:
> - o intervalo pareado de 95%, agrupado por tarefa, sobre a razão de Custo-por-Aprovação fica
>   inteiramente abaixo de 1,0;
> - a não-inferioridade da taxa de aprovação se sustenta: o limite inferior do intervalo pareado de
>   95%, agrupado por tarefa, sobre a diferença de taxa de aprovação (harness menos nu) está acima
>   de −δ.

As duas condições são um único teste conjunto, já que ambas precisam valer, então não exigem
correção para multiplicidade. Qualquer teste adicional que possa sustentar uma alegação, como o
subconjunto de tarefas longas ou um número por módulo, é nomeado no plano com sua correção, ou é
rotulado exploratório e não sustenta nenhuma alegação.

### 2. Um conjunto de tarefas congelado com uma solução de referência por tarefa

**O que é:** as tarefas são fixadas antes da execução, cada uma tem uma solução conhecida como
aprovada, e o conjunto é auditado por validade de tarefa e validade de resultado.

**Satisfeito por:** um manifesto de tarefas fixado por commit, que o plano nomeia. Neste
repositório é `benchmarks/tasks.json`, onde cada tarefa nomeia o commit de onde parte e um
`good_sha` que a resolve. Toda tarefa passa por três auditorias, registradas no conjunto de prova:

- **Validade de tarefa:** o prompt é suficiente para fazer a tarefa, e a solução de referência é
  alcançável a partir do commit de início com as ferramentas e o acesso que os dois braços têm.
- **Validade de resultado:** a verificação oculta passa na solução de referência e falha no commit
  de início inalterado. `python3 scripts/cost_bench.py replay --verify-tasks` prova as duas para
  toda tarefa sem chamar um modelo.
- **Nenhuma mudança depois do plano:** o manifesto que a execução usou é idêntico byte a byte ao
  que o plano fixou.

### 3. Modelo, CLI, esforço, data, container, sementes e taxa de fallback fixados

**O que é:** tudo que mudaria o resultado se se desviasse.

**Satisfeito por:** por trial, o ID exato do modelo (nunca um alias), a versão da CLI, a
configuração de esforço, a data e hora em que o trial começou, o digest da imagem do container, e
toda semente que o harness controla, como ordem de tarefa e o bootstrap. A amostragem de modelo não
é semeável (seedable), então o registro diz isso em vez de sugerir o contrário. A taxa de fallback
é a fração de trials que rodaram em um modelo diferente do fixado, lida da própria transcrição de
cada trial; esses trials permanecem nas linhas e são contados, nunca descartados. Uma execução sem
container declara isso, e nomeia a máquina, o sistema operacional e as configurações de sandbox em
vez disso.

### 4. Uma tabela de preços datada

**O que é:** os preços com que todo número de custo foi calculado.

**Satisfeito por:** uma tabela no conjunto de prova com o preço por milhão de tokens para entrada,
saída, escritas de cache e leituras de cache, por modelo, com a data em que foi lida e a página de
onde foi lida. Números de custo são calculados a partir de contagens de token e desta tabela, então
uma mudança de preço posterior é uma rederivação, não uma reescrita das linhas.

### 5. Resultados pareados por tarefa com intervalos e a correlação intra-cluster

**O que é:** os números de toda tarefa para os dois braços lado a lado, os intervalos principais, e
o quão fortemente os trials da mesma tarefa concordam.

**Satisfeito por:** uma linha por tarefa e braço com seus trials, aprovações e custo, e os
intervalos principais que SM-2 define:

> Os intervalos pareados de 95%, agrupados por tarefa, sobre a razão de Custo-por-Aprovação e sobre
> a diferença de taxa de aprovação governam a comparação. Eles vêm de um bootstrap pareado
> agrupado por tarefa, que reamostra tarefas e mantém os trials dos dois braços de uma tarefa
> juntos, ou do método delta.

> Intervalos de Wilson ou bayesianos descrevem a própria taxa de aprovação de cada braço. São
> apenas descritivos, assim como os números por tarefa relatados ao lado do principal.

A correlação intra-cluster de aprovação e de custo dentro de uma tarefa é relatada ao lado deles,
com o efeito de design que ela implica, `1 + (m − 1) × ICC` para `m` trials por tarefa, para que um
leitor veja o quanto os trials por tarefa acrescentaram.

### 6. Uma visão de custo-efetividade

**O que é:** custo e taxa de aprovação mostrados juntos, para que um braço mais barato que aprova
menos seja visível como tal.

**Satisfeito por:** um gráfico ou tabela posicionando cada braço, e cada configuração quando há
mais de duas, por taxa de aprovação contra custo médio por tentativa, com a fronteira de Pareto
marcada e qualquer configuração dominada nomeada. A razão ao lado da qual isso se posiciona é a de
SM-2:

> O Custo-por-Aprovação de cada braço agrupa o conjunto: o custo total de cada tentativa dividido
> pelo número total de aprovações. A razão divide o número do harness pelo do nu. Se qualquer um
> dos braços não aprovar nada, a razão é indefinida e o resultado é relatado apenas como resultado
> de taxa de aprovação.

### 7. Trajetórias e um comando que reproduz a execução

**O que é:** o que cada agente de fato fez, e uma forma de fazer de novo.

**Satisfeito por:** a transcrição de todo trial no conjunto de prova, trials falhos, com timeout e
de fallback incluídos, com credenciais e caminhos pessoais redigidos mas não encurtados. Um comando
declarado reexecuta todo o cronograma a partir do commit e manifesto fixados, e um rederiva todo
número publicado a partir das linhas sem chamar um modelo.

### 8. Concordância de juiz

**O que é:** evidência de que qualquer resultado julgado é julgado da forma que uma pessoa
julgaria.

**Satisfeito por:** para todo resultado decidido por um modelo ou uma pessoa em vez de uma
verificação determinística, o κ de Cohen contra rótulos manuais em uma amostra que o plano
dimensionou, a matriz de confusão, e auditorias de viés para posição ou ordem, extensão, identidade
de braço (o juiz não consegue dizer qual braço produziu a saída) e autopreferência (um juiz da
mesma família de modelo que um braço). Quando todo resultado é uma verificação determinística, como
são as verificações ocultas da reprodução, o item é marcado como não aplicável com esse motivo.

### 9. Uma verificação de contaminação

**O que é:** evidência de que nenhum dos braços conseguiu ver a resposta, e de que os dois braços
tinham o mesmo acesso.

**Satisfeito por:** um registro de que as soluções de referência eram inalcançáveis de dentro de um
trial (nenhum histórico posterior no checkout, nenhum caminho de rede para a solução), de que os
dois braços tinham acesso idêntico à web e à rede, e as datas das tarefas ao lado da data de corte
de treinamento declarada do modelo. SM-2 registra por que este item existe:

> As execuções de oito tarefas de 23 de setembro não foram pontuadas e rodaram com acesso à web
> desigual entre os braços, então não são um resultado.

### 10. Rótulos de estimando (estimand)

**O que é:** cada número diz qual efeito estima.

**Satisfeito por:** um rótulo em todo número publicado:

- **Intenção de tratar (intention to treat):** todo trial como atribuído, incluindo travamentos,
  timeouts e fallbacks. Este é o principal.
- **Adesão (adherence):** apenas trials em que o tratamento de fato aconteceu, como o mecanismo sob
  teste disparando. SM-4 governa o crédito: "Nenhuma economia é creditada a um mecanismo a menos
  que as linhas do ledger mostrem que ele disparou."
- **Efeito do cumpridor (complier effect):** o efeito entre trials onde o mecanismo dispararia,
  estimado a partir da atribuição em vez de selecionar esses trials depois do fato.
- **Hipotético:** qualquer número que é calculado em vez de medido, como um preço hipotético ou um
  subconjunto projetado, é marcado como hipotético onde aparece.

### 11. Verificações de campo

**O que é:** verificações que importam quando uma comparação roda em sessões reais em vez de uma
reprodução.

**Satisfeito por:**

- **Razão de amostra:** a contagem observada por braço é testada contra a divisão atribuída, e uma
  discrepância com p abaixo de 0,001 interrompe a análise até que seja explicada. Uma reprodução
  aplica isso a trials planejados contra completados por braço.
- **Novidade:** o efeito é relatado por período de exposição, para que um efeito precoce que
  desaparece seja visível.
- **CUPED:** quando uma covariável de pré-período é usada para reduzir variância, tanto o número
  ajustado quanto o bruto são relatados, e a covariável é nomeada no plano.
- **Diluição:** a fração de sessões que o tratamento não poderia ter afetado é relatada, com o
  efeito tanto através de todas as sessões quanto através das disparadas.

Um conjunto de prova só de reprodução marca novidade, CUPED e diluição como não aplicáveis, com
esse motivo.

### 12. O que não alegamos

**O que é:** uma seção no resultado publicado que nomeia as alegações que seus dados não sustentam.

**Satisfeito por:** uma seção cabeçalhada "O que não alegamos" que ao menos nomeia os modelos,
runtimes, tipos de tarefa e magnitudes que o resultado não cobre, todo mecanismo que não é
creditado, e o resultado da condição de parada de SM-2 quando ela se aplica. SM-2 limita a
magnitude:

> O resultado é publicado com seus intervalos, seja lá o que mostrar. Uma magnitude só é alegada na
> medida em que o intervalo a sustenta: "pelo menos 15% mais barato" precisa que o limite superior
> do intervalo esteja em 0,85 ou abaixo.

## Fontes

SM-2, SM-4 e NFR-15 nos requisitos de produto, e as fontes que SM-2 cita para Custo-por-Aprovação,
intervalos pareados e agrupados, o método delta e intervalos de taxa de aprovação para amostras
pequenas.
