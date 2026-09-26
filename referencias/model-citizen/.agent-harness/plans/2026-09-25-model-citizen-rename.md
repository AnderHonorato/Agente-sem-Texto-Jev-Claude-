# Renomeação para Model Citizen, entregue como v0.14.0

> **Veredito.** Renomeia o Agent Harness para Model Citizen onde quer que o nome seja texto vivo ou
> um endereço público, e entrega o lado do repositório como v0.14.0. A marca, um novo comando
> `citizen`, o ID do plugin e o slug do repositório mudam; nomes em disco, IDs `AH-` e registros
> datados mantêm `agent-harness`, `harness` continua como um apelido, e o GitHub mais um 301 do
> CloudFront carregam todo link antigo.
> **Esforço** ~3 dias úteis, cerca de 12 PRs em 5 repositórios · **Risco** médio — usuários do
> plugin precisam reinstalar · **Raio de impacto** instalações do plugin, links antigos, checks com
> chave no slug
> **Mudou nesta rodada.** O passo 6 adiciona um banner "formerly agent-harness" no site inteiro · o
> passo 1 encontrou uma marca de podcast dos EUA na classe 9 e o Jake escolheu seguir em frente · a
> Decisão 2 foi fechada: a renomeação entra dentro da v0.14.0.

## Em resumo

- **Resultado** — Toda superfície viva diz Model Citizen, `citizen` roda tudo que `harness` faz,
  model-citizen.dev serve o site por HTTPS, URLs antigas redirecionam, e a v0.14.0 sai sob o novo
  nome.
- **Abordagem** — Mudar 209 arquivos vivos e manter 666 datados ou em disco; renomear no GitHub;
  delegar o domínio para o Route 53 e fazer 301 do host antigo; texto voltado para fora só sai com
  a aprovação do Jake item por item.
- **Toca** — Este repositório, seu site, jakeselby-com, ruleprobe e seu site; GitHub; GoDaddy e
  Route 53; divulgação e a própria configuração do mantenedor, rastreadas fora deste repositório.
- **Novas dependências** — Nenhuma. Uma zona hospedada do Route 53 para model-citizen.dev.
- **Fora de escopo** — Renomear caminhos em disco, `~/repos/agent-harness`, IDs `AH-`, o
  `service.name` da telemetria ou registros datados; publicar no PyPI ou npm (nada publica hoje, e
  um placeholder está ocupando o nome); editar posts já publicados.
- **Teste de saída** — Uma nova regra de lint encontra a marca e o slug antigos só na sua lista de
  permissões; URLs antigas do repositório e do site fazem 301; model-citizen.dev retorna 200; o
  gate, `sync_about.py --check`, a verificação de desvio e a verificação de cartão estão verdes.
- **Pergunta em aberto** — Nenhuma. A Decisão 2 está fechada (dentro da v0.14.0); 1, 3, 4 e 5 ficam
  como recomendado.

## Design do sistema

```text
 PRs A-D ── *citizen, *plugin ID, *copy, *slugs ──▶ main ──▶ *v0.14.0
 GitHub agent-harness ── *rename; old URLs 301 ──▶ *model-citizen
 GoDaddy ── *NS delegation ──▶ *Route 53 zone model-citizen.dev
 *zone ── ACM cert, alias records ──▶ CloudFront site (same stack)
 agent-harness.jakeselby.com ── *301 by Host ──▶ model-citizen.dev
 product.json ── sync_about --apply ──▶ About: homepage, topics
 jakeselby.com card, ruleprobe ── *copy and links ──▶ new name
 outreach ┄┄ maintainer's go per item ┄┄▶ new name
 on-disk names, AH- IDs, telemetry, dated records ── kept ──▶ as is
```

`*` = novo ou alterado. O site mantém seu bucket, sua distribuição e sua stack; só nomes, aliases e
o certificado se movem.

## Passos

