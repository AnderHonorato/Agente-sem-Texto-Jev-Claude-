---
name: code-quality-instruments
description: Measure whether a test suite is any good, not only that it passes: branch coverage, mutation score, complexity-times-coverage risk, duplication. Use when adding or reviewing tests on a change that matters, a suite passes but a bug still shipped, coverage is high and confidence is not, or before promising a module is well tested. (Meça se uma suíte de testes é boa, não só se ela passa: cobertura de branch, pontuação de mutação, risco de complexidade-vezes-cobertura, duplicação. Use ao adicionar ou revisar testes numa mudança que importa, quando uma suíte passa mas um bug ainda foi lançado, a cobertura é alta e a confiança não, ou antes de prometer que um módulo está bem testado.)
---

A postura (stance) `testing` diz se testes são obrigatórios. Isto é como você descobre se os que
você escreveu valem alguma coisa.

Uma suíte pode alcançar cobertura de linha total sem nenhuma asserção. Toda linha executa, nada é
verificado, e o gate fica verde. Cobertura mede o que rodou; ela não mede o que foi verificado. Tudo
abaixo existe para fechar essa lacuna.

## O que medir, em ordem do que revela

1. **Cobertura de branch, não cobertura de linha.** Cobertura de linha conta um branch de dois
   caminhos como coberto quando um lado rodou. Cobertura de branch é o upgrade mais barato
   disponível e geralmente o que revela o caminho de erro não testado.
2. **Pontuação de mutação.** Mude um operador, inverta um limite, apague uma instrução, depois rode
   a suíte de novo. Um mutante que sobrevive é uma mudança no seu código à qual nenhum teste se
   opõe. Este é o único instrumento aqui que mede asserções em vez de execução, então é o que
   captura uma suíte sem asserções.
3. **Complexidade contra cobertura.** Uma função que é tanto ramificada quanto pouco coberta é onde
   os defeitos se concentram. Qualquer um dos números sozinho é fraco; o par ranqueia o trabalho. A
   fórmula CRAP de Robert Martin é uma forma publicada de combiná-los, e qualquer relatório de
   complexidade unido a um relatório de cobertura te dá o mesmo ranking.
4. **Duplicação.** Um sinal de refatoração, nunca um gate. Lógica duplicada significa que uma
   correção pousa em uma cópia. Não reprove um build por causa disso, e não deixe uma ferramenta te
   convencer de uma abstração ruim.

## Instrumentos por linguagem

Verifique cada um contra a postura (stance) `licensing` com a skill `licensing-review` antes de
adotá-lo. Estes rodam no CI em vez de serem entregues dentro do produto, e a postura
permissive-commercial ainda não abre exceção para ferramental.

| Linguagem | Cobertura de branch | Mutação | Duplicação |
| --- | --- | --- | --- |
| Python | `coverage.py` com `branch = true`, geralmente via `pytest-cov` | `mutmut`, ou `cosmic-ray` para uma árvore maior | `pylint --enable=duplicate-code`, ou `jscpd` |
| TypeScript | `vitest --coverage` ou `jest --coverage`, com limiar de `branches` definido | Stryker Mutator | `jscpd` |
| Rust | `cargo-llvm-cov` | `cargo-mutants` | nenhuma ferramenta padrão que valha a pena adotar |
| Go | `go test -covermode=atomic -coverprofile` | `go-mutesting` | `dupl` |

Leia a própria documentação da ferramenta em busca de flags antes da primeira execução. Uma flag
desatualizada numa skill é pior que nenhuma flag, e elas mudam.

## Como rodá-los

- **Diferencialmente, contra o que mudou.** Mutar uma árvore inteira a cada mudança compra um
  número que ninguém lê e um loop que ninguém espera. Mute o diff. Reserve uma execução completa
  para um lançamento ou um job agendado.
- **Um de cada vez.** Execuções de cobertura, mutação e duplicação todas geram processos de teste.
  Rode-as concorrentemente e elas disputam a mesma CPU, as mesmas portas e as mesmas fixtures, e os
  números ficam ruidosos de um jeito que parece instabilidade (flakiness).
- **Workers limitados.** Passe um limite explícito de workers em vez de deixar uma ferramenta tomar
  todo núcleo, ou um comando não relacionado na mesma sessão vai dar timeout.
- **Relate progresso em execuções longas.** Uma execução de mutação sobre um módulo grande é
  indistinguível de uma travada sem saída periódica, e uma execução morta não ensina nada.

## O que fazer com os números

- **Um mutante sobrevivente é uma asserção faltando**, então escreva a asserção. Não é motivo para
  apagar o mutante ou adicioná-lo a uma lista de ignorados.
- **Separe o testável do vinculado ao ambiente.** Código que abre uma janela, fala com um
  dispositivo, ou precisa de rede não é um assunto justo para estes instrumentos. Empurre a lógica
  para fora dele até que a fronteira não testável fique fina, depois meça apenas a parte que pode
  ser medida, e diga qual parte é essa.
- **Não defina um limiar de cobertura como a meta.** Um limiar é um piso que impede regressão.
  Perseguir um número produz testes que executam código e não afirmam nada, que é exatamente a
  falha que o teste de mutação existe para encontrar.
- **Registre a linha de base** nas instruções de agente do repositório na primeira vez que você
  rodar um instrumento, do mesmo jeito que os gates de verificação registram sua saída esperada de
  árvore limpa, para que um movimento posterior seja atribuível.
