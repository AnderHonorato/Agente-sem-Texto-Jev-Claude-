# Um switch pessoal, duas projeções de runtime

Nove eixos de postura são distribuídos, e três deles se ligam a mecanismos de aplicação:
`autonomy` decide qual grau de comando de shell para e pergunta, `delegation` roteia um spawn, e
`cost` resolve uma classe, um esforço e um orçamento por papel. Os outros seis são prosa que troca
de forma limpa em ambas as projeções. O switch demonstrado abaixo é `delegation`, um dos três.

A demonstração descreve o comportamento determinístico do adaptador. Não é um resultado de
qualificação de cliente nativo; use o [catálogo](compatibility.md) para essa evidência.

```sh
citizen config set stances.delegation off
citizen stances --json
citizen sync
```

A fonte resolvida é `primitives/stances/delegation/off.md`. O link de regra selecionado do Claude
e as instruções geradas do Codex carregam essa mesma política. Com os hooks nativos ativos, um
evento `Agent` do Claude e um evento `spawn_agent` do Codex se normalizam para a mesma política de
spawn compartilhada: perguntar antes do spawn, de modo que só um pedido explícito do usuário o
permite. `tests/test_lifecycle.py` exercita ambos os envelopes nativos.

```sh
citizen config set stances.delegation tiered
citizen stances --json
citizen sync
```

Ambas as projeções agora carregam `primitives/stances/delegation/tiered.md`: coleta limitada é
permitida; o julgamento permanece com a sessão. Cada papel compartilhado nomeia uma classe de
capacidade e a tabela `tiers` de cada adaptador mapeia as classes para seus próprios modelos
nativos, de modo que nenhum adaptador interpreta os nomes do outro. Ambos mapeiam as quatro
classes. Uma classe que um adaptador deixa de fora resolve para cima ou herda o modelo da sessão,
e uma sobrescrita de `role_bindings` de `model` para `inherit` faz o mesmo por papel.

Para comunicação, mude `stances.voice` de `answer-card` para `scannable`: o texto resolvido muda do
contrato resposta/porquê/pegadinha para seções que priorizam o veredito e rótulos explícitos de
status. A mesma fonte conduz ambas as projeções, mas só testes comportamentais nativos conseguem
medir a conformidade.

## Crie um switch seu

Crie `stances/feedback/direct.md` e `stances/feedback/gentle.md` em uma raiz de primitivos
externa:

```markdown
# Feedback stance: direct
Lead with the conclusion. Name the evidence and the next useful action.
```

```markdown
# Feedback stance: gentle
Explain the observation first, then suggest one concrete next action.
```

Registre a raiz absoluta em `primitive_roots`, selecione `stances.feedback=direct`, inspecione com
`citizen stances --json`, depois sincronize. Mudar para `gentle` altera as duas projeções sem uma
cópia específica de provedor. Uma nova postura em prosa é consultiva em ambos os adaptadores; ela
não adquire novos controles de aplicação só pelo nome. O [contrato de autoria](primitive-authoring.md)
cobre precedência de projeto e sessão, seleções inválidas, autoridades duplicadas e restrições de
conflito.
