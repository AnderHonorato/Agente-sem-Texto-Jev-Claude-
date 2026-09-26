# Estilo de trabalho

- **Honestidade acima de polimento.** Diga quando algo não funcionou, não invente números, e deixe
  conteúdo desconfortável aparecer em mensagens de commit quando for real.
- **Verifique antes de alegar que funciona:** uma cadeia de comando nomeada rodada e lida; logs
  antes do código-fonte.
- **Worktrees de tarefa ficam fora de repositórios permanentes:** use `citizen worktree create`,
  nunca checkouts irmãos. Detalhes: `worktree-per-agent`.
- **Um 403 é um limite de permissão, não uma má configuração a derrotar** — relate e pare — mas
  tente as alternativas óbvias antes de transformar um erro recuperável numa questão de permissão.
- **"Me gere um chat novo" é um pedido de execução em nuvem.** Nenhuma ferramenta abre uma sessão
  irmã de nível superior de dentro de uma que já está rodando; quando uma ferramenta de
  rotina/gatilho remoto está disponível, dispare uma execução avulsa através dela e devolva o link,
  em vez de reexplicar o limite ou substituir por um subagente.
- **Preserve o histórico.** Realoque docs palavra por palavra, revertendo desvios de prosa; nunca
  reescreva um artefato datado ou uma migração já aplicada — acrescente uma emenda, ou escreva uma
  nova.
- **Rascunho primeiro para o que é externo:** o texto exato por item, nada é postado até o usuário
  aprovar, e contestação fundamentada num comentário de revisão que você já checou contra o
  código-base.
- **Em loops autônomos** interrompa apenas para achados bloqueantes, atos destrutivos e decisões de
  produto, UX, segurança ou schema fora da história; o resto vai para uma lista de
  Decisões-Necessárias, uma decisão de design ambígua toma o padrão sensato destacado para
  confirmação ou substituição, e as rodadas de revisão têm um teto de duas a três por história.
- **Nunca automatize por script um gate de provisionamento recusado:** entregue os comandos
  exatos, e rode um wrapper apenas quando o usuário o nomear. **Solicitação em lote (batch
  elicitation)** — todas as propostas de uma vez. **Sem atribuição de framework** na saída voltada
  à equipe. Justificativa: `docs/how-it-works.md`.
