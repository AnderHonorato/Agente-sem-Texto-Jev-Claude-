# Levantamento de campo: o que o campo de compiladores de configuração faz, e onde este harness se situa

**Lido em 2026-09-21, emendado em 2026-09-23 (§4 e §6). Reverificar até 2026-12-01.** A leitura de
uma pessoa sobre um campo em rápida mudança, em uma data. O ritmo de lançamento entre os projetos
abaixo roda de diário a semanal, então trate todo "lança" e "não lança" aqui como uma observação
datada, não um fato permanente. O método, as fontes e o registro bruto de alegações estão na
execução de pesquisa sob
[`_bmad-output/planning-artifacts/research/`](../_bmad-output/planning-artifacts/research/), e
correções são bem-vindas como uma [issue de Ideia](https://github.com/JakeSelby/agent-harness/issues/new/choose).

## 1. Por que esta página existe

Comparações envelhecem mal e são escritas pela parte com mais a ganhar. Esta nomeia sua data, seu
método e suas próprias lacunas primeiro, e coloca o que usar *em vez* deste repositório acima do
que este repositório faz bem. Se essa ordem parece estranha, é o ponto: a página é feita para ser
útil a alguém escolhendo uma ferramenta, inclusive quando a resposta certa não é esta.

## 2. Como o campo foi lido

Quatro listas públicas selecionadas foram puxadas com `gh api <repo>/readme` e suas categorias
relevantes enumeradas: `RyanAlberts/best-of-Agent-Harnesses` ("Coding harness configs and SDKs",
"Personal agent runtimes", "Evaluation and benchmarking harnesses", "Observability and eval-ops"),
`hesreallyhim/awesome-claude-code` ("Configuration", "Linting"),
`jamesmurdza/awesome-ai-devtools` ("Configuration & Context Management") e
`ai-for-developers/awesome-ai-coding-tools` ("Developer Productivity Tools"). Vinte repositórios
foram então lidos a partir de suas árvores de arquivo, não de seus READMEs, e toda alegação
comparativa abaixo nomeia um caminho de arquivo ou uma URL que um leitor consegue abrir. Oito
rastreadores de issue foram lidos para ver o que os usuários elogiam, reclamam e pedem. Contagens
de estrela são registradas como contexto e nunca usadas como ranqueamento. Este repositório não
aparece em nenhuma das quatro listas até a data da leitura.

A categoria em que este repositório compete, nomeada com precisão: **ferramentas que guardam a
configuração de agente de código — regras, skills, subagentes, comandos, hooks — como uma única
fonte e geram os arquivos nativos de cada runtime a partir dela.** Três categorias adjacentes são
confundidas com ela e são estruturalmente diferentes: pacotes de skill distribuídos como estão
para um único runtime; linters somente-leitura de arquivos de contexto; e planos de governança que
controlam ações em tempo de execução.

## 3. O que usar em vez disso

Para a maioria das pessoas, na maior parte do tempo:

- **[rulesync](https://github.com/dyoshikawa/rulesync)** se você roda mais de dois runtimes. Ele
  compila para cinquenta e dois alvos, e a lista de alvos é derivada em vez de mantida à mão — uma
  tupla por funcionalidade, unida em `src/types/tool-targets.ts` ("nenhum literal mantido
  separadamente para desviar"). Ele importa e converte nas duas direções, é distribuído no npm, e
  cortou três lançamentos em quatro dias na semana em que isto foi escrito. Este repositório
  compila para dois runtimes e ainda não tem nenhum importador.
- **[ctxlint](https://github.com/YawLabs/ctxlint)** ao lado do que quer que você escolha. Noventa
  regras em quatro catálogos JSON, limiares de token que você pode ajustar (`error: 8000`,
  `tierAggregate: 4000`), e detecção de contradição através de arquivos em oito eixos de escolha
  de ferramenta (`src/core/checks/contradictions.ts`). Ele lê e nunca escreve, então compõe com
  tudo aqui. O motor de conflito deste repositório vem com um schema e nenhuma restrição.
- **[planning-with-files](https://github.com/OthmanAdi/planning-with-files)** se planos de longa
  duração são seu problema. Ele resolve um eixo melhor do que este repositório resolve nove, e sua
  precedência de `.mode` — "Root `.mode` is a FLOOR, not a default that slug scope replaces"
  (`scripts/inject-plan.sh`) — é uma ideia melhor que a precedência de sobrescrita deste
  repositório.
- **[gsd-core](https://github.com/open-gsd/gsd-core)** se você quer um controle de custo e
  qualidade hoje, através de dezesseis famílias de runtime, com uma equipe por trás. `MODEL_PROFILES`
  oferece `quality | balanced | budget | adaptive`, e a profundidade de revisão é rebaixada
  automaticamente além de um limiar de arquivo (`src/code-review-depth.cts`).

## 4. O que o campo acertou, nomeado

- **rulesync** — a lista de alvos derivada, `import`/`convert` bidirecional, e um `doctor` com
  dezoito códigos de diagnóstico tipados. Também a tabela de amplitude mais honesta do conjunto:
  ela marca alvos em fim de vida como "frozen-compatibility" em vez de descartá-los ou escondê-los.
- **planning-with-files** — o único projeto posicionado sobre evidência. Seu README abre com "3
  out of 3 blind A/B wins", linka o método, e revela seus limites no mesmo fôlego ("Trate isso como
  a própria medição do projeto, não uma comparação independente"). Seu benchmark contínuo de sete
  braços publica um resultado *contra si mesmo* e carrega uma seção "O que este teste não mede"
  ([`docs/evals.md`](https://github.com/OthmanAdi/planning-with-files/blob/main/docs/evals.md)).
  Essa é a barra para uma alegação de evidência neste campo, e esta página se mantém abaixo a essa
  barra.
- **wshobson/agents** — uma matriz de capacidade gerada a partir de código em vez de mantida como
  prosa: `tools/adapters/capabilities.py` produz
  [`docs/harnesses.md`](https://github.com/wshobson/agents/blob/main/docs/harnesses.md), quatorze
  capacidades por seis harnesses, com uma segunda tabela de "degradação graciosa" nomeando a
  reescrita exata por padrão por runtime. Também uma verificação de colisão de nome que este
  repositório não tinha.
- **gstack** — `bin/gstack-developer-profile` mantém valores declarados *e inferidos* em cinco
  dimensões de preferência e sinaliza desvio entre eles com `--check-mismatch`. Este repositório
  tem posturas declaradas e regras medidas; ainda não infere qual é sua postura efetiva.
- **agents-md-cookbook** — o único limite de tamanho com fonte citada no campo:
  `CODEX_BYTE_CAP = 32768`, citando que o Codex trunca o AGENTS.md em 32 KiB (`rules/byte-cap.ts`).
  Seis projetos aplicam um limite e nenhum dos dois números concorda — 200 linhas, 150, 400, 8.000
  tokens, 32 KiB — e só este diz o porquê.
- **Burnd** ([garvitsurana271/burnd](https://github.com/garvitsurana271/burnd)) — o vizinho mais
  próximo do que este repositório mede. Ele lê as mesmas transcrições do Claude Code, sinaliza
  disparo pesado de skill ("geralmente significa que a descrição de uma skill é ampla demais"), e
  anexa um `claudeMdPatch` — "a única linha do CLAUDE.md (ou bloco curto) que corrige este
  vazamento" — a todo insight. Ele roda na direção oposta a este repositório (vazamento →
  regra sugerida, em vez de regra → disparou), e é creditado aqui porque a direção é a única
  diferença.
- **claude-md-doctor** ([agent-clinic/claude-md-doctor](https://github.com/agent-clinic/claude-md-doctor),
  lido em 2026-09-23) mede o que este repositório mede, a partir das mesmas transcrições do Claude
  Code. Em cada checkup, o modelo decompõe o CLAUDE.md em matchers regex por regra, um script de
  biblioteca padrão os reproduz sobre o histórico de sessão, e o modelo verifica por amostragem
  cada disparo antes de contá-lo. O relatório dá a cada regra suas oportunidades, um número de
  conformidade e um veredito, depois ordena violações por causa e propõe um hook para as regras que
  valem a pena aplicar. Regra para "disparou ou não" é a mesma direção deste repositório, e para o
  próprio CLAUDE.md de uma pessoa ele responde hoje o que `citizen usage --rules` só responde para
  regras que carregam um detector.
- **RuleReceipt** ([rulereceipt/rulereceipt](https://github.com/rulereceipt/rulereceipt), lido em
  2026-09-23) verifica se uma sessão do Claude Code seguiu seu CLAUDE.md ou AGENTS.md, com
  verificações determinísticas sobre comandos git e operações de arquivo e uma linha de evidência
  citada para cada resultado. Regras que exigem julgamento relatam UNCLEAR a menos que o usuário
  opte por um avaliador de modelo com sua própria chave. Também escreve um arquivo de recibo para
  CI e distribui uma guarda de pré-ferramenta. É disponível por fonte (source-available) em vez de
  open source.
- **superpowers** — dezesseis seções de instalação por runtime e nenhuma alegação de amplitude em
  sua linha de destaque, o que é o oposto do exagero usual do campo.

## 5. O que este repositório tirou do campo

- A **alegação de singularidade limitada** na §6 existe porque o cenário de avaliação e telemetria
  foi verificado em vez de afirmado; o "ninguém mede" ilimitado era falso, e Burnd é o motivo. A
  emenda de 2026-09-23 a estreitou de novo, porque claude-md-doctor e RuleReceipt agora ligam uma
  verificação a cada regra e relatam se foi seguida.
- Uma **matriz de compatibilidade gerada** com uma tabela de degradação, no modelo de wshobson,
  substitui duas autoridades mantidas à mão que tinham se desalinhado (`compatibility/catalog.json`
  marcava clientes como qualificados enquanto `adapters/*/capabilities.json` marcava toda postura
  como não qualificada).
- Um **manifesto de plugin, um caminho de instalação empacotado e um importador** — as três coisas
  que todo vizinho de alta adoção distribui e que este repositório não distribuía — são trabalho da
  0.13, com o `import` do rulesync como referência.
- **Semântica de piso (floor) para posturas**, de planning-with-files, está agendada e ainda não
  adotada.
- O **vocabulário do campo**: das oito linhas de destaque de projeto, só uma usa a palavra
  "harness", e ali ela nomeia os runtimes alvo. O substantivo mais comum é "skill", depois
  "config", depois "rules". A porta de entrada deste repositório agora lidera com regras.

## 6. O que existe aqui que eu não encontrei em outro lugar

Declarado tão restritamente quanto a evidência permite. Cada linha nomeia o arquivo que a
implementa.

- **Regras que são medidas, e um lint que recusa uma não medida.** Todo arquivo de regra nomeia um
  detector determinístico sobre a própria transcrição do agente ou carrega um motivo de uma linha
  para nada na transcrição conseguir decidi-lo; `check_detectors` em `bin/harness` falha o commit
  caso contrário. `citizen usage --rules` relata taxa de acerto por regra, agrupada por
  repositório e por qual variante de preferência foi selecionada. Ligar uma verificação a cada
  regra e relatar se foi seguida não é mais único: claude-md-doctor e RuleReceipt fazem os dois em
  transcrições do Claude Code (§4). O que eu não encontrei em outro lugar, até 2026-09-23, é o
  resto: um lint que recusa uma regra não medida, detectores commitados como dados e pontuados
  contra um corpus rotulado com um piso de precisão na CI, taxas por regra agrupadas por variante
  de preferência, e a mesma medição tanto no Codex quanto no Claude Code. Também exporta o mesmo
  ledger via OTLP para o stack de observabilidade que você já roda — Langfuse, Phoenix e Opik todos
  o aceitam — adicionando a única coisa que essas plataformas não conseguem ver, qual regra
  disparou.
- **Um diário de posse para os arquivos que gerencia.** `lib/harness_core/reconcile.py` registra o
  conteúdo anterior e o aplicado por campo possuído, recusa um caminho não gerenciado ("adote
  explicitamente antes de substituí-lo"), sai com código não-zero em conflito, e
  `citizen uninstall` restaura valores anteriores somente enquanto o valor atual ainda combina com
  o que foi aplicado por último. O equivalente do rulesync cobre apenas hooks, opt-in.
- **Comandos de shell classificados de 0 a 3 antes de rodar.** `claude/hooks/grade-bash.py`
  decompõe compostos, substituições e heredocs e classifica reversibilidade; a postura autonomy
  define qual classe para e pergunta. Ferramentas comparáveis fazem correspondência de padrão sobre
  a string do comando.
- **Um coordenador de política por evento de ciclo de vida através de dois runtimes**, falhando
  fechado (`lib/harness_core/lifecycle.py`): um spawn do Claude Code e um spawn do Codex resolvem
  para a mesma política de delegação.
- **Preferências como nove eixos extensíveis pelo usuário.** Outros três projetos distribuem de um
  a três eixos comportamentais trocáveis; este repositório generaliza a ideia, e só três dos seus
  nove eixos se ligam a mecanismos de aplicação hoje (autonomy, delegation, cost). O resto é prosa
  que troca de forma limpa. Esse limite é declarado no texto do produto, não escondido aqui.

## 7. O que isto deliberadamente não faz

- Nenhum roteamento de modelo, nenhum gateway de API, nenhum loop de agente. O Claude Code e o
  Codex continuam responsáveis por acesso a modelo, permissões nativas e comportamento de cliente.
- Nenhum cinquenta e dois alvos. Seis runtimes na mesma profundidade é o teto que este repositório
  almeja, e só depois que o ciclo de medição estiver fechado. Usuários de todo projeto neste campo
  pedem novos runtimes mais do que qualquer outra coisa; essa demanda é real, e é do rulesync
  atendê-la.
- Nenhum daemon sempre ativo, nenhum serviço hospedado, nenhuma superfície de equipe. Tudo é
  arquivo local.
- Nenhuma alegação de que uma regra produziu o mesmo comportamento em dois runtimes. Ninguém no
  campo mostrou isso, este repositório incluído.

## 8. Lacunas honestas

A seção que decide se o resto é crível.

- **A validade do detector é medida para dezenove detectores de dezenove.** O wheel vendorizado
  `ruleprobe` distribui um corpus rotulado e um avaliador `validity.py` para os detectores
  genéricos que o próprio motor distribui; `tests/fixtures/detector-corpus/` rotula o resto, cinco
  positivos e cinco quase-erros cada, exceto `research/search-over-cap`, cujo positivo custa uma
  transcrição inteira de duzentas buscas. A CI roda `scripts/detector_corpus.py --floor 0.9` sobre
  os dois corpora no job `corpus`, então uma precisão ou recall abaixo de 0,9 é um check vermelho.
  Dois detectores ficam abaixo do piso e são registrados como tal, com a pontuação e o piso contra
  o qual foram medidos, em vez de o piso ser abaixado: `secrets/git-add-secret-file` lê qualquer
  nome-base contendo `id_rsa` como uma credencial, e `autonomy/denied-by-grade` lê a assinatura do
  hook de classificação em qualquer lugar de um resultado de Bash, então um runbook nomeado após
  uma chave e um grep que imprime a assinatura são ambos acertos (p=0,83, r=1,00 cada). Um corpus é
  sintético e escrito à mão, então mede o detector contra o que seu autor diz que ele deveria
  encontrar, não contra o campo.
- **Taxas de acerto por variante são observacionais.** Nenhum conjunto fixo de tarefas é
  reproduzido sob a variante A e a variante B; "esta regra funciona melhor sob `execute`" ainda não
  é uma frase sustentada. O único projeto que rodou um A/B neste campo mostra tanto o quanto isso
  ajuda uma posição quanto quão rápido um método fraco é descontado.
- **Regras que optam por sair de um detector ficam no escuro.** Regras de tom, altitude e
  honestidade carregam um motivo `OPT_OUT` e nenhuma medição. A maquinaria de juiz-LLM que
  Langfuse, Opik e Phoenix distribuem é exatamente o que essas regras precisam, e não está aqui.
- **O motor de conflito distribui quatro restrições e nunca usou `requires`.**
  `constraints.json` suporta `when`/`requires`/`excludes`, `citizen lint` falha e `citizen sync`
  recusa em uma seleção que viola uma delas, e as quatro restrições distribuídas incluem a
  contradição que a motivou: `delegation/tiered.md`, sempre carregado, diz "Nunca `frontier`",
  então um papel declarando `tier: frontier` é excluído a menos que a skill delegation-tiering o
  isente (#464). O que ainda não foi testado na prática é o resto do schema, e as restrições são
  só sobre declarações de postura e papel, nunca sobre a prosa de uma regra.
- **Nenhum manifesto de plugin, nenhuma instalação empacotada, nenhum importador** até a data da
  leitura; de 8 a 12 comandos até o primeiro valor. #446, #447, #448.
- **O limite sempre carregado agora é um limite de token, e cita sua fonte.** `bin/harness` cita a
  documentação de memória do Claude Code sobre o que o número de 200 linhas vale e não vale, e
  define o limite aplicado como um terço do contexto permanente de 12.607 tokens que a issue #430
  mediu contra um perfil nu; o limite de 200 linhas permanece como a guarda secundária de
  legibilidade (#450). A lacuna residual é a própria estimativa: caracteres divididos por quatro,
  não um tokenizador, bom para um limite e uma tendência e nunca para cobrança.
- **Dois runtimes.** "Entre agentes de IA" ainda não é uma manchete honesta, e não é a manchete.
- **Duas coisas que o instrumento capturou sobre este próprio repositório**, registradas como o
  exemplo trabalhado em vez de escondidas: #429, uma postura de delegação distribuída medida como
  nunca disparando em dezenove execuções headless; #324, um hook distribuído medido como não
  movendo a métrica que foi construído para mover. Nenhum outro projeto no campo consegue produzir
  um achado dessa forma sobre si mesmo, e ambos foram registrados como bugs.

## 9. Correções bem-vindas

Esta página é versionada e datada. Se um projeto nomeado aqui lançar algo que muda uma linha, ou se
uma alegação não combinar com o que você encontra no arquivo que ela cita, abra uma
[issue de Ideia](https://github.com/JakeSelby/agent-harness/issues/new/choose) com o caminho. A
execução de pesquisa que produziu esta página carrega um mapa de obsolescência; sua primeira
reverificação é 2026-12-01, e uma atualização substitui esta página em vez de emendá-la.
