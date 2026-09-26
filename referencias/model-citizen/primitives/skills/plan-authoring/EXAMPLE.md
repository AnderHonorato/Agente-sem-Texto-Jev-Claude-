Este é um plano real de 884 linhas reduzido ao seu Review Card. Todo fato abaixo já existia
naquele arquivo — estava espalhado por 590 linhas antes da primeira coisa que o revisor precisava
decidir. Nada foi inventado para encurtá-lo. Nomes foram trocados; a forma não.

---

# Execução de design 2 — integração de quatro handoffs

> **Veredito.** Reconcilia os handoffs de quatro agentes paralelos num único board, um único
> registro de decisões e uma única fila de revisão ordenada, verificando toda alegação de
> fechamento contra os repositórios em vez de retransmiti-la.
> A Fase 0 registra o estado verificado no "build"; publicação e toda mudança de status esperam
> um gate.
> **Esforço** uma sessão + ~80 min de revisão · **Risco** médio — duas submissões não publicadas
> ambas escrevem o objeto compartilhado `terrain` · **Raio de impacto** apenas commits no
> repositório de planejamento

## Em resumo

- **Resultado** — Um board, um registro, uma fila de revisão ordenada. Nada publicado, nada `done`
- **Abordagem** — Checar toda alegação contra o repositório, hash, commit e render, depois uma
  passada de edição central
- **Toca** — o repositório de planejamento (board, `decisions.md`); o repositório de arte
  somente-leitura; 4 registros de handoff
- **Novas dependências** — Nenhuma. O Gate 2 adiciona dois pacotes de asset CC0-1.0, já
  manifestados
- **Fora de escopo** — Publicar qualquer submissão · Gate 3+ · trilha C1c · qualquer item chegando
  a `done`
- **Teste de saída** — Contagens recomputadas uma vez centralmente e reconciliando para 104
  itens; toda mudança de status carrega um artefato vinculado e rotulado como **Mock**
- **Questão em aberto** — Quem publica, e em que ordem — decisões 2 e 3

## Design do sistema

```text
H1 Estruturas ──┐
H2 Água ────────┤
H3 Vegetação ───┼─▶ Verificar contra os repositórios
H4 Assentamentos┘     ├── alegações verificadas ──▶ Board + decisions.md
                      ├── 3 itens, ~80 min ──▶ *Fila de revisão
                      │                          └── aceitação ──▶ Board
                      └┄┄ congelado ┄┄▶ 3 submissões preparadas
                                       └┄ precisa ┄▶ *Publicador — não preenchido
```

`*` marca um gate: nada o atravessa sem o revisor.

## Passos

1. **[Preservar o buffer sujo órfão](#step-1--the-orphaned-dirty-buffer)** — `renders/settlements/c1b/`.
   *Exit:* cópia datada escrita e SHA-256 registrado. Bloqueia toda outra ação de editor.
2. **Edições no board** — C1b e C1h para `blocked`, três defeitos de corpus, Q17–Q18, X38–X47.
   *Exit:* toda linha carrega um link de evidência e um rótulo **Mock**.
3. **Adicionar seis linhas a `decisions.md`** — apenas anexação, nada reordenado.
   *Exit:* nenhuma linha existente editada, confirmado por diff.
4. **[Recomputar contagens centralmente, uma vez](#step-4--why-counts-are-central)** — não por
   handoff.
   *Exit:* reconcilia para 104 — 51 itens de trilha, 37 adiados, 16 questões.
5. **Commit, um Conventional Commit por passo lógico** — planejamento `main`.
   *Exit:* check de governança e log tentados ao redor de cada um.
6. **Aguardar o Gate 1 (C1b) e o Gate 2 (estruturas)** — nenhum trabalho adicional até que ambos
   respondam.
   *Exit:* a formulação exata e a data do revisor registradas literalmente.

## Decisões para o revisor

> **1. O buffer sujo órfão — preservar, preservar e fechar, ou descartar?**
> *Recomendo* preservar numa cópia datada e deixar o processo em paz — a proteção permanente diz
> isso e esta cena já foi preservada desta forma antes.
> *Alternativa* descartar, se a revisão de distrito de quatro dias for conhecidamente superada.

> **2. Quem é o publicador designado, ou a publicação fica congelada?**
> *Recomendo* nomear um — três submissões preparadas não podem se mover, e nenhum dono vai
> atestar por outro.
> *Alternativa* ficar congelado; as três submissões permanecem imutáveis e nada se perde.

> **3. Se um publicador for nomeado, qual é a ordem de publicação?**
> *Recomendo* a regra permanente como está escrita — água se reprojeta contra a revisão publicada,
> nunca uma cena antiga de vegetação sobrescrevendo-a.
> *Alternativa* publicar o anexo de dossel de vegetação primeiro e rerodar o gate de 28 m de água
> depois.

> **4. Q17 — a saída de C1h aceita o par 7 km e 20 km, ou exige uma faixa estratégica?**
> *Recomendo* aceitar o par; a galeria está completa em ambas as faixas e um terceiro render é
> trabalho novo.
> *Alternativa* exigi-la, e C1h fica `blocked` até que essa passada exista.

> **5. Q18 — água e vegetação recebem itens no board, ou permanecem rastreados por suas
> especificações?**
> *Recomendo* itens no board — ambas estão autorizadas e ativas, e o registro ainda chama a
> reconstrução de 28 m de "escopada, não autorizada", que agora é falso.
> *Alternativa* deixar ambas para suas especificações e apenas emendar o texto desatualizado de
> X19.

## Riscos

- **O `terrain` compartilhado é escrito por duas submissões não publicadas** — a ordem de
  publicação é uma restrição de correção, não uma preferência; tudo fica congelado até as decisões
  2 e 3.
- **Duas janelas de editor mostram ambas "C1b"** — a fila nomeia um processo explicitamente;
  julgar o outro julga uma revisão de quatro dias.
- **A trilha D é o caminho crítico e nenhum agente está nela** — D1 espera por B2c, que está
  `not started`.

---

# Adendo

<As outras 800 linhas vão aqui: o registro de gates, o registro de IDs, a matriz de toque, as
quatro seções de verificação por handoff, o registro de licenciamento, os scripts da fila de
revisão, a avaliação por trilha. Um cabeçalho `## Step N — <titulo>` para cada passo ao qual o
card se ancora.>
