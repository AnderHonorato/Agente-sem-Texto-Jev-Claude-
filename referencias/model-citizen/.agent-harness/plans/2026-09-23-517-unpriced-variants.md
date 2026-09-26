# Variantes de modelo não listadas ficam sem preço, não herdam

> `price_key` torna-se uma busca exata, depois que `normalise_model` aprende a
> remover um sufixo de release — um carimbo de data, `-v1:0`, `@date`. Um id que a
> tabela de preços não lista resolve para `None`, nunca para a taxa de sua família.
> Esforço meio dia · Risco baixo · Raio de impacto só `policy/`.

## Em resumo

- **Resultado** — uma variante não listada fica sem preço, não é cobrada na taxa de uma irmã.
- **Abordagem** — remover o sufixo de release, depois combinar chaves de tabela exatamente.
- **Toca** — `pricing.py`, `prices.json`, `docs/usage.md`, os testes de preço.
- **Novas dependências** — nenhuma; `re` da stdlib, já importado por `pricing.py`.
- **Fora de escopo** — uma coluna de custo corrigido, pesquisa de preços, reescrita de ledger.
- **Teste de saída** — 3443 linhas reais do ledger têm o mesmo preço em centavos depois.
- **Pergunta em aberto** — decisão 1: combinação exata, ou uma flag `prefix` declarada.

## Design do sistema

```text
ledger id ──▶ *normalise_model ──▶ *price_key
                                      │    │
        usd ◀── rate ◀── in table ────┘    │
        unpriced footer ◀── None ◀─────────┘
```
`*` marca o que muda; uma linha sem preço também derruba `harness.usd` no OTLP.

## Passos

1. **Estender `normalise_model`** — `pricing.py:77-93`, remover um sufixo de release.
   *Saída:* `normalise_model("claude-opus-5-20260401") == "claude-opus-5"`.
2. **Tornar `price_key` uma busca** — `pricing.py:111-120`, descartar a varredura de prefixo.
   *Saída:* `price_for(T, "gpt-5.5-pro")` é `None`; `"gpt-5.5"` continua 5.0.
3. **Reproduzir o ledger antes e depois** — script descartável, não commitado.
   *Saída:* 0 de 3443 linhas mudam `(usd, as_of)`; contagem sem preço e total iguais.
4. **Reescrever `_limitations`** — `prices.json:25-33`, cláusula de herança fora.
   *Saída:* `grep -c inherits policy/prices.json` retorna 0.
5. **Reescrever o marcador de resolução** — `docs/usage.md:412-418`.
   *Saída:* `grep -c "longest prefix" docs/usage.md` retorna 0.
6. **Adicionar e ajustar testes** — `tests/test_usage_prices.py`, cinco casos abaixo.
   *Saída:* `bin/harness lint` e `python3 -m unittest discover -s tests` verdes.

## Decisões para o revisor

**1. Combinação exata após normalização, ou uma flag `prefix` por entrada?**
*Recomendação* exata — um sufixo de release é uma grafia, e `normalise_model`
já é dona das grafias; uma flag reabre a brecha em toda entrada que a define.
*Alternativa* a flag, que é literalmente o que a aceitação da #517 nomeia.

**2. O que pode seguir um id listado e ainda ser o mesmo modelo?**
*Recomendação* só um sufixo de release: `-20260401`, `-2026-04-01`, `@20260401`,
`-v1:0`. Qualquer outra coisa, inclusive uma palavra à direita, é um modelo diferente.
*Alternativa* permitir também uma palavra à direita — que é o caso `-pro` que fechamos.

**3. A remoção mora em `normalise_model`, ou em um helper `price_key`?**
*Recomendação* `normalise_model` — uma única noção de "mesmo modelo" para o preço e
para o join pai/subagente, verificado para não mudar nenhuma linha do ledger.
*Alternativa* um helper privado: raio de impacto menor, duas noções para manter alinhadas.

## Riscos

- **Um formato de id que não antecipamos** cai fora da gramática e fica
  sem preço — a direção segura, mas observe a contagem do rodapé após o lançamento.
- **Um snapshot de mesmo preço com sufixo de palavra** (`gpt-5.6-terra-high`) precisa
  ser listado antes de ter preço; uma entrada na tabela ou um override em `config.json`.
- **`normalise_model` também alimenta o join pai/filho de `row_model`**, então mais
  ids agora comparam iguais; rode de novo a reprodução do passo 3 imediatamente antes do merge.

---

# Anexo

Os fatos abaixo foram reverificados em `main` `d4cf311` (0.12.0), não o `d884cff`
nomeado no brief; os números de linha são desse checkout.

## Passo 1 — Estender `normalise_model`

`pricing.py:77-93` deixa tudo minúsculo, descarta um sufixo `[...]`, pega o último segmento após
`/`, depois descasca prefixos alfabéticos `<vendor>.`. Seu docstring termina com "the
remainder is matched by prefix, so a dated id still reaches its family"
(`pricing.py:83-84`) — essa frase é o comportamento sendo removido e precisa
ser reescrita no mesmo commit.

