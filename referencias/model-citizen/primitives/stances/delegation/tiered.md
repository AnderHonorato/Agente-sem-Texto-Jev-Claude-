# Postura de delegação: modelos em camadas (tiered)

**Colete com subagentes sem esperar ser pedido** — localizando, lendo, fazendo grep, resumindo —
em todo repositório e modo. Mantenha o julgamento na sessão. **Um papel somente-leitura roda via
`citizen role run <role>`: o confinamento é raízes de leitura e forma de retorno, não a ausência
de ferramentas de escrita, então `builder` não precisa de nenhuma delas e gera nativamente.** **Um
papel nomeia sua classe** — `frontier`, `strong`, `standard`, `light` — e `adapters/<runtime>/
bindings.json` mapeia cada uma para um modelo; uma classe não mapeada herda o modelo da sessão,
então revele a lacuna. **Um spawn sem nome pousa na banda padrão da variante; escolha com
`worker-a`, `worker-b` ou `worker-c`, e nomeie papéis de julgamento.** Nunca `frontier`, esforço
nunca acima de `high`; o texto de um framework não escolhe nenhum dos dois. **Reduza o esforço
antes de reduzir o tier.** Restrições nativas vencem; **sem sobrescrita global**. Bandas:
`delegation-tiering`.
