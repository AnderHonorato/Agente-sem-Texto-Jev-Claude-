# Pego em flagrante

Duas funcionalidades foram lançadas aqui e não fizeram a coisa que seu lançamento supunha. Nenhuma
delas foi encontrada lendo o código. Uma foi encontrada por um benchmark de custo que conta
chamadas de ferramenta, a outra pela telemetria de regras em [usage.md](usage.md), e nos dois
casos o código estava fazendo exatamente o que dizia.

## Uma postura medida como nunca disparando

**O que foi lançado.** A postura `delegation` diz a uma sessão para reunir informações com
subagentes sem esperar ser solicitada, e é onde o harness reivindica sua economia de custo:
trabalho retirado do fio da conversa, não contexto aparado do início dele. É contexto sempre
carregado em toda sessão que a seleciona.

**O que o instrumento mediu.** Zero. Em 19 execuções headless do benchmark de reprodução — o
primeiro conjunto ao vivo mais duas sondagens posteriores — não houve chamadas de ferramenta
`Agent` em nenhum dos braços. Em `hook-inventory`, a tarefa fixa de ler e resumir muitos arquivos
que é o caso que a postura nomeia por descrição, o braço com harness leu os 18 arquivos sozinho em
10 chamadas de API contra as 11 do braço nu. A postura foi carregada, resolvida e nunca posta em
ação.

**Reproduzindo.** A reprodução chama um modelo e gasta uso real, então é rodada manualmente:

```sh
python3 scripts/cost_bench.py replay --model <id> --raw /tmp/replay-raw   # 7 tarefas x 2 braços x 2 repetições
grep -o '"name": *"Agent"' /tmp/replay-raw/*.json | wc -l                 # spawns, ambos os braços
```

O campo `turns` por execução em `benchmarks/<harness version>/results.jsonl` é a contagem de
chamadas de API de onde vem o número 10 contra 11. Veja [benchmarks.md](benchmarks.md) para o que
os braços compartilham e o que a reprodução simula.

**O que foi feito a respeito.** Nada na postura ainda, o que é a parte honesta.
[#429](https://github.com/JakeSelby/agent-harness/issues/429) está aberta e enquadra a medição
como uma pergunta com duas respostas em vez de como um defeito: ou a postura não se liga sob
`claude -p`, ou as quatro tarefas fixas são pequenas demais para que a delegação valha a pena, e um
agente que recusa delegar numa tarefa de 11 chamadas está correto. A issue fecha com um par de
execuções mostrando um spawn e seu efeito no custo, ou com um achado registrado de que recusar é
correto nesse tamanho, mais o tamanho a partir do qual deveria disparar. Um benchmark que não
consegue separar essas duas coisas é a primeira coisa a corrigir.

**Sem o instrumento.** Uma postura que nunca dispara lê exatamente como uma postura que dispara e
ajuda: a prosa está no contexto, as execuções passam, as tarefas são feitas. Perceber teria exigido
abrir a transcrição de cada execução e procurar nela por um spawn que nunca esteve lá.

## Um hook cuja métrica não se moveu

**O que foi lançado.** `brief-guard`, um hook `PreToolUse` que anexa um limite de retorno a todo
brief de subagente, apoiado pela linha de regra de `delegation` que diz para limitar o brief.

**O que o instrumento mediu.** O detector `transcript-hygiene/brief-without-cap` disparou na mesma
taxa antes, durante e depois de o hook existir: **3,2 acertos a cada 100 turnos antes, 3,6
durante, 3,2 depois**, no ledger de uma única máquina.

**Reproduzindo.** Os acertos vêm do ledger local, e uma nova varredura os reconstrói a partir das
transcrições:

```sh
bin/harness usage --rescan --days 30 --rules   # preenchimento retroativo, depois acertos por detector
bin/harness usage --rules --by stance          # o mesmo, por dimensão=variante
```

O detector é hoje `transcript-hygiene/model-wrote-no-cap`; `--rules` dobra o id antigo no novo
enquanto lê, então a série não se divide na renomeação.

**O que foi feito a respeito.** A causa foi estabelecida a partir de uma transcrição registrada, e
não era nenhuma das duas hipóteses em [#324](https://github.com/JakeSelby/agent-harness/issues/324).
O hook estava registrado e disparando. O Claude Code registra a entrada de uma chamada de
ferramenta como o modelo a escreveu, e o `updatedInput` de um hook `PreToolUse` cai em uma entrada
separada que a varredura do ledger nunca lê — então limitar um brief não poderia mover um número
derivado do texto pré-hook, seja lá o que o hook fizesse. A métrica foi renomeada para dizer o que
mede: `model-wrote-no-cap` conta briefs que o hook depois limitou, e um acerto é a omissão do
orquestrador, não um brief sem limite chegando a um subagente. Isso faz a flag `promote?` do
relatório voltar a significar algo. `rule-detectors.RENAMED` dobra o id antigo no momento da
leitura, o arquivo do ledger não é reescrito, e `tests/test_brief_cap_metric.py` fixa o
comportamento. Medir o brief entregue ainda é possível a partir das entradas do hook, mas isso
exige que a varredura do ledger leia a saída do hook, o que é uma mudança de ledger e não de
detector.

**Sem o instrumento.** O hook funcionava. Nada deu erro, nenhum teste falhou, e todo brief saiu
limitado. O único sintoma visível era um número que deveria ter caído e não caiu, o que só existe
porque o número já vinha sendo mantido antes do lançamento do hook.

## O que o instrumento ainda não consegue mostrar

- **A validade do detector é medida para dezenove detectores de dezenove, contra um corpus
  sintético.** O wheel vendorizado `ruleprobe` rotula os detectores que o motor distribui e
  `tests/fixtures/detector-corpus/` rotula os escritos para as próprias regras deste repositório, e
  o job `corpus` roda `scripts/detector_corpus.py --floor 0.9` sobre ambos em todo pull request
  ([#522](https://github.com/JakeSelby/agent-harness/issues/522)). O que isso compra é um detector
  medido contra o que seu autor diz que ele deveria encontrar; `secrets/git-add-secret-file` e
  `autonomy/denied-by-grade` estão registrados abaixo do piso em p=0,83 em vez de o piso ser
  deslocado para atendê-los. Uma taxa sobre sessões reais ainda é uma taxa de comportamento só na
  medida em que o corpus se pareça com elas.
- **As taxas por variante são observacionais.** `--rules --by stance` agrupa sessões pela variante
  que por acaso foi selecionada, escolhida por uma pessoa por razões que o ledger não registra. Diz
  o que foi visto sob uma variante, nunca o que a variante causou.
- **Regras que optaram por sair ficam no escuro.** Uma regra sem nada que uma transcrição consiga
  decidir opta por sair pelo nome, e essas regras não têm taxa de acerto nenhuma — ausência ali é
  silêncio, não conformidade.
