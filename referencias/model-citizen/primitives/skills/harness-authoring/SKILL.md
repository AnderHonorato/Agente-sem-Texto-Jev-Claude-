---
name: harness-authoring
description: Decide where an instruction belongs and write it there, then sync and lint. Use when asked to add, change or remove a rule, skill, instruction, hook, setting or CLAUDE.md line, to "remember" something that should persist beyond this session, or when a correction should apply to future sessions. (Decida onde uma instrução pertence e escreva-a lá, depois sincronize e faça lint. Use quando pedido para adicionar, mudar ou remover uma regra, skill, instrução, hook, configuração ou linha do CLAUDE.md, para "lembrar" de algo que deve persistir além desta sessão, ou quando uma correção deve se aplicar a sessões futuras.)
---

# Autoria do harness

Toda instrução tem exatamente um lar certo. Esta skill o encontra, escreve ali, e mantém o
checkout do harness como a fonte de verdade para tudo que é genérico.

## Encontre o checkout e quem chama

```bash
python3 - <<'EOF'
import json, pathlib
m = json.load(open(pathlib.Path.home() / ".local/state/agent-harness/manifest.json"))
print(m["repo"])
EOF
git -C "$(…)" remote -v
```

Se o manifesto estiver faltando, localize ou instale o harness antes de editar conteúdo gerenciado.
Não crie uma segunda autoridade num diretório de configuração de runtime. Se `origin` é um fork e
`upstream` é o harness, você é um **usuário de fork**. Senão, se `origin` é `<owner>/model-citizen`,
ou `<owner>/agent-harness` de antes do renomeio, e você é aquele dono, você é o **mantenedor**.

## A escada — a primeira correspondência vence

1. **Precisa rodar num ponto do ciclo de vida independente do julgamento do modelo** (um check
   antes de todo commit, um validador depois de toda escrita) → uma política compartilhada sob
   `policy/hooks/`, despachada por `lib/harness_core/lifecycle.py`; registros nativos pertencem aos
   adaptadores de runtime.
2. **Muda a configuração de ferramenta ou editor, não o comportamento** → uma configuração nativa
   própria no adaptador relevante ou na projeção do editor, reconciliada pelo instalador. Não
   adicione um segundo primitivo para representar uma configuração de runtime.
3. **Verdadeiro só para este usuário, um segredo, ou sobre um projeto** → nunca o repositório do
   harness. Uma preferência pessoal vai na configuração do usuário ou numa raiz de postura
   personalizada documentada em `docs/primitive-authoring.md`; outra orientação pessoal fica no
   arquivo pessoal do runtime. Um fato sobre um repositório vai no `AGENTS.md` daquele repositório.
4. **Um usuário razoável poderia ter a preferência oposta** → uma variante de postura sob
   `primitives/stances/<pref>/<variant>.md`, e uma linha em `config.example.json` e
   `docs/preferences.md`. Nunca uma regra central.
5. **Um procedimento com passos, com mais de 40 linhas, ou necessário apenas sob um gatilho** →
   uma skill sob `primitives/skills/<name>/SKILL.md`, com uma descrição que diz quando usá-la.
6. **Aplica-se apenas a alguns tipos de arquivo** → uma regra com frontmatter `paths:`, no
   repositório ao qual se aplica.
7. **Curto, global, desejado em todo turno** → `primitives/rules/<topic>.md`. Verifique toda regra
   existente primeiro; o resultado usual é uma frase dobrada num arquivo existente, não um novo.
8. **Caso contrário é uma memória, não uma instrução** → memória automática para o projeto atual.

Um pedido de "lembre-se disto" percorre a mesma escada do topo. Um fato sobre um projeto ou uma
máquina é memória automática para aquele projeto, nunca o harness. Uma correção de como o agente
deve se comportar em qualquer lugar é uma regra ou uma postura, e você diz isso antes de escrevê-la.
Um fato sobre o usuário é um arquivo pessoal, fora do repositório.

## Testes a aplicar antes de escrever

- **Regra ou skill?** Regras carregam toda sessão e custam contexto em todo turno para todo
  usuário. Skills carregam sob invocação. Quando uma regra começa a crescer em passos, ela queria
  ser uma skill.
- **Central ou postura?** Se você consegue imaginar um engenheiro competente escolhendo o oposto, é
  uma postura. Licenciamento, estilo de commit, filosofia de teste e nível de autonomia são
  posturas; "verifique antes de alegar que funciona" não é.
- **Duplica uma regra global?** Faça grep em `primitives/rules/` e `primitives/stances/` pelo
  tópico. Não reafirme uma política que vive numa regra global dentro de uma regra de projeto;
  vincule a ela.
- **É genérico?** Sem nomes, sem caminhos sob um diretório home, sem empregador, sem projeto. O
  lint vai rejeitar de qualquer forma; escreva na segunda pessoa desde o início.

