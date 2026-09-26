# <O que será construído — um sintagma nominal, não uma frase>

> **Veredito.** <O que isto constrói, uma frase.> <O mecanismo, uma frase.>
> **Esforço** <n> · **Risco** <baixo/médio/alto — a única razão> · **Raio de impacto** <o que pode quebrar>

## Em resumo

- **Resultado** — O que é verdade quando isto está pronto
- **Abordagem** — O mecanismo em uma linha
- **Toca** — Repositórios, superfícies, número de arquivos
- **Novas dependências** — Nome + licença, ou Nenhuma
- **Fora de escopo** — As 2–3 coisas que um leitor assumiria estarem incluídas
- **Teste de saída** — Como sabemos que funcionou
- **Questão em aberto** — A única coisa ainda não resolvida, apontando para seu número de decisão

## Design do sistema

```text
Fonte ── o que se move ──▶ *Transformação ──▶ Destino
```

<Uma linha de legenda. `*` = novo ou alterado.>

## Passos

1. **<A coisa mais barata que poderia invalidar o resto>** — [file.ts](src/file.ts).
   *Exit:* `pnpm test x` passa.
2. **[<Passo com detalhe>](#step-2--title)** — <o que ele toca>.
   *Exit:* <um comando, um render, ou uma asserção que passa>.

## Decisões para o revisor

> **1. <Pergunta, declarada de forma que possa ser respondida por número.>**
> *Recomendo* <opção> — <a razão, uma oração>.
> *Alternativa* <opção> — <seu caso honesto>.

## Riscos

- **<Gatilho>** — <o que fazemos quando ele dispara>.

---

# Adendo

Tudo que o agente implementador precisa e o revisor não precisa. Nada acima da régua é repetido
aqui.

## Passo 2 — <titulo>

## Contexto e background

## Evidência e verificação

## Adiado, e por quê
