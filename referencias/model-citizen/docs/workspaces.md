# Workspaces

Esta página descreve o adaptador de workspace/session-store do Claude Code. Ela não mescla o
histórico nativo ou a memória do Codex. Use a [continuação compartilhada de tarefa](task-continuation.md)
para levar trabalho entre runtimes.

Nada no harness precisa ser a raiz de um workspace. Tudo se instala em nível de usuário e carrega
em toda sessão. Esta página trata de workspaces multi-raiz do VS Code em geral, porque o Claude
Code baseia duas coisas na **primeira** pasta do workspace.

## O que a primeira pasta decide

- A **configuração em nível de projeto** (`.claude/settings.json`, `.claude/skills/`, `CLAUDE.md`)
  carrega a partir da primeira pasta. Pastas seguintes só contribuem com `.claude/skills/`,
  `.claude/commands/` e `.claude/agents/`.
- O **histórico de sessão e a memória automática** são indexados pelo caminho da primeira pasta
  sob `~/.claude/projects/`.

Portanto, escolha como primeira o repositório cuja configuração de projeto você quer, e nunca
reordene as pastas de um workspace de forma casual: o armazenamento de sessão pareceria ter
desaparecido.

## Um armazenamento por workspace

`citizen workspace create <name> <folder…>` grava `<name>.code-workspace` com as pastas na ordem
dada (a primeira é a raiz) e o checkout do harness anexado como uma pasta não-raiz, a menos que
`--no-harness` seja usado. Em seguida cria `~/.claude/workspaces/<name>/` e faz symlink da chave
de projeto de cada pasta sob `~/.claude/projects/` para esse armazenamento, de modo que o mesmo
histórico e memória acompanhem o workspace independentemente de qual pasta seja a primeira.

Se uma chave de projeto já contiver histórico real, o comando a deixa intacta e avisa disso. Para
mesclar manualmente: mova a chave existente para o lado, crie o symlink, copie o conteúdo antigo
para o armazenamento sem sobrescrever (`rsync --ignore-existing`), depois apague a cópia que foi
movida para o lado. Para desfazer, remova o symlink e mova o diretório de volta.

## Adicionando o checkout do harness a um workspace existente

Opcional, apenas por conveniência de edição. Adicione-o como uma pasta posterior. Ele não
contribui em nada para a ordem de carregamento (suas skills ficam em `claude/skills/`, não em
`.claude/skills/`), e seu próprio `AGENTS.md` só carrega quando você abre o repositório do harness
sozinho.
