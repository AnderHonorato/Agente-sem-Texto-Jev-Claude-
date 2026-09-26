# Como contribuir

Contribua para uma única autoridade de primitivos compartilhada sob `primitives/`. Preferências pessoais são
interruptores de política extensíveis; diferenças de runtime pertencem aos adaptadores, nunca duplique catálogos
de preferência ou de habilidade. [O contrato de autoria](docs/primitive-authoring.md), o [catálogo de compatibilidade](docs/compatibility.md)
e a [política de compatibilidade](docs/compatibility-policy.md) definem extensão, qualificação e o
contrato público estável. Regenere as projeções depois de mudar papéis ou workflows compartilhados.

Ideias são tão bem-vindas quanto patches. Se uma regra, preferência ou habilidade aqui deixou seu agente melhor ou
pior, diga isso. Se você tem uma correção, envie. Esta página diz onde as coisas vão e como a
revisão funciona.

## Duas formas de contribuir sem código

- **Uma ideia** — abra uma [issue de Ideia](../../issues/new?template=02-idea.yml) ou comece uma
  [Discussão](../../discussions). Diga o que você queria que o agente fizesse, o que ele fez em vez disso,
  e o que você tentou.
- **Uma regra, preferência ou habilidade proposta** — abra uma
  [issue de Regra ou habilidade](../../issues/new?template=03-rule-or-skill.yml) com o texto que você tem
  em mente e em qual degrau da escada abaixo ela se encaixa.

Qualquer coisa maior que a correção de um erro de digitação é melhor discutida primeiro. Um PR que chega depois de uma thread curta
quase sempre mescla mais rápido do que um que chega do nada.

## O fluxo fork → branch → pull request

Toda mudança, incluindo documentação, precisa de uma issue de entrega dedicada antes da implementação.
Cada PR fecha exatamente uma issue neste repositório com `Closes #N`; cada issue de entrega pertence
a um PR. Divida trabalho que exige múltiplos PRs em issues filhas. Referências contextuais a issues são
bem-vindas, mas não use palavras-chave de fechamento para elas. Um PR substituto só pode reaproveitar a issue
depois que o PR anterior fecha sem ser mesclado.

O check obrigatório `issue-ownership` valida os links de fechamento do GitHub e rejeita issues já
reivindicadas por um PR aberto ou mesclado. Ele roda na criação do PR, em edições do corpo, ao reabrir e em novos commits.
Rode-o de novo imediatamente antes de mesclar se os links de outro PR mudaram: o GitHub não fornece
uma restrição de unicidade atômica entre PRs, e a mudança de outro PR não consegue invalidar um check antigo.

1. Faça um fork e clone:
   ```sh
   gh repo fork JakeSelby/agent-harness --clone --remote
   cd agent-harness
   git remote -v        # origin = seu fork, upstream = JakeSelby/agent-harness
   ```
2. Mantenha o `main` do seu fork atualizado com o upstream, e ramifique a partir dele:
   ```sh
   git fetch upstream && git checkout main && git rebase upstream/main
   git checkout -b <topico-curto>
   ```
