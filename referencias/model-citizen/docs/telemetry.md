# Exportando o ledger

O ledger de uso é um arquivo JSONL local e isso é deliberado: é escrito antes de qualquer coisa
ser enviada a qualquer lugar, sobrevive a um backend estar fora do ar, e pode ser relido. A
exportação é uma cópia dele, para dashboards, SQL e uma visão de equipe. Está **desligada por
padrão**; com ela desligada, nenhum código de rede roda e o hook se comporta exatamente como se
comportava antes de isso existir.

**O modelo, em uma linha: o ledger é o registro, um backend é uma cópia reconstruível dele.** A
maioria dos backends expira dados por padrão — o endpoint de referência contra o qual isso foi
testado distribui um TTL de 30 dias — então o histórico fora da janela de retenção vive no ledger
e é devolvido por reprodução.

O que é registrado, e de onde vem, está em [usage.md](usage.md).

## Ligando

```json
{
  "telemetry": {
    "export": "otlp",
    "endpoint": "http://localhost:4318",
    "headers_env": "HARNESS_OTLP_HEADERS",
    "headers_file": "~/.config/agent-harness/otlp-headers",
    "labels": { "deployment.environment": "laptop" }
  }
}
```

- `export` é `off` ou `otlp`. Qualquer outro valor para `citizen sync` em vez de silenciosamente
  não exportar nada.
- `endpoint` é a URL base de **qualquer endpoint OTLP/HTTP**; `/v1/logs` é anexado. Nenhum
  fornecedor é exigido e nenhum é nomeado no código.
- `labels` são atributos adicionados a todo registro — o lugar para um ambiente ou um nome de
  host.
