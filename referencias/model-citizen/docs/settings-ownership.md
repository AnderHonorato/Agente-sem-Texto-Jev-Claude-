# Posse das configurações (settings ownership)

As declarações de posse nativa e o diário de reconciliação delimitam o que `citizen sync` pode
escrever. `claude/OWNERSHIP.json` registra os campos do template do Claude. Leia-o antes de
alterar o template.

## Claude Code (`~/.claude/settings.json`)

- **Chaves possuídas**: `outputStyle`, `plansDirectory`, `useAutoModeDuringPlan`,
  `showThinkingSummaries`. Reconciliadas contra o diário de posse; edições do usuário geram
  conflitos.
- **Estilo de saída**: `outputStyle` vem da postura `voice`, não do template. Uma variante com um
  arquivo em `claude/output-styles/` instala esse estilo, então `scannable` instala `Scannable`.
  Uma variante mapeada para um estilo embutido do Claude Code instala esse estilo pelo nome; hoje
  isso é só `concise`, que instala `Concise`. Uma variante sem nenhum dos dois, `answer-card` e
  `off` hoje, não instala nenhum. A posse do diário é a mesma para os dois tipos. `scannable` é a
  única variante à qual a projeção do Codex dá material de apresentação, que ela nomeia
  explicitamente, de modo que os dois runtimes fazem a mesma variante significar a mesma coisa. A
  posse é o que o diário de reconciliação registra o harness escrevendo, nunca o que o estilo se
  chama: um estilo que você mesmo escolheu — incluindo um chamado `Scannable` que você escolheu
  antes de instalar — nunca é reescrito, nunca é removido na desinstalação, e nunca é relatado
  como desvio. O estilo que o harness instalou é retirado quando a variante muda.
- **Chave de postura**: `permissions.defaultMode`, escrita somente quando a configuração
  `permissions` não é `inherit` (`bypass` → `bypassPermissions`, `auto` → `auto`, `manual` →
  `default`).
- **Regras de permissão (allow)**: a lista do template é mesclada como um conjunto em
  `permissions.allow`. É essa lista que permite ao modo plano rodar comandos somente leitura sem
  pedir confirmação: leituras em qualquer lugar sob o home, ferramentas de shell somente leitura
  que o conjunto embutido não cobre, formas de leitura de `gh`, `npm`, `cargo`, `uv`,
  `WebSearch`, e domínios de documentação e registro para `WebFetch`. Regras que você mesmo
  adicionou são mantidas. Uma regra que um template anterior carregava e o atual descartou é
  removida na próxima sincronização, então uma regra retirada aqui não sobrevive a ela nas suas
  configurações. Ferramentas cuja forma somente leitura depende de suas flags (`sort`, `sed`,
  `awk`, `fd`, `rg`, `tree`) não estão na lista; o hook `readonly-bash` aprova suas invocações
  seguras e deixa `sort -o`, `sed w`, `fd -x` e afins caírem no prompt.
- **Modo plano**: sem chave de configuração. Sob uma postura `bypass` ou `auto`, o coordenador
  PreToolUse responde às chamadas investigativas que as regras de permissão não conseguem provar,
  em vez de deixar o modo plano perguntar abaixo da postura que você selecionou;
  `plan_allow_tools` na configuração do usuário estende isso a globs de ferramentas nomeadas. O
  que cada grau recebe: `docs/preferences.md`.
- **Hooks**: um coordenador de política compartilhada em cada um dos eventos PreToolUse,
  PostToolUse, SessionStart, Stop e SessionEnd, gerado pelo adaptador nativo. Marcadores legados do
  harness são substituídos; hooks não relacionados permanecem. O harness possui apenas suas
  próprias entradas na lista de cada evento, aquelas cujo comando carrega um marcador `# harness:`
  ou nomeia um de seus scripts legados, então um hook que você adiciona ao lado deles não é um
  conflito de sincronização nem desvio, e a desinstalação o deixa no lugar. Adicione o seu como uma
  entrada separada: um comando colocado dentro de uma das entradas do harness torna essa entrada
  uma edição, o que a sincronização relata e a desinstalação preserva. As políticas decidem se a
  postura selecionada ativa uma verificação.
- **Nunca tocados**: `model`, `theme`, `viewMode`, `effortLevel`, `alwaysThinkingEnabled`,
  `skipDangerousModePermissionPrompt`, `env`, `permissions.deny`, `permissions.ask`, e qualquer
  chave não nomeada aqui.

## VS Code (`settings.json` do usuário)

- **Possuídas**: `claudeCode.focusView`, `claudeCode.preferredLocation`,
  `claudeCode.hideOnboarding`.
- **Postura**: `claudeCode.initialPermissionMode`, `claudeCode.allowDangerouslySkipPermissions`.
- Tudo mais, incluindo configurações de editor, terminal e tema, é deixado intacto.

## Codex (`~/.codex/config.toml`)

- **Possuída**: `project_doc_fallback_filenames = ["CLAUDE.md"]`.
- **Postura**: `approval_policy`, `sandbox_mode`, e a chave de revisor de aprovação. `manual`
  solicita revisão humana com um sandbox somente leitura; `auto` solicita revisão automática com
  escritas no workspace. As duas grafias dessa chave — `approvals_reviewer`, que o Codex atual
  aceita, e a mais antiga `approval_reviewer` — são possuídas pelo harness: a sincronização escreve
  a que o cliente instalado aceita e remove a outra, e a desinstalação restaura qualquer uma que
  tivesse escrito.
- **Gerados**: `AGENTS.md`, TOML de papel e skills de workflow, rastreados no diário de posse.
- **Hooks**: as próprias entradas do harness em cada array de evento de `hooks.json`, ao lado de
  quaisquer que você adicione; a confiança nativa nunca é fabricada.
- Modelo, esforço de raciocínio, hooks de notificação, servidores MCP, plugins e confiança por
  projeto nunca são tocados.

## Adicionando uma chave possuída

Adicione-a ao template, ao `OWNERSHIP.json`, a esta página, e a um teste em
`tests/test_harness.py` que mostre que o valor de um usuário para uma chave não possuída sobrevive
à mesclagem.

Veja [posse da instalação](runtime-installation.md) para adoção, tratamento de conflitos e
restauração.
