# Spikes

Um spike responde a uma pergunta com o experimento mais barato capaz de respondê-la, e é julgado
contra um número escrito antes de o experimento rodar. O formato de uma linha — pergunta,
experimento mais barato, critério de saída, status, máquina — é a skill `spike-contract`; esta
pasta guarda os registros, um arquivo por spike, nomeado pela data em que foi decidido e pela
pergunta que resolveu.

Um registro de spike é histórico. Ele não é revisado quando uma medição posterior discorda: a
medição posterior ganha seu próprio registro, e os dois são lidos em ordem.

- [2026-09-22 — adiar o texto de regra condicionado a ação para depois dos hooks que disparam na
  ação](2026-09-22-deferred-rule-text.md): aberto, nada rodado ainda. Formulado ao aparar o
  contexto padrão (#430).
- [2026-09-22 — aviso de orçamento durante a execução para um subagente em execução](2026-09-22-in-run-budget-nudge.md):
  não construir. Medido no ledger de uma única máquina (#322).
