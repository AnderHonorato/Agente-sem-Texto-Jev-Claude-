# Spike: o texto de regra condicionado a ação pode ser adiado para depois do hook que dispara na ação?

**Status:** `open` — formulado, não executado, 2026-09-22. Nada aqui é uma medição. Issue
[#430](https://github.com/JakeSelby/agent-harness/issues/430), mudança 1 de três; as mudanças 2 e 3
foram feitas sem ela.

## Pergunta

Sete arquivos sempre carregados só se ligam quando um ato específico é tentado: `secrets`,
`verification` e as variantes de postura `commits`, `licensing`, `testing`, `plan-ceremony` e
`build-vs-buy`. Medidos nesta branch, são 5.012 caracteres, uma estimativa de 1.253 tokens, 36% da
camada de regras e posturas de 3.524 tokens. O harness já adia dessa forma em outros lugares —
`grade-bash` e `brief-guard` entregam seu texto na chamada da ferramenta em vez de no início da
sessão — e a camada de regras ainda não adotou o padrão.

Mover esses sete arquivos da camada sempre carregada para a saída de um hook mantém o
comportamento que eles compram, ou uma regra que chega no momento do ato chega tarde demais para
mudar o plano que o produziu?

Esse é o risco real, e não é uma questão de tokens. `testing` e `plan-ceremony` moldam o trabalho
bem antes de qualquer chamada de ferramenta condicionada: um agente que aprende "os testes vão
junto com a mudança" no `git commit` já escreveu a mudança sem eles. `secrets`, `verification`,
`commits` e `licensing` estão mais próximos de um único ato detectável e são os candidatos
plausíveis.

## Experimento mais barato

Não construir o adiamento. Dois passos baratos, em ordem, e o primeiro sozinho pode matar a ideia:

1. **Rastrear cada um dos sete até um ato que um hook consiga enxergar.** Para cada linha
   operativa, nomeie o evento (`PreToolUse` em `Bash`, em `Write`, `UserPromptSubmit`, `Stop`) e o
   matcher que o dispararia, usando os detectores existentes em `policy/hooks/` — `rule-detectors.py`
   já reconhece formatos de commit, push, segredo em escrita e plan-card, então os matchers já
   existem em sua maioria. Uma linha sem ato, ou cujo ato vem depois da decisão que ela governa,
   não é adiável e permanece residente.
2. **Reproduzir o braço adiado contra o braço residente nas tarefas que exercitam essas regras.**
   `scripts/cost_bench.py replay` é o executor; o braço é um perfil cujo diretório de regras omite
   os arquivos adiados e cujos hooks os emitem. Pontue a conformidade com um oráculo que lê a
   transcrição, não o relato do próprio modelo: mensagens de commit contra Conventional Commits,
   uma tentativa de `--no-verify` ou force-push, um segredo escrito em um arquivo rastreado, uma
   mudança entregue sem teste.

## Critério de saída

Fixado antes de qualquer execução. Construir o adiamento somente quando as três condições valerem:

- **Ao menos 900 dos 1.253 tokens** são rastreados no passo 1 até um ato que um hook consiga
  enxergar antes da decisão que a regra governa, para que o ganho valha uma mudança de
  arquitetura.
- **A conformidade não cai**: em pelo menos 20 execuções pareadas de tarefas, a contagem de
  aprovações do oráculo do braço adiado não é menor que a do braço residente menos um — a mesma
  barra que `benchmarks/history.jsonl` já usa para custo.
- **O prefixo ao vivo medido cai em pelo menos 700 tokens**, lido do `cache_creation_input_tokens`
  do primeiro turno do assistente em uma transcrição pareada, não de `benchmarks/static.json`.

Se qualquer uma faltar, é um registro `failed` e os sete arquivos ficam onde estão. Uma aprovação
parcial — digamos, `secrets` e `commits` rastreáveis mas `testing` não — é um spike mais restrito
contra esses arquivos apenas, não uma licença para adiar os sete.

## O que NÃO foi executado

Tudo. Nenhum rastreamento foi feito, nenhum braço foi construído, nenhuma reprodução foi lançada,
nenhuma transcrição foi pareada. Os números de token acima são a estimativa estática de contagem
de caracteres para esta branch e nada mais; `benchmarks/static.json` conta arquivos, então não
consegue responder à questão de conformidade nem à do prefixo ao vivo. A próxima sessão começa no
passo 1, que custa uma leitura cuidadosa de sete arquivos e nenhum gasto de modelo.

## Máquina

Ainda não aplicável. Quando o passo 2 rodar, registre a máquina, a versão da CLI, o modelo e o
dia, porque os valores em dólares da reprodução só são comparáveis dentro de um desses.