3. Faça a mudança. Rode os checks (próxima seção).
4. Faça o commit com uma mensagem no formato [Conventional Commit](https://www.conventionalcommits.org/):
   `docs(rules): fold the 403 line into working-style`, `feat(cli): add workspace create`,
   `fix(hook): treat dangling && as unparseable`.
5. Envie para o seu fork e abra o PR contra `main`:
   ```sh
   git push -u origin <topico-curto>
   gh pr create --repo JakeSelby/agent-harness --base main --fill
   ```
6. O CI roda o lint e os testes. Corrija qualquer coisa vermelha; o botão de mesclagem fica desabilitado até que os
   checks passem. Squash merge é o único método de mesclagem, e o título do PR vira a mensagem do
   commit, então faça do título uma boa linha de Conventional Commit.

Se você mesmo usa o harness, a habilidade `harness-authoring` roda os passos 2 a 5 para você de
dentro do seu runtime de agente selecionado.

## Checks para rodar antes de abrir um PR

```sh
bin/harness lint                       # sem strings pessoais, sem padrões de segredo
python3 -m unittest discover tests     # lógica de merge, link, configuração e lint
bin/harness sync --dry-run             # para mudanças de conteúdo: o plano de preferência e link ainda resolve
```

O CI roda exatamente isso (o dry run do sync contra a configuração de exemplo), e `citizen sync`
instala `.githooks/pre-commit` no checkout para que
todo commit seja "lintado" antes de existir. O lint é rigoroso de propósito e não carrega **nenhuma lista de
valores reais**: ele bate com formatos (ids de conta de 12 dígitos, endereços de e-mail, caminhos de diretório home,
ARNs de nuvem, ids de zona hospedada, tenants de provedor de identidade, IPs privados, padrões de segredo), deriva
o nome do mantenedor a partir de `LICENSE` e `CODEOWNERS` e o proíbe dentro de conteúdo instalado,
e lê seus próprios termos (empregador, cidade, hostnames) do arquivo não versionado
`~/.config/agent-harness/lint-terms.txt` (veja `lint-terms.example.txt`). Uma lista de valores
reais a evitar seria, ela mesma, uma exposição no momento em que fosse commitada; foi exatamente o que aconteceu
no primeiro lançamento, e por isso o design é assim.

## O que vai onde

Toda instrução tem um lar certo. A primeira correspondência vence:

1. **Precisa rodar num ponto do ciclo de vida independentemente do julgamento do modelo** → um hook sob
   `policy/hooks/` mais seu mapeamento de adaptador de ciclo de vida e testes.
2. **Configuração de ferramenta ou editor, não comportamento** → uma chave própria em
   `claude/settings.template.json` ou `vscode/settings.owned.json`, listada em
   `claude/OWNERSHIP.json`.
3. **Verdade sobre uma pessoa, uma máquina, ou um projeto** → não pertence a este repositório. Vai na
   configuração de harness daquela pessoa ou no `AGENTS.md` daquele repositório.
4. **Uma preferência que um engenheiro razoável poderia ter ao contrário** → uma variante sob
   `primitives/stances/<pref>/`, mais uma linha em `docs/preferences.md`. Licenciamento, estilo de commit,
   filosofia de teste e nível de autonomia são preferências.
5. **Um procedimento com passos, ou algo só necessário sob um gatilho** → uma habilidade sob
   `primitives/skills/<nome>/SKILL.md` com uma descrição que diz quando usá-la.
6. **Curto, genérico, desejado em todo turno** → `primitives/rules/<tópico>.md`. Regras custam o
   contexto de todo usuário em todo turno, então a barra é alta; o resultado normal é uma frase dobrada dentro de
   uma regra já existente. `CLAUDE.md` mais toda regra mais a variante mais longa de cada preferência tem teto de
   225 linhas e `bin/harness lint` aplica isso, então uma regra carrega suas linhas operativas e aponta
   para a habilidade que guarda o raciocínio.

## O que não será mesclado

- Qualquer coisa pessoal ou específica de projeto, por melhor que seja. Coloque na sua própria configuração de harness ou raiz de primitivo personalizado.
- Material com licença copyleft, share-alike ou sem licença, incluindo texto e trechos de código
  incorporados cuja origem você não consegue nomear. Veja `THIRD_PARTY_NOTICES.md` para como o único item derivado é registrado.
- Credenciais de qualquer tipo. O lint e a proteção de push do GitHub bloqueiam ambos, e um PR que
  aciona qualquer um dos dois é fechado.
- Uma regra que repete algo que já está no repositório. Faça um grep primeiro.
- Uma mudança em `bin/harness` ou num hook sem um teste.

## Mesclando um pull request (mantenedores)

`main` recebe pull requests através de uma fila de mesclagem e exige histórico linear, então uma mesclagem
segue um formato só. Cada linha aqui custou uma mesclagem quebrada antes de ser escrita.

- Uma mesclagem entra na fila. `gh pr merge --squash` ainda funciona: ele adiciona o pull request à fila,
  cujo próprio método de mesclagem (squash) decide como ele é aplicado. A fila constrói um branch temporário
  `gh-readonly-queue/main/pr-<n>-<sha>` contendo `main` mais toda entrada à sua frente, roda os
  checks obrigatórios ali, e mescla assim que ficarem verdes. A fila
  substitui o requisito de estar atualizado, então não há necessidade de mesclar `origin/main` num branch
  só para aplicá-lo. Quando um branch realmente precisa do `main` (um conflito), use
  `git merge --no-edit origin/main`, nunca um rebase ou um force-push.
- Uma falha na fila remove o pull request dela; as entradas atrás dele são reconstruídas
  sem ele e continuam. `gh pr view <n>` mostra que ele não está mais na fila, a linha do tempo do pull request
  diz que ele foi removido da fila de mesclagem, e a execução que falhou é listada por
  `gh run list --event merge_group`, num branch nomeado para o pull request. Corrija no
  branch e mescle de novo. Um check que nunca reporta no branch da fila trava a fila até seu
  tempo limite, e é por isso que todo workflow de pull request também roda em `merge_group`.
- Depois do 0.13.0, toda mudança sob `bin/`, `lib/`, `adapters/`, `primitives/`, `policy/`, `docs/`
  ou `scripts/` carrega um fragmento de changelog,
  `changelog.d/<issue-ou-pr>.<added|changed|removed|fixed>.md`, em vez de uma edição em
  `CHANGELOG.md`, então dois branches nunca entram em conflito sobre uma seção; veja
  [`changelog.d/README.md`](changelog.d/README.md). `bin/harness lint` reprova um branch sem um.
- Rode o portão e leia seu código de saída diretamente. `python3 -m unittest discover -s tests | tail -1`
  esconde uma suíte vermelha atrás do código de saída do `tail`; redirecione para um log e teste por `^OK`.
- `gh pr checks <n> --watch` retorna na hora quando nenhum check ainda se registrou, e uma mesclagem logo
  depois é recusada. Espere até `gh pr checks <n>` listar todo check obrigatório, então observe, depois
  `gh pr merge --squash` para entrar na fila. Nunca `--admin`.
- `scripts/bmad_issue_sync.py new` registra a issue e depois corre contra o endpoint de listagem. Quando ele imprime
  "not reserved", espere alguns segundos e rode `reserve --issue N --kind K --parent P`. Duas worktrees
  reservando ao mesmo tempo podem pegar o mesmo ID; mantenha a entrada do `main` e reserve de novo a outra issue.
- O lint de dados pessoais lê uma especificação npm com escopo e versão fixada (arroba, escopo, barra,
  nome, arroba, versão) como um endereço de e-mail, e sinaliza endereços de contato de terceiros citados em
  READMEs. Escreva "versão 1.2.3 do pacote npm" em vez disso, e limpe imports antes de dar stage.
- Nunca pule o hook de pre-commit, nem mesmo para uma primeira tentativa que você pretende refazer; um commit que
  pulou o lint continua sendo um commit.

## Revisão

Um mantenedor revisa todo PR, geralmente dentro de uma semana. Espere perguntas sobre em qual degrau a
mudança se encaixa e se ela é genérica. PRs pequenos e de assunto único são revisados mais rápido. O mantenedor
pode enviar pequenas edições para o seu branch antes de mesclar; você vai vê-las no PR.

O CodeRabbit também revisa todo PR para `main`, forks inclusos, uma vez quando ele abre, ou quando um rascunho é
marcado como pronto. Trate os comentários dele como trataria os de um revisor: envie uma correção, ou responda com o motivo
pelo qual uma não se aplica, depois resolva a thread, porque o `main` não mescla enquanto uma thread de revisão estiver aberta.
Comente `@coderabbitai review` para uma nova passada depois que você enviar. Os comentários dele são conselho, e onde
você discordar, o mantenedor decide.

## Licenciamento das contribuições

Ao abrir um pull request você concorda que sua contribuição é licenciada sob a licença MIT
deste repositório, sem termos adicionais, e confirma que tem o direito de contribuir com
ela. Os Termos de Serviço do GitHub já dizem o mesmo para qualquer repositório com um aviso de licença
("inbound = outbound", [seção D.6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#6-contributions-under-repository-license)):
"Sempre que você adiciona Conteúdo a um repositório contendo aviso de licença, você licencia esse
Conteúdo sob os mesmos termos, e concorda que tem o direito de licenciar esse Conteúdo
sob esses termos." Sem CLA, sem linha de assinatura.

Papéis e workflows compartilhados são escritos em `primitives/`, com vínculos nativos em `adapters/`.
Rode `bin/harness generate` depois de mudá-los; veja [autoria de primitivos](docs/primitive-authoring.md).
