# Continuar uma tarefa em qualquer um dos dois runtimes

O snapshot compartilhado e legível por humanos é `.agent-harness/progress.md`; o início de sessão
lê o antigo `.claude/progress.md` somente quando o arquivo compartilhado está ausente. Os planos
ficam em `.agent-harness/plans/`. Transcrições nativas e memória permanecem em seus próprios
armazenamentos de runtime.

Para um handoff estruturado, prepare um arquivo JSON:

```json
{
  "objective": "Complete the selected change",
  "next_steps": ["Inspect the current diff", "Run the repository gate"],
  "decisions": ["Keep the public API stable"],
  "artifacts": ["docs/design.md"],
  "framework_root": "/path/to/shared-checkout",
  "baseline": "the-reviewed-base-commit"
}
```

```sh
citizen task show
citizen task save --input task-input.json --runtime claude-code --revision 0
# No Codex, a partir do mesmo worktree:
citizen task show
citizen task save --input task-input.json --runtime codex --revision 1
```

A revisão rejeita escritores concorrentes desatualizados. A identidade do repositório e uma
impressão digital de conteúdo impedem que uma árvore alterada herde uma alegação de verificação.
Planos e progresso compartilhados contam como entradas mesmo quando ignorados pelo Git; apenas a
contabilidade da tarefa é excluída. A verificação relatada é mantida como evidência não verificada;
a sessão que recebe roda o gate por conta própria. Os próximos passos são dados, nunca executados
pelo carregador, e aprovações nunca são transferidas. O armazenamento rejeita symlinks. Mantenha
dados pessoais de handoff fora dos commits com uma entrada de ignore do projeto quando necessário.
