# Spike: um aviso de orçamento durante a execução para um subagente em execução valeria seu peso?

**Status:** `failed` — não construir, 2026-09-22. Os números medidos não atenderam ao critério de
saída, e o critério não foi ajustado. Issue [#322](https://github.com/JakeSelby/agent-harness/issues/322).

## Pergunta

Um subagente aprende seu orçamento flexível em seu brief e não ouve mais nada depois disso. Um
aviso no meio da execução — uma linha nomeando o real contra o orçamento, sem negar nada — alcança
execuções acima do orçamento em número suficiente, e cedo o bastante nelas, para pagar pela
maquinaria que exige: um leitor incremental de transcrição em toda chamada de ferramenta de
subagente, que é a peça mais pesada do feed de uso?

## Experimento mais barato

A telemetria para responder isso já existe, então nada foi construído e nada foi rodado ao vivo.
Um script descartável leu duas coisas em uma máquina:

- `~/.local/state/agent-harness/usage.jsonl`, para toda linha `kind: "subagent"` que carrega
  `budget_output_tokens` — a amostra **registrada**, escrita pela 0.11.1 quando os briefs já
  carregavam orçamentos.
- As linhas de subagente anteriores do Claude Code do mesmo ledger, cujo papel é precificado em
  `primitives/stances/cost/balanced.json`, com o orçamento de hoje aplicado retroativamente — a
  amostra **reconstruída**. Essas execuções são anteriores a orçamentos no brief, então
  representam o comportamento sem nenhum sinal de orçamento.

Para cada linha o script reconstruiu a curva cumulativa de saída da execução a partir da própria
transcrição do agente sob `~/.claude/projects/<project>/<session>/subagents/`, um ponto por
mensagem de assistente, cada id de mensagem contado uma vez em seu maior `output_tokens`, na ordem
do arquivo, com a contagem cumulativa de uso de ferramenta ao lado. Onde um id de agente existia
sob dois diretórios de projeto, a transcrição mais completa foi usada; o total da curva de cada
linha então igualava exatamente o total do ledger, 89 de 89 e 235 de 235, o que é a verificação de
que o arquivo certo foi lido. A curva dá o que o ledger sozinho não consegue: o ponto de uma
execução onde um limite foi cruzado, e quanto de execução restava depois disso.

O que é simulado: nada foi avisado de fato, então toda cifra de "poderia ter economizado" é o
**teto**: os tokens emitidos depois do cruzamento, sob a suposição de que um agente avisado para
de imediato. Um aviso real economiza uma fração disso.

## Critério de saída

Fixado antes da varredura da curva, a partir da própria formulação da issue — o aviso precisa
valer um leitor incremental em toda chamada de ferramenta de subagente:

- ele dispara em **pelo menos 10%** das execuções de subagente com orçamento, e
- no cruzamento, a execução mediana que disparou ainda tem **pelo menos 10 chamadas de
  ferramenta** restantes, para que o aviso possa ser posto em prática, e
- a saída emitida depois do cruzamento é **pelo menos 10%** de todos os tokens de saída de
  subagente.

Dois dos três não foram atendidos.

## Máquina

Apple M5 Pro, 24 GB, macOS 26.5, arm64. Uma máquina de desenvolvedor, um ledger:
3.477 linhas, 3.085 delas subagentes, das quais 2.778 Claude Code. A janela com orçamento é de
2026-09-21 a 2026-09-23 no harness 0.11.1; a janela reconstruída é tudo antes disso. Todo número
abaixo é dessa máquina, e uma segunda máquina poderia diferir.

## Medido

Amostra registrada — 89 linhas de subagente cujo brief carregava um orçamento:

- 2 de 89 execuções (2,2%) terminaram acima de `budget_output_tokens`. As duas eram `builder`;
  nenhum outro papel excedeu uma única vez.
- A execução mediana terminou em 0,17 do seu orçamento; p75 0,32, p90 0,53, p95 0,87, máx 1,66.
- Excesso total nas duas execuções acima do orçamento: 118.056 tokens de saída, 4,5% dos
  2.594.799 tokens de saída que essas 89 execuções gastaram.
- Um aviso em 1,0× do orçamento teria disparado duas vezes em 89 execuções, cada vez com margem
  real — 19 e 67 chamadas de ferramenta restantes, a 18% do tempo de relógio da execução —
  endereçando no máximo 115.713 tokens.
- Um aviso em 0,8× teria disparado 6 vezes; 4 dessas 6 execuções terminaram abaixo do orçamento,
  uma taxa de falso alarme de dois para um. Teria endereçado no máximo 161.579 tokens nas
  execuções que de fato excederam.
- Chamadas de ferramenta não são um proxy utilizável para o mesmo sinal: 4 execuções de 89
  excederam `budget_tool_calls`, todas `builder`, e apenas 1 dessas 4 também excedeu seu
  orçamento de tokens.

Amostra reconstruída — 235 execuções anteriores, sem orçamento no brief, com o orçamento de hoje
aplicado:

- 51 de 235 (21,7%) terminaram acima do orçamento, e o excesso é de 714.033 tokens, 8,9% de
  8.026.505.
- Os excessos são marginais e distribuídos entre quatro papéis: `reviewer` 15, `gatherer` 14,
  `builder` 14, `spec-reviewer` 8, com as doze menores razões entre 1,00 e 1,07.
- **Este é o achado que decide tudo.** No cruzamento de 1,0×, a execução mediana que disparou
  tinha **1 chamada de ferramenta restante**; 23 de 51 não tinham nenhuma e 29 de 51 tinham duas
  ou menos. Em 0,8×, a execução mediana que disparou tinha 1 chamada restante e 41 de 92 disparos
  não tinham nenhuma. Um aviso entregue em uma chamada de ferramenta que o agente nunca faz não é
  entregue.
- A taxa de falso alarme de 0,8× tem o mesmo formato em escala: 41 de 92 disparos terminaram
  abaixo do orçamento.

Volume, para o lado do custo: 77.943 chamadas de ferramenta de subagente estão registradas nesta
máquina contra as 4.167 das 89 execuções com orçamento. O feed hoje roda em quatro eventos do fio
pai por spawn; um aviso no próprio `PostToolUse` do subagente roda em cada uma dessas chamadas.

## Onde um aviso teria que se apoiar

- **Não `SubagentStop`** — a execução já acabou, e o feed já relata o total ali.
- **O próprio `PostToolUse` do subagente** é o único evento dentro de um subagente em execução.
  Hooks de fato disparam dentro de um subagente: 22 registros de feedback de hook foram
  encontrados estruturalmente nas transcrições de subagente desta máquina, cada um deles um bloco
  `tool_result` em um registro `user` de sidechain, 18 de `PreToolUse` e 2 de `PostToolUse`. A
  documentação de hooks do runtime concorda, e acrescenta que o payload carrega `agent_id` e
  `agent_type` dentro de um subagente, que é a identificação de que uma trava "uma vez só" por
  agente precisa.
- `transcript_path` nesse payload é a transcrição **do pai**, não a do agente, então o aviso
  precisaria derivar o arquivo do agente da mesma forma que `usage-feed.py` já faz, a partir do id
  de sessão e do id de agente. O leitor incremental — offset salvo, inode e hash do primeiro
  registro, orçamentos de byte e de relógio — existe ali e seria reaproveitado em vez de
  reescrito. Então o harness *consegue* endereçar um subagente em execução; é o valor, não o
  mecanismo, que falha aqui.

## Veredito: não construir

Contra o critério: o aviso dispara em 2,2% das execuções com orçamento, não 10%; os tokens que
poderia endereçar são 4,5% da saída de subagente, não 10%. Só o teste de margem passa, e só numa
amostra de dois. A amostra reconstruída, uma ordem de grandeza maior, mostra por que essa margem
é sorte: quando papéis excedem sem orçamento no brief, excedem por poucos por cento bem no final
da execução, onde um aviso chega depois da última chamada de ferramenta.

A leitura mais barata dos mesmos dados é que o brief já fez o trabalho. Orçamentos nos briefs
coincidem com excessos caindo de 21,7% para 2,2% e a execução mediana pousando em 0,17 do
orçamento. O que resta é um papel, `builder`, excedendo um orçamento que pode simplesmente ser
pequeno demais para o trabalho que lhe é dado — uma questão de tabela de custo, respondida
mudando um número, não com um canal novo.

A chave `switches.nudge_at` permanece como está. Já é nula em `frugal`, vazia em `max`, e
`[1.0, 1.5]` em `balanced` para o feed de turno no fio pai; nada aqui a muda, e nenhum leitor do
lado do subagente é adicionado.

## O que mudaria isso

Rodar essa mesma varredura de novo — o ledger já registra orçamento e real em toda linha de
subagente, então custa um script e nenhuma instrumentação nova — e construir quando, sobre uma
janela de pelo menos 200 linhas de subagente com orçamento:

- as execuções acima do orçamento forem **10% ou mais** delas, e
- o excesso for **10% ou mais** dos tokens de saída de subagente, e
- no cruzamento de 1,0×, a execução mediana acima do orçamento ainda tiver **10 ou mais chamadas
  de ferramenta** restantes.

Qualquer uma dessas isoladamente não é suficiente: uma taxa de excesso alta descoberta sem margem
é a amostra reconstruída, e é o caso em que um aviso não pode ajudar. Um gatilho mais restrito
também mudaria a resposta: se os excessos ficarem concentrados em um papel, um aviso restrito a
esse papel é algo bem menor que um leitor em toda chamada de ferramenta de subagente, e deveria
ser investigado separadamente, só contra as linhas desse papel.
