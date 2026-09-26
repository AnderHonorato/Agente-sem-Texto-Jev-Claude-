# Postura de custo: frugal

O esforço da sessão roda em **baixo** a menos que a tarefa seja design ou revisão adversarial.
Subagentes são apenas coletores, o fan-out não passa de três, e o modo rápido nunca é usado.
Times de agente estão desligados. Termine uma tarefa com `/clear`, nunca `/compact`; passando
80.000 e depois 120.000 tokens de contexto, o feed diz para fazer handoff e começar do zero —
pontos de partida escolhidos contra uma janela de 200k, não figuras medidas. Antes de uma chamada
de modelo, tente um comando determinístico — o teste, o linter, o código de saída. A tabela
precifica cada papel e banda: classe, esforço, orçamento. O tier vem de `delegation`. Cache:
`cache-hygiene.md`.