## Escreva, sincronize, faça lint, commit

1. Edite as fontes compartilhadas no checkout de desenvolvimento isolado. Diretórios de runtime
   contêm links gerenciados e visões geradas; editá-los pode mudar o checkout ao vivo ou criar
   desvio.
2. Rode `bin/harness generate` para visões nativas e `bin/harness generate --check` para
   verificá-las. Veja `docs/primitive-authoring.md` para dimensões personalizadas e vínculos
   nativos. Verifique a sincronização num home descartável com `HARNESS_HOME`,
   `CLAUDE_CONFIG_DIR`, e `CODEX_HOME` redirecionados. Sincronize instalações normais a partir do
   release revisado, não da worktree de desenvolvimento.
3. `bin/harness lint` — falha em strings pessoais e padrões de segredo.
4. Faça commit com um Conventional Commit. Depois, dependendo de quem você é:
   - **Mantenedor:** toda mudança vai num branch numa worktree e abre um PR; o conjunto de regras
     do `main` exige checks verdes e um squash merge. Mudanças de código (`bin/harness`, política
     compartilhada, testes) carregam um teste; mudanças de conteúdo são controladas pelo lint e
     pela revisão.
   - **Usuário de fork:** faça commit no `main` do seu fork, que é seu harness ao vivo. Se a
     mudança vale a pena compartilhar, `git fetch upstream && git rebase upstream/main`, envie um
     branch para o fork, e `gh pr create --repo <owner>/<name>`, nomeando o repositório para o qual
     seu remote `upstream` aponta.
5. Registre em uma linha para onde o item foi e por quê, para que o posicionamento seja auditável.

## Escrevendo texto de regra e comentário: os exemplos de concisão

`conciseness.md` foi cortado para suas linhas operacionais quando o contexto sempre carregado
recebeu um teto. Seus exemplos trabalhados vivem aqui.

**Explique uma decisão uma vez.** Escolha o lar mais natural único para uma justificativa de
design — geralmente o docstring do módulo ou classe onde a coisa é definida, ou a página de
documentação voltada ao usuário para qualquer coisa que um usuário precise. Todo outro arquivo que
toca o conceito recebe um ponteiro curto de volta, não uma reafirmação.

```python
# Ruim — reafirma a justificativa completa num arquivo consumidor
# We chunk at 999 rather than the documented 10,000 limit because early testing
# suggested the endpoint became unreliable above 1,000 records, and because ...

# Bom — uma linha, aponta para a explicação canônica
# Chunked per `batch_size`; see the class docstring for the API's limits.
```

Se um segundo documento explica o mesmo conceito que um primeiro, ele se vincula a ele.

**Não narre o que o código já diz.** Comentários explicam um *porquê* não óbvio. Se um comentário
seria um resumo exato de uma linha da próxima linha de código, apague-o.

**Docstrings seguem o padrão da casa.** Combine exatamente com o estilo ao redor. Leia uma função
vizinha antes de escrever uma nova. Não adicione docstrings puramente para satisfazer um linter que
não está rodando; adicione-os onde um usuário da API pública precisar deles.

**Sem referências de contexto privado em código entregue.** Código, testes e docs precisam se
sustentar sozinhos para um estranho. Nenhuma referência a docs de planejamento, outros
repositórios, números de tickets internos, ou notas de avaliação. Números públicos de issue e PR
estão bem e são úteis — são resolvíveis por qualquer leitor.

**Descrições de PR.** Comece com o quê e o porquê em alguns marcadores, mais um link para a issue.
Preencha as seções do template e não apague nenhuma, mas mantenha cada uma curta. Uma descrição de
PR longa com cabeçalhos pesados e formatação em negrito é mais difícil de revisar, não mais
informativa. Conteúdo explicativo longo pertence à issue ou a `docs/`, referenciado a partir do
corpo do PR.

## O teto de sempre-carregado

`primitives/instructions.md`, todo arquivo em `primitives/rules/`, e a variante mais longa de cada
dimensão de postura são carregados em todo turno de toda sessão. `citizen lint` falha quando o
tamanho combinado deles excede `ALWAYS_LOADED_TOKEN_CAP` em `bin/harness` — um terço do contexto
permanente de 12.607 tokens medido na issue #430, e o limite vinculante — ou o `ALWAYS_LOADED_CAP`
secundário em linhas. Ambos são impressos em toda execução de lint. Uma regra que precisa de mais
espaço do que o teto permite está te dizendo que ela queria ser uma skill: mantenha a linha
operacional residente, mova a justificativa, exemplos e evidência para a skill que a regra aponta,
e deixe um ponteiro de uma linha para trás. A contagem de posturas usa a variante *mais longa* por
dimensão, então nenhuma configuração que um usuário possa selecionar jamais fica acima do teto.
