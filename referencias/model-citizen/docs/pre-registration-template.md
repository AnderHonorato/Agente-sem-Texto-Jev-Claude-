# Modelo de pré-registro

Copie este arquivo para cada rodada de prova, preencha cada seção, e faça commit da cópia antes do
primeiro trial da rodada. Nomeie a cópia pela data e pela pergunta, por exemplo
`benchmarks/preregistrations/2026-10-01-harness-vs-bare.md`, e faça o merge do pull request dela
antes do primeiro trial, para que o horário de publicação do plano seja um que o GitHub registra,
em vez de uma data que você mesmo define. Este é o item 1 do [padrão de evidência](evidence-standard.md),
que diz como a ordem é verificada.

Substitua cada `<...>` por um valor. Uma seção que não se aplica diz "none" e o porquê; um espaço
em branco ou um `<...>` esquecido falha a verificação. Os valores do SM-2 são preenchidos como
padrão; mude um só registrando a mudança e o motivo aqui, antes do primeiro trial.

Depois do primeiro trial, as seções acima do registro de desvios ficam congeladas. Uma mudança
depois desse ponto é uma entrada anexada no registro de desvios, nunca uma edição acima dele.

---

## Rodada

- **Pergunta:** <uma frase: o que esta rodada decide>
- **Papel do autor:** <mantenedor, contribuidor>
- **Data de registro:** <YYYY-MM-DD>
- **Manifesto de tarefas:** `benchmarks/tasks.json` no commit `<sha>`
- **Braços:** <harness na tag ou commit, nu>
- **Modelo, CLI e esforço:** `<ID exato do modelo>`, `<versão da CLI>`, `<esforço>`

## Hipóteses

- **Primária:** o harness reduz o Custo-por-Aprovação (Cost-of-Pass) em relação ao nu, com uma
  razão esperada de 0,85, e não reduz a taxa de aprovação em mais que a margem de não-inferioridade
  δ.
- **Secundária:** <cada hipótese adicional, com sua direção, ou "none">
- **Exploratória:** <cada análise que será relatada mas não sustenta nenhuma alegação, ou "none">

## Métrica primária

- **Métrica:** razão de Custo-por-Aprovação, harness sobre nu, agrupada em todo o conjunto: o
  custo total de cada tentativa dividido pelo número total de aprovações, por braço.
- **Intervalo:** intervalo pareado de 95%, agrupado por tarefa, por <bootstrap pareado agrupado por
  tarefa com N reamostragens e semente S, ou o método delta>.
- **Caso indefinido:** se qualquer um dos braços não aprovar nada, o resultado é relatado apenas
  como resultado de taxa de aprovação.

## Salvaguardas (guardrails)

- **Taxa de aprovação:** margem de não-inferioridade δ = 0,125 na diferença pareada, agrupada por
  tarefa, da taxa de aprovação (harness menos nu).
- **Taxa de fallback:** <a fração de trials em um modelo não fixado acima da qual a rodada é
  relatada como comprometida>
- **Gasto:** <o orçamento por trial e o teto da rodada inteira>
- **Outra:** <cada métrica de salvaguarda adicional e seu limite, ou "none">

## Tamanho da amostra

- **Tarefas:** <k>, das quais <n> são tarefas longas de múltiplos turnos.
- **Trials por tarefa e braço:** <m>, cinco ou mais.
- **α e poder:** α 0,05 bicaudal, poder conjunto 0,8 nos dois testes da regra de decisão, assumindo
  uma razão verdadeira de 0,85 e taxas de aprovação iguais.
- **Poder da alegação:** <o poder conjunto, com este k, n e m, das três condições que uma alegação
  de economia exige: os dois testes da regra de decisão e a vitória do intervalo do subconjunto de
  tarefas longas. Dimensione para 0,8, ou declare o valor menor e o porquê.>
- **Efeito mínimo detectável:** <no máximo 15%>
- **Fonte de variância:** <as linhas piloto ou rodada anterior que a análise de poder usou, com sua
  correlação intra-cluster>
- **Cálculo de poder:** <o comando ou fórmula que produziu k, n e m para a regra de decisão e para
  a alegação, e sua saída>

## Regra de parada

- **Amostra fixa:** a rodada para quando toda tarefa tiver <m> trials por braço, e nenhum resultado
  é lido antes disso. <Ou: o design sequencial, seus pontos de checagem e sua função de gasto.>
- **Parada antecipada por dano ou custo:** <a condição, ou "none">
- **Condição de parada para a alegação:** uma alegação de economia exige a hipótese sustentada no
  conjunto inteiro e uma vitória no subconjunto de tarefas longas, sendo vitória o intervalo da
  razão do subconjunto ficar inteiramente abaixo de 1,0. Sem essa vitória, os achados do
  instrumento são publicados como o resultado.

## Multiplicidade

- **Regra de decisão:** as duas condições devem valer, então os dois testes formam um único teste
  conjunto e não precisam de correção.
- **Testes confirmatórios adicionais:** <cada um, com sua correção, como Holm sobre a família, ou
  "none">
- **Tudo mais:** exploratório, rotulado como tal, e não sustenta nenhuma alegação.

## Regra de decisão

A hipótese é sustentada apenas quando ambas as condições valem:

- o intervalo pareado de 95% agrupado por tarefa sobre a razão de Custo-por-Aprovação fica
  inteiramente abaixo de 1,0;
- o limite inferior do intervalo pareado de 95% agrupado por tarefa sobre a diferença de taxa de
  aprovação (harness menos nu) está acima de −δ.

O resultado é publicado com seus intervalos, seja qual for o que mostrar.

## Exclusões

- **População de análise:** todo trial atribuído, incluindo travamentos, timeouts e fallbacks.
- **Exclusões pré-declaradas:** <cada regra que remove um trial, decidida agora, ou "none">

## Registro de desvios

Anexe uma entrada datada para cada mudança depois do primeiro trial: o que mudou, por quê, e quais
números isso afeta. Nunca edite uma entrada.

- <YYYY-MM-DD: nenhuma ainda>