1. **[Reexaminar o nome e rodar as verificações negativas da UE e do Reino Unido](#passo-1--reexaminar-o-nome)**
   — registros, TSDR, TMview, UKIPO; somente leitura.
   *Saída:* todo nome continua livre e nenhuma marca idêntica ao vivo está nas classes 9 ou 42, ou
   o plano para aqui.
2. **[Delegar model-citizen.dev para o Route 53](#passo-2--delegar-o-domínio)** — deploy só da
   zona em agent-harness-site (G1); servidores de nome no GoDaddy pelo Jake (G2).
   *Saída:* `dig +short NS model-citizen.dev @8.8.8.8` retorna os quatro servidores `awsdns`.
3. **[Registrar as issues da renomeação e emendar o corpus](#passo-3--issues-e-corpus)** —
   `bmad-correct-course`, um épico e cinco histórias no marco v0.14.0.
   *Saída:* `python3 scripts/bmad_issue_sync.py audit` está limpo e a issue de cada história está
   no marco v0.14.0.
4. **[PR A: `citizen` com `harness` como apelido. PR B: ID do plugin](#passo-4--pr-a-e-pr-b)** —
   `bin/`, `lib/`, `policy/hooks/`, `.claude-plugin/`, doctor, testes.
   *Saída:* `bin/citizen doctor` e `bin/harness doctor` concordam, o doctor reconhece os dois IDs
   de plugin, e o gate está verde.
5. **[PR C: texto vivo](#passo-5--pr-c-texto-vivo)** — README, docs, product.json, AGENTS.md,
   primitivos e suas projeções, as emendas do BMad.
   *Saída:* `git grep -n 'Agent Harness'` fora da lista de permissões imprime só as linhas
   "Formerly"; `bin/harness generate --check` passa.
6. **[Servir o site em model-citizen.dev](#passo-6--site-e-marca)** — certificado, aliases, um 301
   baseado em Host, `site` do Astro, um banner "formerly agent-harness" em toda página, o cartão OG
   e uma marca nominativa (G3, G22).
   *Saída:* o ápice retorna 200; o host antigo e o www retornam 301 para o mesmo caminho no ápice;
   a verificação de fumaça encontra o banner em toda página.
7. **[Renomear no GitHub, corrigir slugs, lançar a v0.14.0](#passo-7--trocar-e-lançar)** — G4, PR D
   com a regra de lint de nome aposentado, About (G7), tag (G8), reancoragem do site e cartão (G9).
   *Saída:* URLs antigas fazem 301, `sync_about.py --check` e `advance_stable.py --check` passam, e
   o site serve a v0.14.0.
8. **[Divulgação](#passo-8--divulgação)** — listagens públicas e anúncios, rastreados fora deste
   repositório.
   *Saída:* toda listagem pública mostra o novo nome e link.

## Decisões para o revisor

> **1. Comando: tornar `citizen` o comando e manter `harness` como um apelido permanente?**
> *Recomendação* sim — nenhum pacote do Homebrew, PyPI ou npm instala um binário `citizen`,
> `harness` colide com o CLI da Harness Inc., e adicionar um comando é um minor; remover `harness`
> precisaria de um major mais 90 dias de aviso, então não anuncie nenhuma descontinuação.
> *Alternativa* manter só `harness` — zero atrito, mas a marca e o comando nunca combinam.

> **2. Versão e momento: entregar a renomeação dentro do marco v0.14.0 completo, como um minor?**
> *Recomendação* sim — a v0.14.0 é o marco Switchable do roteiro e a v0.15.0 é o Measured, então
> tirar issues dali colidiria com isso; o repositório, o site e os registros ainda trocam antes de
> 2026-09-30, e só a tag e o anúncio esperam.
> *Alternativa* cortar a v0.14.0 em torno da renomeação assim que seus PRs mesclarem, e renumerar os
> marcos do roteiro subindo um.
> *Decidido* dentro da v0.14.0 (Jake, 2026-09-25).

> **3. Domínios: servir o site no ápice model-citizen.dev, e pular um backorder em
> modelcitizen.dev?**
> *Recomendação* sim — o slug com hífen é o nome em todo lugar, o www e o host antigo fazem 301
> para o ápice, e um backorder só compensa se o dono deixar expirar (expira em 2026-10-28 na
> Dynadot).
> *Alternativa* servir em docs.model-citizen.dev para guardar o ápice para uma página de destino
> futura, e fazer o backorder como seguro barato contra um squatter de erro de digitação.

> **4. Descoberta e lançamento: manter o tópico `agent-harness`, e anunciar a renomeação uma vez
> junto com a v0.14.0 no X e no LinkedIn, dobrando junto a thread não postada da v0.13?**
> *Recomendação* sim — "agent harness" é a categoria que as pessoas pesquisam, então troque
> `coding-agent` (quase duplicado de `ai-coding-agent`) por `model-citizen`; um único lançamento
> vale mais que uma thread sob um nome aposentado uma semana depois.
> *Alternativa* descartar o tópico antigo para um corte limpo, e postar a thread da v0.13 já
> renomeada agora com um post de renomeação separado.

> **5. Marca registrada: rodar as verificações negativas da UE e do Reino Unido no passo 1 e não
> registrar nada ainda?**
> *Recomendação* sim — a triagem nos EUA está livre nas classes 9 e 42, e a verificação e o registro
> custam dinheiro de verdade antes de haver usuários para proteger.
> *Alternativa* uma verificação de advogado e um registro de intenção de uso nos EUA em 9 e 42
> agora, o que trava uma data de prioridade antes que outra ferramenta de agente pegue o nome.

## Riscos

- **O Claude Code mantém instalações existentes no ID de plugin antigo** — o doctor reconhece os
  dois IDs e avisa quando os dois estão ativados, e as notas de lançamento carregam os passos de
  reinstalação.
- **A delegação de servidor de nome ou a validação de certificado emperra** — o certificado só faz
  deploy quando `dig NS` mostra o Route 53, e o host antigo continua servindo até lá.
- **Uma verificação com chave no slug antigo fica quieta** (desvio do site, verificação de cartão)
  — cada uma é mudada antes da renomeação e rodada de novo depois dela no passo 7.

---

# Anexo

Tudo que o agente que implementa precisa e o revisor não. Nada acima da regra é repetido aqui.
Números G são os itens voltados para fora com portão em
[Passos com portão voltados para fora](#passos-com-portão-voltados-para-fora).

## Regras de trabalho para a construção

- Cada item G precisa da aprovação do Jake só para aquele item. Aprovar este plano não aprova
  nenhum deles. Mostre o texto ou comando exato, depois espere. Ele também pediu para ser
  consultado antes de qualquer submissão de listagem ser registrada, mesmo dentro de um plano
  aprovado.
- Deploys têm portão por instância, sempre. Uma tag, um lançamento e `sync_about.py --apply`
  mantêm suas próprias aprovações.
- Ações consequentes (commit, push, merge, deploy) passam pela verificação de confiança e são
  registradas, conforme as regras globais. Nenhum agente gradua confiança.
- Texto em nome do mantenedor, incluindo corpos de PR e issue, não carrega travessão longo.
- A entrega segue `docs/bmad-governance.md`: uma issue por PR, reservada em
  `_bmad-output/issue-map.json`, `Closes #N` no corpo, CodeRabbit trabalhado conforme o AGENTS.md.
- Nunca crie um repositório chamado `agent-harness` depois da G4; isso quebraria todo redirecionamento.

## Passo 1 — Reexaminar o nome

A triagem tem um dia, e ferramentas de agente reivindicam nomes mensalmente, então rode-a de novo
antes de qualquer coisa pública.

- Registros, códigos esperados: `curl -s -o /dev/null -w '%{http_code}\n' <url>` para
  `https://pypi.org/pypi/model-citizen/json` (404), `https://registry.npmjs.org/modelcitizen` (404),
  `https://github.com/JakeSelby/model-citizen` (404). O `model-citizen` do npm está ocupado e fica
  fora de escopo.
- EUA: rode de novo a verificação negativa em
  `.agent-harness/diagrams/brand/naming-trademark-screen.md` (checkout principal, não rastreado).
  `https://tsdr.uspto.gov/statusview/sn<serial>` funciona com curl onde uspto.report e Justia
  retornam 403. Conhecido: 90977894 MODEL CITIZEN está morto (classe 41); 88899582 MODEL CITIZENS
  está vivo na classe 35 (um clube de carros), fora de 9 e 42.
- UE e Reino Unido: TMview (`tmdn.org/tmview`) busca por palavra "MODEL CITIZEN", classes 9 e 42,
  marcas vivas em todo o EUIPO e os escritórios nacionais; UKIPO "search for a trade mark" por
  palavra. Os dois têm bastante script; conduza-os com Playwright (Chromium está instalado) ou
  entregue ao Jake as duas buscas.
- Registre os resultados no arquivo de triagem. Regra de parada: uma marca idêntica ou
  confusamente parecida ao vivo na classe 9 ou 42 nos EUA, na UE ou no Reino Unido interrompe o
  plano e vai para o Jake com o registro.
- **Resultado, 2026-09-25:** EUA 99552170 MODEL CITIZEN está vivo nas classes 9 e 41 para
  podcasts; a UE está livre; o registro do Reino Unido não foi verificado (CAPTCHA). Jake escolheu
  seguir em frente, e a busca manual no Reino Unido é opcional.

## Passo 2 — Delegar o domínio

- Em agent-harness-site, `infra/lib/agent-harness-site-stack.ts`, adicione uma
  `route53.PublicHostedZone` para `model-citizen.dev` e um `CfnOutput` de seus servidores de nome.
  Mantenha o nome da stack `AgentHarnessSite` e todo ID de construct existente: um ID alterado
  substitui o bucket ou a distribuição.
- G1 faz deploy só da zona. G2 é a mudança de servidor de nome do Jake. A delegação pode levar até
  48 horas, então comece os dois no primeiro dia, em paralelo com o passo 3.
- Hoje o domínio está nos servidores de nome padrão do GoDaddy com uma página de estacionamento;
  HTTPS falha, e .dev tem HSTS pré-carregado, então nada serve até o passo 6.

## Passo 3 — Issues e corpus

- Rode o `bmad-correct-course` no sprint v0.14.0. A proposta registra a renomeação, a lista de
  manutenção em [Inventário](#inventário) e o reescopo da Decisão 2.
- Depois `bmad-create-epics-and-stories`, e registre cada um com
  `python3 scripts/bmad_issue_sync.py new`. `new` relata "filed but not reserved" por atraso da
  listagem; siga com `reserve --issue N`. Reserve um de cada vez: duas reservas em andamento
  entram em conflito em `issue-map.json`, e a correção é reaplicar a entrada no formato JSON da
  ferramenta e rodar `audit`. Linke cada história ao épico como uma sub-issue pela API antes de
  mesclar.
- O épico, "Rename the product to Model Citizen", e cinco histórias, cada uma um PR com um rótulo
  `type::*` e o marco v0.14.0:
  - **S0, chore** — registra a mudança de sprint e reserva as histórias. Um PR só de registro
    falha em `issue-ownership` sem sua própria issue de chore.
  - **S1, feature** — adiciona o comando `citizen` e mantém `harness` como apelido (PR A).
  - **S2, feature** — renomeia o plugin para `model-citizen` e continua reconhecendo o ID antigo
    (PR B).
  - **S3, docs** — renomeia o texto do produto para Model Citizen (PR C).
  - **S4, chore** — aponta links fixos para o novo repositório e domínio, e adiciona a regra de
    lint de nome aposentado (PR D, depois da G4).
- Emendas, cada uma através da intenção de atualização da skill correspondente com uma entrada de
  memlog, no PR que torna o documento desatualizado: o resumo do produto (nome, e a linha de
  posicionamento assim que o Jake escolher uma) e o PRD (nome do produto, e texto de FR nomeando o
  comando) no PR C; a especificação de UX (nome do comando na saída) no PR A; a espinha dorsal de
  arquitetura ganha uma AD na S0: a marca é Model Citizen, enquanto nomes em disco, IDs `AH-`, o
  `service.name` da telemetria e registros datados mantêm `agent-harness`. Nomes de diretório como
  `prd-agent-harness-2026-09-23/` ficam, já que centenas de âncoras apontam para dentro deles.
- G6 foi descartado: a Decisão 2 mantém a renomeação dentro do marco v0.14.0 completo.

## Passo 4 — PR A e PR B

**PR A (S1).**
- `bin/citizen` é um link simbólico relativo para `harness`. `bin/harness` continua sendo o
  arquivo real, porque os hooks e o instalador encontram o checkout por esse caminho
  (policy/hooks/harness-session.py:65,100,153,251; policy/hooks/decisions.py:297;
  policy/hooks/usage-log.py:169; scripts/install.sh:66,80), e recusas de ciclo de vida imprimem
  seu caminho absoluto (lib/harness_core/lifecycle.py:180-183).
- `prog` vem do basename de `argv[0]`, `citizen` ou `harness`, senão `citizen`
  (bin/harness:4844); o docstring de uso (:10-29) começa com `citizen`.
- O banner `agent-harness {VERSION}` torna-se `model-citizen {VERSION}` em bin/harness
  :4845,1818,1243,2834,2913,3220; atualize tests/test_harness.py:542.
- Mensagens em `bin/`, `lib/` e `policy/hooks/` que nomeiam o produto ou sugerem um comando movem
  para Model Citizen e `citizen`. Todo caminho na lista de manutenção fica como está.
- Testes (seguros para Python 3.9): `bin/citizen --help` imprime `usage: citizen` e
  `bin/harness --help` imprime `usage: harness`; os dois `--version` imprimem
  `model-citizen <VERSION>`; a detecção de checkout funciona pelos dois nomes.
- Fragmento `changelog.d/<issue>.added.md`: "Added the `citizen` command; `harness` remains a
  supported alias." O corpo carrega `Landing copy: command examples move to citizen in the copy
  PR, #<S3>`.

**PR B (S2).**
- `.claude-plugin/plugin.json` e `marketplace.json`: `name` do plugin e `name` do marketplace
  `model-citizen`, displayName `Model Citizen`, descrições. URLs mudam no PR D, depois da G4.
- O doctor (bin/harness:1600-1640) aceita `agent-harness@agent-harness` e
  `model-citizen@model-citizen` como a chave ativada e qualquer um dos nomes de marketplace, e
  avisa quando os dois estão ativados, já que as skills carregariam duas vezes.
- docs/runtime-installation.md:97-104 recebe os passos de instalação e migração de
  [Migração](#migração-para-instalações-existentes).
- tests/test_plugin_manifests.py: só o ID antigo, só o novo ID, e os dois ativados.
- Antes de mesclar, em um perfil descartável (perfil vazio logado, cwd fora de `$HOME`, ambiente
  limpo), instale a partir do marketplace da v0.13.1, atualize para este branch, e registre se o
  Claude Code mantém o ID antigo. O resultado vai nas notas de lançamento.
- Fragmento `changed`: "The plugin is now `model-citizen@model-citizen`; reinstall it."

## Passo 5 — PR C, texto vivo

- O texto de marca torna-se Model Citizen no README.md, CONTRIBUTING.md, no título do AGENTS.md,
  nas páginas vivas de docs/ (não docs/plans/), no `hero.subtitle` do product.json, em
  primitives/instructions.md:3 (depois `bin/harness generate` para claude/CLAUDE.md:3), em
  codex/config.toml.example:1, no `aria-label` de docs/assets/brand/mark.svg, e no título de
  lançamento em .github/workflows/release.yml:31.
- Exemplos de comando tornam-se `citizen <subcommand>` no README, em docs/, no product.json
  (:9,71,167,172,204,233), em primitives/ e templates/. O bloco Gate do AGENTS.md e o CI mantêm
  `bin/harness`, então os dois continuam idênticos.
- O substantivo de categoria em minúsculas ("an agent harness", "the harness") fica.
- primitives/skills/harness-authoring/SKILL.md:23,80 escreve `<owner>/model-citizen`; o lint
  proíbe o nome do mantenedor ali.
- Recapture docs/assets/sync-dry-run.svg como `bin/citizen sync --dry-run`, o método que a
  AH-S116 usou.
- Uma linha "Formerly Agent Harness" no README e no índice da documentação, para que buscas
  cheguem lá.
- Fragmento `changed`: "Renamed the product to Model Citizen."

## Passo 6 — Site e marca

- `infra/lib/agent-harness-site-stack.ts`: o domínio (:16) torna-se `model-citizen.dev`. O
  certificado (:42-44) cobre `model-citizen.dev`, `www.model-citizen.dev` e
  `agent-harness.jakeselby.com`, validado com `CertificateValidation.fromDnsMultiZone`: a nova
  zona para os dois primeiros, a zona jakeselby.com (:37-39) para o terceiro. Aliases (:81)
  adicionam os novos nomes e mantêm os antigos. Adicione registros de alias A e AAAA para o ápice
  e o www na nova zona; mantenha o registro do host antigo (:116-120).
- O 301 entra na `RoutingFunction` de viewer-request já existente (:59-91), já que uma
  distribuição usa uma função por tipo de evento: quando `host` não é `model-citizen.dev`, retorna
  301 para `https://model-citizen.dev` mais a URI e a query string.
- `astro.config.mjs:17` define `site` como `https://model-citizen.dev`.
- O banner: um `<aside aria-label="Name change">` fino no site inteiro acima do cabeçalho em
  `src/layouts/Layout.astro`, em toda página, sem controle de dispensa e sem script. Texto (G22):
  "Model Citizen was formerly agent-harness: same project, new name.", linkando para o
  repositório. `scripts/smoke.mjs` reprova qualquer página construída sem ele, e ele passa no
  gate de contraste do design loop. Ele é entregue junto com a própria renomeação do site neste
  passo, não antes, porque até lá toda página ainda diz Agent Harness. Fica até o Jake removê-lo.
- A marca nominativa e o cartão OG passam pelo `design-loop` (designer, depois design-judge): uma
  marca nominativa Model Citizen ao lado do mostrador âmbar e um `og.png` de 1200x630. Rode
  `licensing-review` na fonte tipográfica antes de qualquer glifo delineado ser entregue. O
  favicon do mostrador fica.
- G3 faz deploy assim que a delegação resolver. Comandos de saída:
  `curl -sI https://model-citizen.dev/` (200),
  `curl -sI https://agent-harness.jakeselby.com/docs/` e `curl -sI https://www.model-citizen.dev/`
  (301, `location: https://model-citizen.dev/docs/` e `/`).

## Passo 7 — Trocar e lançar

Em ordem, em uma única sentada:

1. G4 renomeia o repositório. Depois verifique os redirecionamentos:
   `gh api repos/JakeSelby/agent-harness -q .full_name` imprime `JakeSelby/model-citizen`, e
   `git ls-remote https://github.com/JakeSelby/agent-harness.git refs/heads/main` combina com o
   novo repositório. G5 (opcional) renomeia o repositório do site da mesma forma.
2. PR D (S4) muda o slug em scripts/release_notes.py:29, scripts/bmad_issue_sync.py:1618,
   scripts/install.sh:8,21, .github/ISSUE_TEMPLATE/config.yml:4,7, README.md:5,9,148,160,
   CONTRIBUTING.md:40,42,56, docs/runtime-installation.md:97, tests/test_plugin_manifests.py:63,108,
   e os `homepage` e `repository` do plugin e do marketplace. Muda a URL do site em README.md:8,
   docs/releasing.md:8 e plugin.json:8. product.json ganha
   `"homepage": "https://model-citizen.dev"` (suportado em scripts/sync_about.py:55-57) e troca
   `coding-agent` por `model-citizen` nos topics (o teto é 20); tests/fixtures/gh/repo-view.json
   segue junto. `_bmad-output/issue-map.json:3` mantém o slug antigo: `planning_block` o escreve em
   todo corpo de issue (scripts/bmad_issue_sync.py:649-663,719), então mudá-lo reescreveria 160
   issues. A regra de lint `retired-name` reprova "Agent Harness", o slug antigo e o host antigo
   fora de uma lista de permissões (as áreas datadas, os nomes em disco e as linhas "Formerly"),
   com seu teste. O PR D é o primeiro PR depois da renomeação, então confirme que o CodeRabbit
   ainda posta uma passada.
3. G7 aplica o About, depois `python3 scripts/sync_about.py --check`.
4. Lança a v0.14.0 através de `docs/releasing.md` e as cinco superfícies do AGENTS.md: evidência
   nativa fresca para todo cliente obrigatório, o catálogo, a dobra do changelog, notas de
   lançamento cujas ações e recuperação carregam os passos de migração, preflight num clone fresco
   da nova URL, a tag (G8), o workflow de lançamento, e `scripts/advance_stable.py --check`.
5. Superfícies de lançamento. Site: reancorar para
   v0.14.0, apontar `scripts/drift.mjs:11,84` e `.gitmodules:3` para o novo slug, depois
   `git submodule sync`. Cartão, em jakeselby-com: `src/data/agent-harness.ts` (nome e links; o
   nome do arquivo fica), `src/pages/index.astro:83,224`, `src/pages/projects/index.astro:81`, o
   301 de `/agent-harness` (stack de infra :78-84) agora para `https://model-citizen.dev` mais um
   caminho `/model-citizen`, e `scripts/harness-card-check.mjs:16`; G9 faz o deploy.
6. ruleprobe README.md:756 e as duas linhas do ruleprobe-site, cada uma um PR pequeno sob as
   próprias regras daquele repositório.

## Passo 8 — Divulgação

Divulgação (os registros de listagem aberta, o anúncio, links de perfil) e a própria configuração
do mantenedor são rastreadas fora deste repositório. Cada item voltado para fora é G10 a G19
abaixo, cada um com sua própria aprovação.

## Passos com portão voltados para fora

Cada um precisa da aprovação do Jake só para aquele item. Itens só de humano são dele para
executar, com o texto abaixo.

- **G1, fazer deploy da zona** — `cd ~/repos/agent-harness-site/infra && npx cdk diff AgentHarnessSite && npx cdk deploy AgentHarnessSite`, com o diff mostrando só a nova zona e a saída.
- **G2, servidores de nome (Jake, GoDaddy)** — model-citizen.dev → DNS → Nameservers → Change → "I'll use my own nameservers", depois os quatro valores de `aws route53 get-hosted-zone --id <zone-id> --query DelegationSet.NameServers`.
- **G3, fazer deploy do certificado, aliases e 301** — o comando da G1, depois de
  `dig +short NS model-citizen.dev @8.8.8.8` retornar esses quatro.
- **G4, renomear o repositório** — `gh repo rename model-citizen -R JakeSelby/agent-harness --yes`.
- **G5, renomear o repositório do site (opcional, recomendado)** —
  `gh repo rename model-citizen-site -R JakeSelby/agent-harness-site --yes`.
- **G6, reescopar o marco** — descartado; a Decisão 2 mantém a v0.14.0 completa.
- **G7, About** — `python3 scripts/sync_about.py --apply`.
- **G8, tag** — a tag anotada `v0.14.0` e o push conforme `docs/releasing.md`, depois do preflight
  num clone fresco.
- **G9, fazer deploy do cartão** — `cd ~/repos/jakeselby-com && npm run deploy`.
- **G10 a G19, divulgação** — os registros de listagem aberta, o diretório de plugins, uma resposta
  de e-mail, o anúncio e links de perfil; rastreados fora deste repositório, cada um com a
  aprovação do mantenedor.
- **G20, backorder de modelcitizen.dev** — só se a Decisão 3 for para a alternativa.
- **G21, verificação e registro de marca registrada** — só se a Decisão 5 for para a alternativa.
- **G22, o texto do banner do site** — "Model Citizen was formerly agent-harness: same project,
  new name.", linkando para o repositório; com a aprovação do mantenedor antes de ser entregue.

## Inventário

Arquivos rastreados na main `a9968d9`, como linhas e arquivos combinados por `git grep`:

- **"Agent Harness", 59 linhas em 34 arquivos** — muda as 14 linhas vivas (README, docs,
  product.json, `.claude-plugin/`); mantém 45 em `_bmad-output/`, que são registros datados.
- **"agent harness" em minúsculas, 17 em 9** — mantém: o substantivo de categoria ainda descreve o
  produto.
- **`JakeSelby/agent-harness`, 4.117 em 585** — muda cerca de 70 linhas vivas no PR D; mantém 4.045
  em `_bmad-output/` e no mapa de issues, que o GitHub redireciona.
- **`agent-harness.jakeselby.com`, 6 em 5** — muda para `https://model-citizen.dev`.
- **`agent-harness@agent-harness`, 7 linhas** — muda para `model-citizen@model-citizen`; o doctor
  aceita os dois.
- **O banner `agent-harness {VERSION}`, 6 lugares em bin/harness** — muda.
- **Texto `harness <subcommand>`, 1.344 em 371** — muda em cerca de 156 arquivos vivos (docs 27,
  primitives 19, policy 12, claude 11, lib 9, templates 5, raiz 5, scripts 4, outros); mantém as
  607 linhas em `_bmad-output/`, as 123 em evidência de compatibilidade fixada por sha256, e
  invocações de teste.
- **`bin/harness`, 684 em 257** — mantém: é o caminho do apelido e o arquivo real.
- **`~/.config/agent-harness` (44 em 23), `.agent-harness/` (163 em 74),
  `~/.local/state/agent-harness/`** — mantém: uma renomeação precisaria de uma migração automática
  reversível ou um major mais 90 dias de aviso.
- **launchd `com.agent-harness.*`, marcadores `# harness:`, o bloco de PATH e de ignore
  `# agent-harness`, CODEX_BANNER, `~/.claude/{rules,hooks}/harness`** — mantém: instalação,
  desinstalação e reconciliação os encontram por texto exato
  (remote_control.py:160,183; bin/harness:1126-1155,1470; reconcile.py:98; lifecycle.py:625).
- **Telemetria `service.name="agent-harness"`** (policy/hooks/telemetry.py:41) — mantém, para que
  dashboards existentes ainda combinem.
- **`project_name` do BMad, os IDs `AH-`, os caminhos `prd-agent-harness-…` e
  `architecture-agent-harness-…`** — mantém: IDs e centenas de âncoras dependem deles.
- **`agent_harness` e `AGENT_HARNESS_*`** — nenhum; as variáveis de ambiente são `HARNESS_*` e
  ficam.
- **Totais** — 209 arquivos vivos mudam; 666 arquivos em áreas datadas ou mantidas ficam.
- **agent-harness-site** — 9 linhas de marca, 14 de slug e 17 de URL do site, 111 com caminhos:
  domínio, certificado, aliases, `site` do Astro, mudança de slug de desvio e URL de submódulo; a
  stack, os IDs de construct e os nomes de arquivo ficam.
- **jakeselby-com** — 12 linhas de marca, 4 de slug e 3 de URL do site: o cartão, os dois locais, o
  301 de `/agent-harness` e a verificação de cartão mudam.
- **ruleprobe** — 27 linhas de slug, majoritariamente em `_bmad-output/`: README.md:756 muda; o
  resto redireciona. **ruleprobe-site** — 2 linhas em testes e CLAUDE.md mudam.
- **GitHub** — a homepage do About e o tópico `agent-harness` (Decisão 4); nenhuma prévia social
  personalizada, então o cartão gerado pelo GitHub segue a renomeação; 151 das 160 issues abertas
  mencionam o nome, quase todas através do bloco de planejamento do BMad, e ficam; o único título
  da v0.14.0 que o nomeia (#825) fica.
- **Divulgação e a própria configuração do mantenedor** — rastreadas fora deste repositório.

## Sequenciamento contra a v0.14 e os prazos

- **Antes da tag:** passos 1 a 6, depois G4, PR D e G7. Ordem dos PRs: S0 primeiro, depois A, B e
  C (C depois de A, para que seus exemplos rodem), depois D depois da G4. Site: a zona (passo 2) no
  primeiro dia; o certificado e o 301 (passo 6) assim que a delegação resolver.
- **A tag:** depois do PR D e da G7, através do PR de lançamento em `docs/releasing.md`.
- **Depois da tag:** a reancoragem do site e o cartão (G9), o ruleprobe, e a divulgação (G10 a
  G19).
- **Metas, a partir da aprovação na sexta-feira 2026-09-25:** G1 e G2 no primeiro dia, já que a
  delegação é o gargalo mais longo; PRs A a C e o passo 6 até 2026-09-29; G4, PR D, G7 e a tag em
  2026-09-29 ou 2026-09-30; edições de divulgação logo depois da G4.
- **Os prazos:** o awesome-claude-code tem portão na G4 e no passo 6, não numa data, então sempre
  que o Jake o registrar, entra sob o novo nome. A thread da v0.13 não é postada antes da G18. Com
  a Decisão 2 como recomendada, o repositório, o site e os registros ainda trocam nesse
  cronograma, e só G8, G9 e G18 esperam pelo marco.

## Migração para instalações existentes

- **Instalações por checkout** — nada a fazer. `git pull` segue o redirecionamento; `bin` já está
  no `PATH` através do bloco `# agent-harness`, então `citizen` aparece; configuração, estado e
  marcadores ficam inalterados. `git remote set-url origin https://github.com/JakeSelby/model-citizen.git`
  é opcional.
- **Instalações por plugin** — `/plugin marketplace add JakeSelby/model-citizen`,
  `/plugin install model-citizen@model-citizen`, `/plugin uninstall agent-harness@agent-harness`,
  `/plugin marketplace remove agent-harness`. Skills se movem de `/agent-harness:<skill>` para
  `/model-citizen:<skill>`. O doctor avisa enquanto os dois estão ativados.
- **As notas de lançamento** carregam isso como ações. Recuperação: a instalação por checkout não é
  afetada pela mudança do plugin.

## Contexto e histórico

"Agent harness" está se tornando um substantivo de categoria, usado genericamente pela Anthropic,
LangChain, OpenAI e outros. Depois de sete rodadas de nomeação, o Jake escolheu Model Citizen em
2026-09-25 e comprou model-citizen.dev no GoDaddy no mesmo dia. O posicionamento, em suas
palavras: "We want agents to become autonomous, but to make them so we have to be able to measure
their behavior and ensure that they are model citizens." Linhas candidatas, nenhuma aprovada:
"Autonomy, earned."; "Agents you can count on."; "Find out whether your models are model
citizens."; "Proof your agents kept the rules." `citizen` e "Agents you can count on" vieram do
assistente, não do Jake.

A revisão de raio de impacto da primeira sessão de renomeação recomendou renomear a marca e o ID
do plugin, manter os nomes em disco e `~/repos/agent-harness` (renomeá-lo quebra 46 links
simbólicos e 37 pastas de projeto e órfa o diretório de memória), adicionar um novo comando ao
lado de `harness`, e terminar antes do registro no awesome-claude-code e da thread da v0.13. Este
plano verifica cada um desses pontos contra o código e `docs/compatibility-policy.md`. A promessa
de SemVer da política começa na v1.0.0 (:10). Comandos `harness` documentados são estáveis (:12), e
um minor pode adicionar comandos compatíveis com versões anteriores (:37). Remover um precisa de
um aviso, o próximo major e 90 dias (:49-55). Texto legível por humanos não é estável (:22). O ID
do plugin e o slug do repositório não estão listados.

## Evidência e verificação

- **Verificado em 2026-09-25:**
  - A main local é igual à origin em `a9968d9`. Contagens são `git grep` sobre arquivos
    rastreados.
  - Nenhuma fórmula ou cask do Homebrew, pacote do PyPI ou pacote do npm instala um binário
    `citizen`. O `citizen` 1.0.2 do npm é uma biblioteca sem bin.
  - O `model-citizen` do PyPI e o `modelcitizen` do npm retornam 404; o `model-citizen` do npm
    está ocupado; `JakeSelby/model-citizen` retorna 404.
  - model-citizen.dev: servidores de nome do GoDaddy e uma página de estacionamento, HTTPS
    falhando; criado em 2026-09-25, expira em 2027-09-25, conforme o RDAP. modelcitizen.dev:
    Dynadot, expira em 2026-10-28.
  - agent-harness.jakeselby.com é CloudFront atrás da zona jakeselby.com do Route 53.
  - Marco v0.14.0 (#18): 39 abertas, 32 fechadas, sem data de vencimento. O último lançamento é a
    v0.13.1. O About não tem prévia social personalizada.
  - Os cinco registros estão abertos sem comentários.
- **Não verificado:**
  - O comportamento do Claude Code quando um plugin ou marketplace é renomeado; o passo 4 testa
    isso.
  - Os registros da UE e do Reino Unido; o passo 1 os verifica.

## Adiado, e por quê

- **Registros de pacote** — nada publica hoje: não há pyproject.toml nem package.json, e
  release.yml só cria o lançamento no GitHub. Um placeholder no PyPI é ocupação de nome sob o PEP
  541, então `model-citizen` no PyPI e `modelcitizen` no npm esperam pelo primeiro pacote de
  verdade.
- **Nomes em disco, o caminho de checkout local, IDs `AH-` e o slug do mapa de issues** —
  mantidos, pelas razões em [Inventário](#inventário).
- **Os campos `version` do plugin e do marketplace, travados em 0.11.1** — nada os verifica contra
  o VERSION; registre um acompanhamento para adicioná-los ao passo de versão do lançamento.
- **Um registro de marca registrada** — conforme a Decisão 5.
