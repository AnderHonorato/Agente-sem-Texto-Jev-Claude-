---
name: worktree-per-agent
description: Isolate an agent's work in its own git worktree branched off the default branch, so two agents never land conflicting changes on the shared checkout. Use at the start of any implementation task in a repo where others may also be working, and whenever a repo's instructions say "work in a worktree". (Isole o trabalho de um agente em sua própria worktree git ramificada do branch padrão, para que dois agentes nunca finalizem mudanças conflitantes no checkout compartilhado. Use no início de qualquer tarefa de implementação num repositório onde outros também podem estar trabalhando, e sempre que as instruções de um repositório dizem "trabalhe numa worktree".)
---

# Uma worktree por agente

O checkout compartilhado pertence ao humano. Um agente que o edita diretamente entra em corrida
com todo outro agente e toda mudança humana não commitada. Então: crie um branch numa worktree a
partir do branch padrão, trabalhe ali, finalize o resultado pelo caminho normal do repositório,
remova a worktree.

## Criar

```bash
REPO=$(git rev-parse --show-toplevel)
NAME=<task-slug>
DEST=$(citizen worktree create "$NAME" "$REPO")
cd "$DEST"
```

A raiz dedicada mantém checkouts de tarefa temporários separados de clones permanentes. Por
padrão é `~/worktrees/<repo>/<task>`; `HARNESS_WORKTREE_ROOT` pode substituir `~/worktrees`. O
helper faz fetch de `origin` e cria o branch a partir de `origin/main`, então começa a partir do
que está realmente mesclado. Se as instruções do repositório nomeiam uma base diferente, passe
`--base`; se nomeiam uma localização diferente, siga-as. Nunca crie uma worktree de tarefa como
irmã sob o diretório que guarda os repositórios permanentes.

## Trabalhar

- Instale dependências na worktree se o repositório precisar delas por checkout; não presuma que
  o `node_modules` ou virtualenv do checkout compartilhado é alcançável.
- Rode o gate de qualidade do repositório na worktree antes de dar push, conforme
  `verification.md`.
- Nunca dê `cd` de volta para o checkout compartilhado para rodar algo "rapidinho".

## Finalizar

Dê push no branch e abra um PR, ou dê push no `main` se as instruções do repositório permitirem.
Depois:

```bash
citizen worktree remove "$NAME" "$REPO" --merged
```

`--merged` também apaga o branch local, e apenas uma vez que o `gh` relata um pull request
mesclado cujo commit de topo é a ponta do branch. Um repositório que faz squash-merge deixa os
commits próprios do branch fora do branch padrão, então `git branch -d` recusa trabalho que de
fato foi mesclado; essa prova é o check em vez disso. Omita `--merged` para manter o branch. A
remoção não conta caches regeneráveis como `__pycache__` que uma execução de gate escreveu, e
ainda recusa qualquer outra entrada modificada, não rastreada ou ignorada; `--also-clear <name>`
adiciona um diretório de nível superior regenerável que a lista embutida não cobre.

## Coisas que mordem

- **Ferramental que resolve caminhos contra o diretório de trabalho** (frameworks de
  planejamento, projeções de skill) não vai encontrar seus arquivos numa worktree. Se uma
  ferramenta para com um erro de script faltando, essa é a proteção funcionando; rode aquela
  ferramenta apenas a partir do checkout compartilhado.
- **Documentos compartilhados de apenas-anexação** (um log de decisões, um changelog) não são
  material de worktree: dois agentes anexando em duas worktrees produzem um conflito na
  mesclagem. Anexe a esses no branch padrão, em um só lugar.
- **Arquivos de índice gerados** são reconstruídos uma vez na mesclagem, nunca nos dois lados.
- **Worktrees deixadas para trás** confundem `git status` e reescritas de histórico. `git
  worktree list` antes de qualquer operação que toque todo branch. `citizen worktree audit
  "$REPO"` relata checkouts sujos e obsoletos; um checkout limpo ainda pode conter commits não
  publicados, então audite o histórico de branch antes da remoção.