Adicione, aplicado repetidamente até o nome parar de encolher:

```python
RELEASE = re.compile(
    r"(?:[-@](?:20\d{6}|20\d{2}-\d{2}-\d{2})"
    r"|-v\d+(?::\d+)?)$")
```

O laço importa: `anthropic.claude-haiku-4-5-20251001-v1:0` precisa que `-v1:0`
saia antes de a data ficar no final. O ramo de data é ancorado em "20" para que
`claude-opus-4-8`, `claude-fable-5-1` e `gpt-5.6-luna` fiquem intocados.

Verificado contra as quatro grafias afirmadas pelo teste existente
`test_a_bedrock_id_and_a_long_context_suffix_reach_the_same_entry`
(`tests/test_usage_prices.py:106-110`), e contra
`test_a_dated_id_resolves_to_its_family` e
`test_the_longest_prefix_wins_over_a_shorter_one`. Todos passam sem mudança.

## Passo 2 — `price_key` torna-se uma busca

```python
def price_key(table, model):
    name = normalise_model(model)
    return name if name in table else ""
```

Assinatura e contrato inalterados: uma chave, ou `""`. `price_for`
(`pricing.py:123-126`) e `row_as_of` (`pricing.py:330`) já tratam
`""`, e `bin/harness:3711-3726` não reexporta `price_key`, então nenhuma linha
de CLI muda.

### Questão de design 2 — todo id de fábrica ainda tem preço

Todas as doze chaves em `prices.json:34-101` já são sua própria forma
normalizada, então cada uma é um acerto exato sem edição de tabela. Verificado rodando
o normalizador proposto sobre cada chave:

- **claude-fable-5-1, claude-fable-5, claude-opus-5** — exato, inalterado.
- **claude-opus-4-8, claude-opus-4-6, claude-sonnet-5** — exato, inalterado.
- **claude-haiku-4-5** — exato; `claude-haiku-4-5-20251001` e
  `anthropic.claude-haiku-4-5-20251001-v1:0` o alcançam via a remoção de release.
- **gpt-6-astra, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, gpt-5.5** — exato;
  o `.` em um id `gpt-5.x` sobrevive porque `gpt-5` não é alfabético e
  o laço de prefixo de fornecedor em `pricing.py:88-92` para ali.

`test_every_key_is_already_normalised` (`tests/test_usage_prices.py:81-86`)
é a guarda permanente disso e passa sem mudança.

### Alternativa da questão de design 1 — o formato de prefixo declarado

Se a decisão 1 for para o outro lado, uma entrada carrega a flag e `price_key`
mantém uma varredura de prefixo restrita a chaves marcadas:

```json
"gpt-5.5": {
  "matches_prefix": true,
  "input": 5.0, "output": 30.0,
  "cache_read": 0.5, "cache_write": 0.0,
  "as_of": "2026-09-21",
  "source": "https://developers.openai.com/..."
}
```

Para manter ids datados com preço, as doze entradas precisariam da flag — o que restaura
a herança em todo lugar, `gpt-5.5` incluído. Essa entrada é o próprio exemplo
seis vezes maior da issue (`prices.json:27-29`), então a flag reabriria exatamente o
defeito que foi adicionada para fechar. Por isso a recomendação vai no sentido contrário.

## Passo 3 — Migração, e como foi verificada

**Nenhuma linha existente do ledger muda de preço.** Verificado em vez de argumentado: o
módulo de fábrica e uma cópia com o patch foram carregados lado a lado e
`priced(rows, table)` rodado sobre cada linha de
`~/.local/state/agent-harness/usage.jsonl`.

- **3443 linhas lidas**, 15 ids distintos entre `models`, `model`, `by_model`.
- **0 linhas** mudaram `(usd, as_of)`.
- **Sem preço: 329 antes, 329 depois.**
- **Total 26050.116679 USD antes e depois**, no float completo.

Os 15 ids são as sete famílias Claude, quatro ids `gpt`, os dois apelidos
`opus` e `fable` (sem preço antes e depois), `<synthetic>`, e as grafias datada
e Bedrock do Haiku. Nada no ledger resolve por um prefixo que não seja
também uma chave exata uma vez removido o sufixo de release.

Rode de novo essa reprodução no worktree de implementação antes do merge — o ledger
continua crescendo, e uma variante recém-registrada é exatamente o que mudaria.

## Questão de design 3 — o que uma variante não listada produz

Tome `gpt-5.5-pro`: hoje com preço em 5.0/30.0 do `gpt-5.5` contra um real
30/180, o caso seis vezes maior.

