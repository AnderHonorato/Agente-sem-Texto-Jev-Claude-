# <nome do projeto>

Um parágrafo: o que é este repositório, para quem ele é, e o único fato arquitetural que um
agente não pode violar. Ligue o corpus de design, se ele viver em outro lugar.

As regras globais de agente são carregadas a partir do harness do usuário; **não as repita aqui —
apenas linke-as.** Este arquivo carrega apenas o que é verdadeiro sobre este repositório.

## Comandos

```sh
<instalação>          # ex.: pnpm install
<gate de qualidade>   # o comando exato que o CI roda; os agentes rodam isso na HEAD antes de todo push
<teste>               # o loop local rápido
<execução>            # inicia a aplicação
```

**Saída esperada em árvore limpa** do gate de qualidade em um checkout não modificado, para que
uma falha seja atribuível: `<cole a linha final, ex.: "All checks passed!", e a contagem de testes>`.

## Gate

```sh
<gate de qualidade>   # ex.: ruff check .
<teste>               # a suíte rápida, não a execução de integração completa
```

O hook `stop-gate` roda este bloco quando a árvore mudou desde sua última execução bem-sucedida,
bloqueia o turno enquanto ele estiver vermelho, e libera após oito bloqueios consecutivos.

## Convenções

- As versões de toolchain e framework estão fixadas em `<arquivo>`; atualize no cronograma
  deste projeto.
- Trabalhe em um worktree ramificado a partir de `main`, nunca no checkout compartilhado (veja a
  skill `worktree-per-agent`), a menos que este repositório diga o contrário aqui.
- `decisions.md` é apenas para acréscimo (append-only); em um conflito de merge, mantenha os
  dois lados em ordem de data.
- Arquivos de índice gerados são reconstruídos uma vez no merge, nunca nos dois lados.
- O trabalho de uma feature termina com o checklist de pré-PR abaixo, não com "pronto".

## Checklist de pré-PR

- Gate de qualidade verde na `HEAD` neste checkout.
- Todo arquivo no diff remonta à issue ou história declarada.
- Nenhum rodapé de framework de planejamento, referência a ticket interno ou nota de contexto
  privado no código entregue.
- Documentação atualizada no mesmo PR quando o comportamento mudou.

## Regras com escopo de caminho

Regras que se aplicam apenas a alguns arquivos vivem em `.claude/rules/<topic>.md` com um glob
`paths:` no frontmatter, para que carreguem apenas quando esses arquivos forem tocados. Mantenha
este arquivo curto.

## `AGENTS.md` e `CLAUDE.md` são um único arquivo

`CLAUDE.md` é um link simbólico para este arquivo (`ln -s AGENTS.md CLAUDE.md`), para que todo
agente leia as mesmas instruções. Edite `AGENTS.md`.