- `native` pede a um runtime para exportar **sua própria** telemetria para o mesmo endpoint.
  `true` é todo runtime, `false` é nenhum, e uma lista — `["claude-code"]`, `["codex"]` — nomeia
  aqueles aos quais se aplica; qualquer outro nome de runtime para `citizen sync` com os nomes que
  conhece. Desligado por padrão, e uma decisão separada de `export`: veja
  [Repasse nativo](#native-pass-through) antes de ligá-lo, porque os runtimes anexam
  identificadores que o ledger não anexa, e porque só o Claude Code consegue alcançar um endpoint
  que exige um cabeçalho.

`citizen doctor` imprime uma linha para isso: o modo, o esquema e o host do endpoint, e os
**nomes** dos cabeçalhos que resolveu.

## O switch do log de decisões

Mais uma chave vive no mesmo bloco e não envia nada a lugar nenhum:

```json
{ "telemetry": { "decisions": false } }
```

`decisions` governa `~/.local/state/agent-harness/decisions.jsonl`, o registro local do que cada
hook decidiu e como se resolveu — [usage.md](usage.md#the-decision-log) descreve as linhas e o
relatório. O padrão é **ligado**, como o ledger de uso ao lado, porque um rótulo só vale a pena
ter a partir do dia em que o hook começa a escrevê-lo; defina como `false` e nenhuma linha, nenhum
arquivo e nenhum diretório é escrito. Não faz parte de `export`: linhas de decisão nunca são
enviadas a um endpoint, seja qual for o valor de `export`, e ligar a exportação não liga nem
desliga isto.

Ao contrário de uma linha de ledger, uma linha de decisão guarda o texto que o hook julgou — um
comando, ou o início de um brief — limitado a 2 KiB, que é a única razão para desligá-lo em uma
máquina compartilhada.

## A amostra de comando permitido

```json
{ "telemetry": { "allow_sample_rate": 0 } }
```

`allow_sample_rate` é o um-em-quantos: **20 por padrão**, então um comando distinto em vinte
daqueles que o harness permite é escrito no log de decisões como um negativo não classificado, e
`0` não escreve nenhum deles. [usage.md](usage.md#sampled-allows) descreve a linha, e por que a
amostra é de comandos distintos em vez de invocações.

Está ligada porque as linhas classificadas são todas prompts, e uma verificação que só pode
transformar um allow em um ask não pode ser medida quanto a falsos alarmes contra prompts
sozinhos. A amostra é tirada do próprio hash de cada comando em vez de um sorteio aleatório, então
os mesmos comandos são amostrados em toda máquina e uma medição sobre essas linhas é reproduzível.
Só um allow que o próprio harness deu é amostrado, nunca um comando que deixou para o runtime
responder. O texto de uma linha amostrada é redigido primeiro — valores de atribuição, flags de
credencial, todo formato de segredo que os detectores de regra combinam e o diretório home como
`~` — porque é texto sobre o qual ninguém foi perguntado, e o hash da linha é sobre o texto
redigido para que nada removido dele possa ser recuperado; uma linha classificada ainda guarda o
comando como o usuário o viu.

Defina como `0` em uma máquina onde um log de comandos que ninguém aprovou é indesejável.
`decisions: false` o desliga junto com o resto do log, e nada aqui é exportado: uma linha de
decisão não alcança nenhum endpoint, seja qual for o valor de `export`.

## O switch de alegação de conclusão

```json
{ "telemetry": { "completion_claim": true } }
```

Este tem **desligado** como padrão. Ele adiciona `completion_claim` a uma linha de decisão de
`stop-gate`: os últimos 2 KiB da mensagem final de assistente do turno, lidos da transcrição no
Stop, com o hash sobre a mensagem sem limite — ou uma alegação nula ao lado do motivo de não haver
nenhuma. [usage.md](usage.md#the-completion-claim) descreve os campos e as razões. É o que permite
que uma alegação de parada seja lida contra o resultado do gate sentado na mesma linha.

Está desligado porque é o único lugar onde o log de decisões guarda prosa de assistente, e isso é
algo diferente de manter em uma máquina compartilhada de um log de comandos. `decisions: false`
também o desliga, já que não há linha para colocá-lo. Nada aqui também é exportado: uma linha de
decisão não alcança nenhum endpoint, seja qual for o valor de `export`.

## Credenciais

Cabeçalhos são lidos da variável de ambiente nomeada ou do arquivo nomeado e de nenhum outro
lugar. Um valor de cabeçalho escrito em `config.json` é recusado pelo nome, porque um arquivo de
configuração é feito backup, sincronizado e lido por toda ferramenta que lê a configuração.

```sh
export HARNESS_OTLP_HEADERS='authorization=<token>,x-scope-orgid=<tenant>'
```

As duas formas são aceitas, na variável e no arquivo: `name=value` por linha, ou a lista
separada por vírgula `name=value` que `OTEL_EXPORTER_OTLP_HEADERS` usa.

Um `headers_file` é recusado, com o motivo, quando está **dentro de uma work tree do git** — um
`git add -A` de distância de ser publicado — ou quando é **legível por outros usuários**. Crie-o
no modo 600 fora de todo repositório:

```sh
install -m 600 /dev/null ~/.config/agent-harness/otlp-headers
```

Nenhum valor de cabeçalho é jamais impresso, registrado em log ou escrito em um registro de erro.
Um registro de falha nomeia só o esquema e o host do endpoint, já que um caminho ou uma string de
consulta podem por si só carregar um token.

## O que é enviado

Um registro de log OTLP por linha de ledger, `POST <endpoint>/v1/logs`,
`Content-Type: application/json`, usando só a biblioteca padrão. Logs em vez de métricas: uma
linha é um resumo posterior ao fato que carrega seus próprios timestamps.

- `timeUnixNano` é o `ended` da linha, `observedTimeUnixNano` é o momento em que foi enviada.
  Ambos são **strings** decimais, como o mapeamento OTLP/JSON exige de um inteiro de 64 bits —
  então um atributo inteiro viaja como `{"intValue": "200"}`, não como um número JSON.
- O **corpo (body)** é a linha como uma string JSON, então nada se perde na tradução — tudo que o
  ledger guarda exceto o mapa `stances`, que viaja como atributos em vez disso. Um backend que
  analisa um corpo JSON achata um mapa aninhado em chaves com pontos próprias; um corpo carregando
  `stances` aterrissaria uma segunda cópia de toda postura ao lado dos atributos abaixo.
- **Atributos** são os campos escalares planos da linha — um nulo é omitido em vez de enviado como
  vazio — mais `harness.row_key`, `harness.exported_at`, `harness.version`, `harness.usd` e
  `harness.price_as_of` em uma linha precificada, um `harness.<dimension>` por postura registrada,
  e quaisquer labels configurados. Uma postura é exportada **uma vez**. Um mapa aninhado (`days`,
  `by_model`, `rules`, `counts`) fica no corpo: conjuntos de atributos são planos, e cem fatias
  por dia seriam cem colunas.
- Uma **linha `kind: "decision"`** — uma chamada de provedor de decisão, veja [usage](usage.md) —
  carrega seus próprios campos sob `harness.decision.*`, seu preço incluído como
  `harness.decision.usd`. Ela mede o que o harness gastou perguntando uma pergunta em vez do que
  uma sessão gastou, e exportada crua seu `input`, `output` e `usd` cairiam nas mesmas colunas que
  os de uma sessão, onde qualquer coisa que os some contaria a pergunta como gasto de sessão.
- Atributos de recurso são `service.name=agent-harness` e a versão do harness.

`harness.row_key` é a identidade da linha — id de sessão, runtime, tipo, id de agente — e é
estável através de reproduções. É o que um leitor usa para deduplicar. `harness.exported_at` é o
momento em que o registro foi enviado, como uma string RFC 3339 UTC de largura fixa — seis dígitos
fracionários, sempre `Z` — para que um backend que guarda atributos como strings ainda ordene dois
registros para uma chave corretamente. É a única diferença entre um registro e sua reprodução, e
as linhas de um lote podem compartilhar um carimbo.

### O número em dólar

`harness.usd` é um double e `harness.price_as_of` é a data `as_of` mais nova entre as entradas de
preço com que essa linha foi precificada. Ambos vêm de `policy/prices.json` e das suas próprias
sobrescritas de `prices`, através do mesmo código com que `citizen usage` precifica —
`policy/hooks/pricing.py`, que a CLI e o hook cada um carrega em vez de um dos dois reimplementá-lo.

- **Um equivalente de preço de tabela de API, fixado no momento da exportação.** É o que os tokens
  custariam nas taxas publicadas na data carimbada ao lado deles — não uma fatura, e não o que uma
  assinatura cobrou. Uma reprodução depois de uma mudança de preço recarimba os dois atributos nas
  novas taxas, então leia o registro mais novo por chave em vez de uma média entre reproduções.
- **Uma linha não precificada não carrega nenhum dos dois atributos** — nunca um zero. Uma linha
  com um modelo desconhecido, uma sessão que trocou de modelo sem detalhamento `by_model`, ou uma
  linha `partial` não é precificada por ninguém, e um zero diria que foi de graça.
- **O número de uma sessão do Claude Code já inclui seus subagentes**, exatamente como
  `citizen usage` a relata: os tokens dos subagentes são precificados em seus próprios modelos e
  somados aos da sessão pai. Suas linhas também são exportadas precificadas, para relatório por
  papel, então **nunca some uma linha de sessão e suas linhas de subagente** — filtre por `kind`
  primeiro. Uma linha de subagente do Codex e uma linha de worker de role-run são cada uma
  precificada sozinha, porque nenhuma linha de sessão guarda seus tokens.
- Precificação nunca custa nada à exportação: um arquivo de preço ausente ou uma sobrescrita
  malformada deixa a linha exportada sem dólares e não muda nem o status de saída do hook nem o
  da sessão.

## Onde roda, e o que um endpoint morto custa

A exportação acontece no **worker desacoplado** que o hook `SessionEnd` gera, depois que a linha
já está no ledger. Uma tentativa, um timeout de dois segundos, sem nova tentativa. Um coletor que
está fora do ar, lento ou mal configurado custa uma linha em
`~/.local/state/agent-harness/usage.errors.jsonl` — o horário, a classe de erro, a contagem de
linhas e o host do endpoint — e não muda nem o status de saída do hook nem o da sessão.

## Reprodução

```sh
bin/harness usage export --since 2026-09-01                    # tudo desde esse dia
bin/harness usage export --since 2026-09-01 --until 2026-09-07 # uma semana
bin/harness usage export --since 2026-09-01 --dry-run          # conta, não conecta a nada
```

Linhas são reenviadas em lotes; o comando imprime quantas foram enviadas e quantas falharam, e
sai com código não-zero se qualquer lote falhar. Falhas ficam no arquivo de erros e a mesma janela
pode ser rodada de novo. É assim que um backend é preenchido retroativamente depois de criado,
reconstruído depois de perdido, e reparado depois de uma queda — a capacidade que um fluxo de
telemetria de runtime ao vivo não tem.

## Repasse nativo

O ledger é uma linha por sessão, escrita depois do fato. Cada runtime também pode exportar sua
própria telemetria ao vivo — o Claude Code conta tokens por tipo e relata um número em dólar por
chamada de API; o Codex conta tokens, custo de turno, chamadas de ferramenta e chamadas de API.
`"native": true` faz `citizen sync` escrever essa configuração, apontando os dois runtimes para o
mesmo `endpoint`. Está desligado por padrão e ligá-lo é uma decisão que exige ler os dois avisos
abaixo primeiro.

```json
{ "telemetry": { "export": "otlp", "endpoint": "http://localhost:4318",
                 "headers_file": "~/.config/agent-harness/otlp-headers", "native": true } }
```

### Quais runtimes conseguem alcançar um endpoint autenticado

**O Claude Code consegue; o Codex não consegue.** O Claude Code resolve seus cabeçalhos rodando o
script `otelHeadersHelper` em tempo de execução, então um coletor que exige um cabeçalho
`authorization` — o ClickStack recebe um sem prefixo — é alcançável sem nenhuma credencial em
nenhum arquivo. O Codex recebe valores de cabeçalho em `config.toml` só como literais e não
oferece indireção de ambiente ou comando para eles, então o harness não escreve nenhum; sua
exportação nativa precisa de um endpoint que aceite esta máquina sem autenticação, e contra um
coletor que autentica, toda sessão do Codex é rejeitada.

Nomeie os runtimes que o endpoint de fato consegue servir:

```json
{ "telemetry": { "export": "otlp", "endpoint": "https://collector.example:4318",
                 "headers_file": "~/.config/agent-harness/otlp-headers",
                 "native": ["claude-code"] } }
```

`sync` então deixa a tabela `[otel]` do Codex exatamente como a encontrou — restaurando o que
havia antes se uma sincronização anterior escreveu uma — e `["codex"]` da mesma forma deixa
`~/.claude/settings.json` intocado. `true` ainda significa ambos, que é o que um coletor local não
autenticado quer.

**Leia isto antes de apontá-lo para um endpoint hospedado.** Os dois runtimes anexam
identificadores que a exportação do ledger nunca envia. O Claude Code coloca `user.email`,
`user.account_uuid`, `user.account_id`, `user.id`, `organization.id` e `session.id` em seus
datapoints; seus próprios switches removem alguns deles —
`OTEL_METRICS_INCLUDE_ACCOUNT_UUID` e `OTEL_METRICS_INCLUDE_SESSION_ID` têm ambos `true` como
padrão, `OTEL_METRICS_INCLUDE_VERSION`, `OTEL_METRICS_INCLUDE_ENTRYPOINT` e
`OTEL_METRICS_INCLUDE_REPOSITORY` têm `false`. O harness não define nenhum deles, então adicionar
um a `env` você mesmo é seu para manter: `sync` possui as seis variáveis abaixo e nenhuma outra. O
registro de prompt e resposta fica no padrão de cada runtime, que é desligado.

### O que `sync` escreve

**Claude Code**, em `env` em `~/.claude/settings.json`: `CLAUDE_CODE_ENABLE_TELEMETRY=1`,
`OTEL_METRICS_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`,
`OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`, `OTEL_EXPORTER_OTLP_ENDPOINT` definido para a URL
base, e `OTEL_RESOURCE_ATTRIBUTES` carregando `harness.version` e um `harness.<dimension>` por
postura resolvida, mais os `labels` configurados. Com uma fonte de cabeçalho configurada, também
define `otelHeadersHelper` para `~/.claude/hooks/harness/otel-headers.py`, que lê o mesmo arquivo
ou variável que o exportador lê e imprime um objeto JSON de cabeçalhos; o runtime o roda de novo
a cada 29 minutos aproximadamente. Nenhum valor de cabeçalho é escrito no arquivo de
configurações. Uma variável só alcança o helper se alcançou o runtime que o gerou, então
`headers_file` é a fonte que funciona para um cliente lançado a partir do desktop.

**Codex**, em `[otel]` em `~/.codex/config.toml`: `exporter` e `metrics_exporter`, ambos
`otlp-http` com `protocol = "binary"` e as URLs específicas de sinal `<endpoint>/v1/logs` e
`<endpoint>/v1/metrics`. Os dois são definidos de propósito. `metrics_exporter` tem como padrão o
próprio destino nativo do Codex, e sua fonte mantém uma lista exata de nomes de métricas que esse
destino descarta do lado do cliente — uso de token, custo de turno, chamadas de ferramenta,
chamadas de API — sob o comentário *"Métricas intencionalmente não enviadas através da rota
Statsig embutida do Codex. Mantenha isto como uma lista exata de nomes para que exportadores OTLP
personalizados ainda as recebam."* Definir só `exporter`, portanto, não envia nenhuma métrica de
token a lugar nenhum.

**O Codex não recebe cabeçalhos nem labels, e isso é uma lacuna real.** `[otel]` recebe um mapa de
cabeçalho literal em `config.toml` e não oferece indireção de ambiente ou comando para ele, então
escrever um colocaria uma credencial em um arquivo de configuração — exatamente o que as regras
acima recusam. A exportação nativa do Codex precisa de um endpoint que aceite tráfego não
autenticado desta máquina, ou um por trás de algo em que o usuário se autentique. Também não há
nenhuma chave de configuração para labels de métrica: o Codex constrói seu recurso com o
construtor padrão do SDK, então `OTEL_RESOURCE_ATTRIBUTES` do ambiente de processo é honrado, mas
`sync` não consegue colocá-lo ali, e um Codex lançado de um desktop ou editor pode não herdar
nenhum ambiente de shell. *Não verificado:* as duas afirmações vêm da referência de configuração e
de uma leitura de fonte, não de uma execução.

### Labels são congelados no momento da sincronização

Eles são calculados quando `sync` roda, não por sessão. Troque uma postura sem sincronizar de novo
e o fluxo nativo fica rotulado com a variante antiga até a próxima `sync` — **a linha do ledger
continua certa**, porque ela registra as posturas sob as quais a sessão de fato rodou.
`citizen doctor` diz se os labels escritos combinam com a versão e posturas atuais. Um label cujo
nome ou valor carrega uma vírgula, um sinal de igual ou espaço em branco não consegue viajar em
`OTEL_RESOURCE_ATTRIBUTES`, que não tem nenhum escape em que os runtimes concordem: fica de fora
dos labels nativos, nomeado na saída de `sync` e `doctor`, e ainda enviado com a exportação do
ledger.

### O que posse significa aqui

`sync` registra toda chave que escreve, para poder atualizá-la e retirá-la.

- **Uma variável que você define nunca é tocada.** A posse é por variável, não sobre `env`.
- **Uma chave gerenciada que já guarda algo que o harness não escreveu é deixada intacta e
  relatada**, em `sync` e em `doctor`. Remova-a para deixar `sync` gerenciá-la. Uma chave que já
  guarda exatamente o que o harness escreveria é assumida, já que não há nada a perder.
- **`"native": false` devolve o que cada chave guardava antes**, e remove o resto. Um `"env": {}`
  vazio pode permanecer onde o harness criou o mapa; é inerte. Retirar um runtime da lista é a
  mesma operação só para esse runtime e deixa o outro no lugar.
- `citizen sync --dry-run` imprime as linhas de repasse só quando a chave está ligada.

## Deduplicando um fluxo de pelo menos uma vez

Uma reprodução reenvia linhas que o backend já pode conter, então leia o registro mais novo por
chave em vez de contar linhas. Ordene por `harness.exported_at` e nada mais: o tempo observado do
OTLP é **descartado na ingestão** pelo exportador do ClickHouse, e `Timestamp` é o próprio `ended`
da linha, que é idêntico entre reproduções. Em um schema estilo ClickHouse, onde atributos de log
OTLP caem em um mapa `LogAttributes`:

```sql
SELECT
    LogAttributes['harness.row_key']                                  AS row_key,
    argMax(Body, LogAttributes['harness.exported_at'])                AS row,
    argMax(toFloat64OrNull(LogAttributes['harness.usd']),
           LogAttributes['harness.exported_at'])                      AS usd
FROM otel_logs
WHERE ServiceName = 'agent-harness'
  AND Timestamp >= now() - INTERVAL 30 DAY
  AND NOT (LogAttributes['kind'] = 'subagent' AND LogAttributes['runtime'] != 'codex')
GROUP BY row_key
```

`LogAttributes` é um `Map(String, String)`, então todo atributo lido dele é texto: o `argMax`
acima compara os carimbos de exportação lexicalmente, o que é exatamente por que são de largura
fixa, e `harness.usd` precisa de `toFloat64OrNull` antes de poder ser somado — uma linha não
precificada não tem essa chave, e a string vazia que ela produz vira um nulo em vez de um zero.

A mesma forma funciona em qualquer lugar: agrupe por `harness.row_key`, mantenha o registro com o
maior tempo de exportação. Como uma reprodução carrega a linha como ela está no ledger **agora**,
a cópia mais nova também é a corrigida quando um `--rescan` a melhorou desde então — e o
`harness.usd` mais novo é o precificado nas taxas em vigor quando foi enviado pela última vez.

O filtro `kind` é a outra metade de não contar em dobro: os dólares de uma sessão do Claude Code
já contêm os de seus subagentes, então um total sobre toda linha os cobraria duas vezes. Um
subagente do Codex é ao contrário — seus tokens não estão em nenhuma linha além da própria — que
é por que o filtro também nomeia o runtime. Esta é a regra que `citizen usage` aplica;
[usage.md](usage.md) diz por quê. Gasto por papel é a mesma consulta restrita às linhas de
subagente e worker em vez disso.

## Receita de referência: ClickStack

`endpoint` recebe **qualquer** endpoint OTLP/HTTP. Este é um backend que foi configurado e medido
de ponta a ponta, escrito para que a primeira pessoa a apontar o exportador para algo real não
tenha que redescobrir os passos de configuração. É um exemplo, não um requisito e não um endosso:
qualquer coisa que fale OTLP/HTTP funciona, e nada no harness nomeia um fornecedor.

ClickStack é o stack de observabilidade do ClickHouse — uma interface HyperDX sobre o ClickHouse,
alimentada por um OpenTelemetry Collector. A imagem tudo-em-um roda os três em um container, que
é por que serve bem para um laptop.

### Rode-o

```bash
docker run -d --name clickstack -p 8080:8080 -p 4317:4317 -p 4318:4318 -v clickstack-db:/data/db -v clickstack-ch:/var/lib/clickhouse -v clickstack-chlogs:/var/log/clickhouse-server clickhouse/clickstack-all-in-one
```

8080 é a interface e a API HTTP, 4317 é OTLP/gRPC e 4318 é OTLP/HTTP — a porta para a qual o
`endpoint` acima aponta. Os três volumes são todo o estado: `/data/db` é o MongoDB que guarda o
usuário, a equipe e a chave de ingestão, e os outros dois são os dados e logs do ClickHouse. **Os
volumes são o que persiste**, não o container: depois de um `docker restart`, e de novo depois
que o container foi removido e um novo foi rodado nos mesmos três volumes, os dados continuavam
intactos e a mesma chave de ingestão ainda era aceita, porque a conta e a chave vivem em
`/data/db`. Sem eles, um container recriado começa vazio e a chave é regenerada. Medido ocioso em
um laptop: cerca de 795 MiB residentes, cerca de 1,5 GiB pouco depois da ingestão.

Esta receita deliberadamente não contém nenhum comando que crie uma conta, escreva uma senha, ou
remova um container ou volume. O primeiro é um passo de navegador, o segundo pertence a um arquivo
que só você consegue ler, e o terceiro é destrutivo e seu para digitar.

### Dois passos manuais antes de qualquer dado ser aceito

**Primeiro, crie o primeiro usuário** na interface em `http://localhost:8080`. Os receptores OTLP
em 4317 e 4318 ficam fechados até que essa conta exista, porque o coletor está esperando sua
configuração vinda do aplicativo. Até então, um exportador vê uma conexão que se recusa a falar, e
nada no registro de erro do harness vai explicar o porquê.

**Segundo, envie a chave de ingestão da equipe** — mostrada na interface sob as configurações de
equipe — como um cabeçalho `authorization` simples em toda requisição. É a chave sozinha, sem
prefixo `Bearer`. Sem ela, o receptor responde:

```text
401 missing or empty authorization header: Authorization
```

Então `headers_file` não é opcional para este backend. Um arquivo em modo 600 fora de todo
repositório serve as duas direções da integração: o exportador do ledger o lê como
`headers_file`, e com `"native": true` o script `otelHeadersHelper` lê o mesmo arquivo para o
Claude Code.

```bash
printf 'authorization=%s\n' '<ingestion-key>' > ~/.config/agent-harness/otlp-headers
```

Crie o arquivo em modo 600 primeiro, como em [Credenciais](#credentials); o redirecionamento de
shell acima não muda o modo de um arquivo existente.

**O Codex não consegue usar este backend através de `sync`.** `[otel]` recebe valores de
cabeçalho só como literais em `config.toml`, então não há forma de dar ao Codex a chave sem
escrevê-la em um arquivo de configuração — veja [Repasse nativo](#native-pass-through), que
declara essa lacuna e o que ela custa. Defina `"native": ["claude-code"]` para que `sync` não
escreva nenhuma tabela `[otel]` do Codex contra um backend que rejeitaria toda requisição que ele
faz. A exportação nativa do Claude Code não é afetada, e o exportador do ledger também não.

A exportação nativa do Claude Code também carrega `user.email`, os ids de conta e organização e o
id de sessão em todo datapoint. Em um container vinculado ao localhost, isso é sua própria máquina
falando consigo mesma; leia o aviso sob [Repasse nativo](#native-pass-through) antes de apontar a
mesma configuração para algo hospedado.

### A retenção é de 30 dias por padrão

Toda tabela do OpenTelemetry que o coletor cria vem com seu próprio TTL de 30 dias. Dez tabelas
carregavam um na imagem medida: as tabelas de logs e traces, as cinco tabelas de métricas, os dois
rollups `*_kv_rollup_15m` e `hyperdx_sessions`. Isso é o argumento de ledger-como-registro
concretizado: o backend esquece, e `citizen usage export --since <date>` devolve a janela.

Liste o que de fato está lá, com o TTL que cada tabela carrega, em vez de confiar em uma lista em
um documento:

```sql
SELECT name, engine FROM system.tables WHERE database = 'default' AND create_table_query LIKE '%TTL%' ORDER BY name
```

Depois eleve cada uma com que se importa. A expressão de TTL nomeia a própria coluna de tempo
daquela tabela — as tabelas de log e trace usam `Timestamp`, as tabelas de métrica usam
`TimeUnix` — então copie a expressão do próprio `create_table_query` da tabela e mude só o
intervalo:

```sql
ALTER TABLE default.otel_logs MODIFY TTL toDateTime(Timestamp) + toIntervalDay(365)
```

Um `MODIFY TTL` em uma tabela que já guarda dados agenda uma materialização; não ressuscita
partes que já expiraram.

### O painel

[`telemetry/clickstack-dashboard-native-cost.json`](telemetry/clickstack-dashboard-native-cost.json)
é dez tiles de SQL bruto sobre `otel_metrics_sum`, lendo as métricas nativas de custo e token do
Claude Code: gasto, sessões, a fração de gasto de subagente, taxa de acerto de cache, gasto ao
longo do tempo por modelo e por versão do harness, gasto por agente × modelo × esforço, gasto por
variante de custo e postura de delegação, tokens por tipo, e as sessões mais caras. O SQL é
próprio deste repositório, sobre as tabelas padrão do OpenTelemetry; nenhum painel, consulta ou
documentação é copiado do projeto upstream.

A API HTTP responde sob `/api/api/v2/` na porta da **interface**, não na porta OTLP — o `api`
duplicado não é um erro de digitação. Envie `/api/v2/...` em vez disso e o proxy remove um `/api`,
deixando o backend responder `404 Cannot GET /v2/dashboards`.

**A chave de API e a chave de ingestão são dois segredos diferentes.** A chave de ingestão é
enviada como um cabeçalho `authorization` simples para as portas OTLP; a API HTTP recebe uma
*chave de API pessoal*, criada separadamente na interface, como
`Authorization: Bearer <key>` na porta da interface. Nenhuma funciona no lugar da outra. Mantenha
a chave de API em seu próprio arquivo modo 600 fora de todo repositório e a leia dentro do
argumento de cabeçalho em vez de exportá-la para o ambiente.

Cada tile carrega um `connectionId`, que é específico da instância e vem como o placeholder
`REPLACE_WITH_CONNECTION_ID`. Procure o seu:

```bash
curl -s http://localhost:8080/api/api/v2/connections -H "Authorization: Bearer $(cat ~/.config/agent-harness/clickstack-api-key)"
```

Substitua-o, mantendo o arquivo original intacto:

```bash
sed 's/REPLACE_WITH_CONNECTION_ID/<connection-id>/g' docs/telemetry/clickstack-dashboard-native-cost.json > "$HOME/clickstack-dashboard.json"
```

Faça um dry-run antes de criar qualquer coisa; uma definição boa volta como
`{"valid": true, "errors": [], "normalized": …}`:

```bash
curl -s -X POST http://localhost:8080/api/api/v2/dashboards/validate -H "Authorization: Bearer $(cat ~/.config/agent-harness/clickstack-api-key)" -H 'content-type: application/json' --data-binary "@$HOME/clickstack-dashboard.json"
```

Depois crie-o:

```bash
curl -s -X POST http://localhost:8080/api/api/v2/dashboards -H "Authorization: Bearer $(cat ~/.config/agent-harness/clickstack-api-key)" -H 'content-type: application/json' --data-binary "@$HOME/clickstack-dashboard.json"
```

### Licenças, e o que este repositório distribui

O aplicativo HyperDX é MIT. O ClickHouse e o OpenTelemetry Collector são Apache-2.0. A imagem
tudo-em-um também contém o MongoDB, que está sob a SSPL — uma licença sob a qual este projeto não
distribuiria nada, e não precisa, porque você baixa a imagem do seu publicador. Este repositório
não distribui nada dela, não a empacota, e não copia nenhum de seus painéis ou documentação. Leia
os próprios termos da imagem antes de rodá-la em qualquer lugar além da sua própria máquina.