- **Valor da linha** — `price_for` retorna `None`, `row_cost` retorna `None`
  (`pricing.py:271-272`), `priced` produz `(None, "")` (`pricing.py:349`).
  Nunca `0.0`, que é a disciplina declarada em `pricing.py:15-16`.
- **Rodapé de `harness usage`** — a linha entra na contagem de
  `unpriced: N run(s), unknown model or partial tokens` em
  `bin/harness:4048`, e em `bin/harness:3841` para a tabela de papéis. O texto
  não muda; só N se move.
- **Coluna de dólares** — não contribui com nada, como uma linha `partial` faz hoje.
- **Atributo OTLP** — `telemetry.py:351-355` omite tanto `harness.usd` quanto
  `harness.price_as_of` quando `usd` é `None`. Nenhum zero é jamais exportado.
- **Formato `--json`** — não há nenhum para mudar. `harness usage` não tem
  flag `--json` (`bin/harness:4381-4397`); sua única superfície legível por máquina
  é a exportação OTLP acima. Diga isso no PR em vez de inventar uma.

## Passo 4 — `_limitations`

`prices.json:25-33`. As linhas 26-29 carregam a cláusula a apagar, com o exemplo
de `gpt-5.5-pro` incluído. Substituição, mesma voz, mesmos três pontos:

- um id de modelo resolve por combinação exata após a normalização, que deixa tudo
  minúsculo, remove um prefixo de provedor de nuvem, um sufixo de janela de contexto e um
  sufixo de release;
- uma variante que o arquivo não nomeia fica sem preço, nunca cobrada na taxa de uma
  irmã — um número subestimado é pior que um ausente;
- para dar preço a uma, adicione uma entrada aqui ou sobreponha-a sob `prices` em
  `config.json`, que mescla campo por campo (`pricing.py:56-74`).

Mantenha o parágrafo de contexto longo em `prices.json:30-32`; ele continua verdadeiro.

## Passo 5 — `docs/usage.md`

Reescreva o marcador **Ids resolve by longest prefix** em `docs/usage.md:412-418`,
cabeçalho incluído. Sua frase de fechamento — "The cost of prefix matching is that
an unlisted variant of a listed family inherits the family's rate even when it
is priced differently" — é a afirmação que se inverte.

O marcador **Unpriced is not free** em `docs/usage.md:444-448` já declara
a disciplina e ganha uma cláusula: uma variante não listada de uma família listada
agora entra no caso de apelido (`opus`, `fable`) que já nomeia.

## Passo 6 — Testes

Todos em `tests/test_usage_prices.py`, contra o `TABLE` inventado nas linhas
37-45, a menos que um caso diga o contrário.

1. **Uma variante premium não listada fica sem preço** —
   `price_for(TABLE, "test-model-pro")` é `None`.
2. **Uma entrada declarada ainda tem preço através de um sufixo de release** — estenda
   `test_a_bedrock_id_and_a_long_context_suffix_reach_the_same_entry` com
   `test-model@20260921` e `test-model-2026-09-21`.
3. **Um id exato vence uma irmã mais curta** — renomeie
   `test_the_longest_prefix_wins_over_a_shorter_one` (linha 103) para dizer o que
   ela agora prova: `test-model-mini-20260921` alcança `test-model-mini`.
4. **O rodapé conta a linha sem preço** — conduza `cmd_usage` através do
   helper `loud()` (linhas 56-64) com uma linha `gpt-5.5-pro` e verifique
   `unpriced: 1 run(s)` na saída capturada.
5. **Regressão para o caso seis vezes maior** — contra a tabela de fábrica,
   `price_for(load_prices({}), "gpt-5.5-pro")` é `None`, nomeado para a #517, para que
   uma futura regra de prefixo não restaure silenciosamente 5.0 onde o provedor
   cobra 30.0.

Gate, de `CLAUDE.md:21-26`:

```sh
python3 bin/harness lint
python3 -m unittest discover -s tests
```

## Questão de design 7 — texto de vitrine (landing copy)

`AGENTS.md:64-70`: o check `landing-copy` reprova um pull request que
muda `policy/` sem tocar `product.json`, a menos que o corpo carregue uma linha
`Landing copy:`. Isso corrige um número que o relatório já imprime e
não adiciona nenhuma capacidade, então nenhuma edição de `product.json`. Linha exata para o
corpo do PR:

```text
Landing copy: none — this corrects a rate the report
already printed and adds no capability; product.json
says what the harness does, not which prices it knows.
```

## Changelog e vaga de lançamento

Uma entrada `### Fixed` sob Unreleased, nomeando a mudança de comportamento, para que um
leitor acompanhando um número mês a mês saiba por que uma linha ficou em branco. Alocado
para a v0.13.0 pelo intake
(`roadmap-intake-enterprise-review-2026-09-22.md:141`), que também a registra
como explicitamente não um bloqueador da 0.12 — "the behaviour is documented, the caveat
is stated, and no shipped price row exercises it today" (linha 70).
