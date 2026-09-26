# Coordene um lançamento do harness e suas superfícies públicas

Um lançamento é uma tag de origem verificada e o lançamento do GitHub publicado a partir dela. Um
build bem-sucedido não é qualificação nativa. `scripts/release_preflight.py` recusa a publicação
até que todo cliente obrigatório no catálogo de compatibilidade carregue evidência nativa. Todo
lançamento segue a [política de compatibilidade](compatibility-policy.md); notas geradas a linkam e
afirmam a revisão de migração ou a ação de migração versionada exata. O site de referência em
[agent-harness.jakeselby.com](https://agent-harness.jakeselby.com) acompanha lançamentos do seu
próprio repositório; nada neste procedimento o implanta.

## Quando um lançamento é proposto, e como é numerado

Lançamentos são feitos por marco (milestone). Toda issue destinada ao próximo lançamento carrega o
marco `v<next>`, o trabalho é mesclado livremente, e um lançamento é proposto quando esse marco
esvazia ou quando uma mudança visível ao usuário sem lançamento tem sete dias, o que vier primeiro.
Uma correção de regressão não espera por nenhum dos dois: ela lança na hora como um patch.

O número segue o que mudou, não onde a entrada aterrissou no changelog. Só correções é um patch.
Comportamento visível ao usuário adicionado ou mudado é um minor. Um major é decidido pela
[política de compatibilidade](compatibility-policy.md), que também define o que conta como uma
mudança que quebra compatibilidade. O que o lançamento precisa carregar antes de poder ser marcado
com tag é a próxima seção.

## Origem e qualificação

1. Complete cada caso de aceitação nativa em [compatibilidade](compatibility.md). Mantenha as
   versões exatas de runtime, cliente e plataforma, o commit de origem, observações e digests de
   evidência. Resolva controles falhos ou registre um contrato de suporte deliberadamente mais
   estreito antes de chamar um cliente de qualificado. `permission-controls` ganhou um driver
   depois da 0.12.0 e ainda não rodou ao vivo: na primeira rodada que o executa, qualifique o alvo
   manualmente também e compare os dois resultados antes de confiar no veredito automatizado.
   Registre essa comparação com as observações da rodada, e substitua a recusa registrada em
   `tests/fixtures/permission-controls/` se a rodada produzir uma real. Todo outro caso ganhou um
   driver ao mesmo tempo, e `scripts/qualification_provision.py` e `scripts/qualification_round.py`
   provisionam e conduzem a rodada; o [runbook](qualification-runbook.md) traz a mecânica. A mesma
   comparação manual é devida uma vez por caso na sua primeira rodada ao vivo. Um alvo Codex relata
   `unverified` seja o que for que tenha observado até que `--home-confirmed` diga que seu
   diretório de configuração foi comparado contra uma execução manual. Os casos com script rodam na
   classe de capacidade `standard` e suas observações são avaliadas em `strong`; ambas as classes
   são registradas no registro de evidência e no registro da rodada, e uma rodada cujo executor
   barato seria o único leitor da sua própria evidência é recusada em vez de rodada. As classes, as
   sobrescritas por alvo e as recusas estão no [runbook](qualification-runbook.md). A economia
   esperada é a estimativa da #338 e não uma medição: 230 mil–590 mil tokens de saída por rodada,
   a maior parte deles de autoria em vez de julgamento.
2. Em um lançamento minor, rode a suíte de integração opcional do BMad uma vez, em um alvo, antes
   da tag: a revisão nativa de quatro camadas descrita em [BMad](bmad.md). Ela não bloqueia nada —
   um resultado vermelho é uma issue a registrar, não um lançamento bloqueado — e seu resultado é
   registrado no pull request do lançamento com a versão do harness, a versão do framework e o
   cliente em que rodou. Um lançamento patch pula isso. Nenhum workflow de framework é uma entrada
   de `required_cases`.
3. Mescle mudanças revisadas através do gate de PR do repositório. Mantenha as bases de PR
   empilhados atualizadas sem sobrescrever o histórico de outros contribuidores. Preserve a
   configuração pessoal e o checkout ao vivo.
4. Defina `VERSION`, `compatibility/catalog.json` e `compatibility/migration.json` para o mesmo
   lançamento. Registre ações de migração exatas e recuperação mesmo quando a única ação seja
   revisar uma execução a seco. Regenere projeções e notas de lançamento. Dobre o changelog na
   seção da versão: para a 0.13.0, manualmente a partir de `## [Unreleased]` como antes, e esse
   pull request de lançamento é o corte que encerra a isenção de Unreleased do lint; a partir do
   próximo lançamento, com `python3 scripts/release_notes.py --changelog <version>`, que monta os
   fragmentos de `changelog.d/` em uma ordem estável e os apaga (veja
   [`changelog.d/README.md`](../changelog.d/README.md)). Essa montagem satisfaz a regra de
   fragmento do lint, então o pull request de lançamento não adiciona nenhuma dispensa `.none.md`.
   Rode os comandos de CI e a suíte de piso Python no HEAD commitado; depois rode:

   ```sh
   python3 scripts/release_preflight.py
   python3 scripts/release_notes.py
   ```

   O preflight também compara o painel About do GitHub com `product.json` e verifica toda entrada
   de `on_the_way` que nomeia uma issue; uma entrada cuja issue fechou bloqueia o lançamento até
   que seja promovida ou removida. Os dois leem o GitHub através do `gh`, então os dois só rodam
   atrás de uma sondagem de `gh auth status`. Sem um `gh` autenticado, o preflight imprime
   `release warning: About and On-the-way checks skipped, gh is not authenticated` e não falha, o
   que é o que acontece no workflow de tag: seu passo de preflight não recebe nenhum token de
   propósito, então esses dois checks são esperados a avisar ali e precisam rodar localmente antes
   de marcar a tag. Uma chamada de `gh` que falha depois de a sondagem passar é um lançamento
   bloqueado, não um pulo.

   Atualize o número estático de contexto para a nova versão com
   `python3 scripts/cost_bench.py static --write` e faça commit; veja [benchmarks](benchmarks.md).

   Antes de congelar o candidato, rode `python3 scripts/lifecycle_acceptance.py` sob todo Python e
   sistema operacional de referência que o registro de candidato nomeia. O executor usa diretórios
   home descartáveis, verifica a fixação do arquivo imutável v0.9.0, e cobre instalação limpa,
   sincronização repetida, atualização, rollback, conflitos e desinstalação. Guarde sua saída JSON
   junto com a evidência do candidato. Esta é uma verificação de ciclo de vida de sistema de
   arquivos/configuração; ela não qualifica um cliente nativo.

5. Marque com tag o commit verificado com a tag imutável correspondente `v<version>` e envie
   (push) essa tag. O workflow de lançamento repete a qualificação e os gates de origem antes de
   publicar. Nunca mova uma tag existente para reparar um lançamento falho; corrija a origem e use
   uma nova versão.
6. O job `advance-stable` do workflow, que não consegue falhar a execução, avança (fast-forward) a
   branch `stable` para o commit da tag, então `stable` é sempre o último lançamento enquanto
   `main` é o tronco. Nada mais envia para `stable`, e ela nunca retrocede. Confirme isso, e
   repare-a a partir de um checkout que tenha a tag se estiver desatualizada:

   ```sh
   python3 scripts/advance_stable.py --check
   python3 scripts/advance_stable.py
   ```

   O GitHub recusa um token de workflow que move uma branch através de uma mudança em
   `.github/workflows/`, então um lançamento que edita um workflow pode precisar do segundo
   comando rodado manualmente.
7. Feche o marco lançado e abra o próximo. Este é um passo rodado manualmente em vez de um job de
   workflow, para que um lançamento publicado nunca dependa dele. Leia os números de marco, feche
   o lançado, e crie o próximo se ele não existir:

   ```sh
   gh api repos/{owner}/{repo}/milestones \
     --jq '.[] | "\(.number) \(.title) open:\(.open_issues)"'
   gh api -X PATCH repos/{owner}/{repo}/milestones/<number> -f state=closed
   gh api repos/{owner}/{repo}/milestones -f title=v<next> -f state=open
   ```

   Mova qualquer issue ainda aberta no marco fechado para o novo primeiro, para que o marco
   fechado registre o que o lançamento de fato carregou.

## Congele a branch de qualificação

Corte `release/v<version>` no commit que a rodada qualifica e registre-o em
`compatibility/freeze.json` como `state: frozen` com essa branch e commit completo, depois rode
todo alvo nessa branch para que `main` continue mesclando sem invalidar a evidência. `citizen freeze`
imprime o desvio entre o commit congelado e `origin/main` sob os caminhos de origem de runtime —
`VERSION`, `bin`, `lib`, `adapters`, `primitives`, `policy`, `templates`, `config.example.json` —
e `citizen freeze --merge-check <ref>` recusa um merge na branch congelada que muda qualquer um
deles, porque tal mudança custa parte da rodada de novo. Quanto disso é escopado por alvo: uma
mudança sob o diretório de adaptador de um runtime invalida apenas os alvos desse runtime, a menos
que toque um arquivo que código compartilhado lê para todo runtime, e uma mudança à origem
compartilhada invalida todos eles. A exceção e seus limites estão em [compatibilidade](compatibility.md).
Retorne `state` para `open` depois da tag. O commit de evidência precisa continuar sendo ancestral
do commit de origem da qualificação, o que `evidence_errors` aplica, então uma branch de lançamento
divergente falha fechada em vez de publicar uma origem não qualificada.

Antes de a rodada começar, e de novo no commit de congelamento, rode a camada de smoke test
determinística. Ela não gasta nenhum turno de modelo e custa cerca de dois minutos:

```sh
python3 scripts/smoke_tier.py            # --list nomeia cada verificação, sem rodar nenhuma
```

Ela roda os autotestes do executor de aceitação contra transcrições registradas, a verificação de
link de documentação, a sondagem de pré-condição para o cliente de cada alvo, login e o daemon do
Docker no host que vai rodar a rodada (o [runbook](qualification-runbook.md#target-hosts) os
estabelece), e as verificações de sincronização de diretório home descartável, desvio de projeção
e ciclo de vida. Todo defeito que ela captura é um que de outra forma seria encontrado no meio de
uma rodada e custaria a rodada inteira de novo. Uma camada verde **não é** qualificação: ela não
observa nenhum cliente, não escreve nada sob `compatibility/evidence/` e não aparece em nenhum
registro de catálogo, e a execução falha se qualquer verificação tocar em qualquer um dos dois.
**Uma camada vermelha bloqueia a rodada:** `scripts/qualification_round.py` a roda primeiro e,
quando ela falha ou expira, não lança nenhum alvo e registra o porquê em `round.json`.
`--skip-smoke` é para uma camada que você já rodou verde neste commit; a rodada a registra como
`skipped`. A CI também roda a camada como um job `smoke`, que o conjunto de regras da branch não
exige, então um job vermelho avisa sobre um merge mas só bloqueia a rodada.

**Não corrija nenhum defeito no meio de uma rodada.** Uma rodada roda todos os quatro alvos
obrigatórios até o fim e coleta seus defeitos; uma correção feita entre alvos invalida os alvos já
observados e força uma nova execução de cada um. Aplique as correções coletadas juntas na `main`
depois, corte um novo commit de congelamento, e requalifique uma vez.

## GitHub About

8. Traga a descrição, os tópicos e a homepage do GitHub About para `product.json` com os comandos
   abaixo. Rode a verificação a cada lançamento, mesmo quando nada mudou, e registre seu resultado.

`product.json` é a fonte do texto da página inicial, da grade do README e do painel About.
`scripts/sync_about.py` compara seu `github_description` e `topics` com
`gh repo view --json description,repositoryTopics,homepageUrl`, tratando tópicos como um conjunto
porque o GitHub os retorna em sua própria ordem. Uma chave `homepage` em `product.json` também é
comparada; enquanto o arquivo não nomeia nenhuma, a URL da homepage ao vivo é deixada intacta.

```sh
python3 scripts/sync_about.py --check    # nomeia cada campo diferente, sai não-zero em desvio
python3 scripts/sync_about.py --apply    # os escreve através de `gh repo edit`
```

Rode os dois localmente. `--apply` muda os metadados públicos do repositório, então precisa da
aprovação do dono a cada execução, e não pode ser movido para o workflow de lançamento: editar
configurações de repositório exige acesso de administração, que não está entre os escopos de
permissão disponíveis para o `GITHUB_TOKEN` do workflow
([sintaxe de workflow](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)).
O lado `--check` dele roda dentro de `scripts/release_preflight.py`, que avisa em vez de falhar
quando o `gh` não está autenticado.

`scripts/sync_about.py --apply` escreve seja lá o que `product.json` do *checkout atual* carrega.
Rode-o apenas de uma worktree avançada (fast-forward) para `origin/main`
(`bin/harness worktree create main-sync <repo>`, depois `git merge --ff-only origin/main`); um
checkout desatualizado uma vez reverteu o painel About.

## Rollback

Mantenha a tag anterior do harness e a identidade do artefato de lançamento antes de publicar. Uma
regressão recebe um PR de reversão e um novo lançamento do harness; não redirecione a tag antiga, e
deixe `stable` onde está até que esse lançamento a avance. Restaure o GitHub About rodando
`scripts/sync_about.py --apply` a partir de um checkout da tag anterior, com a aprovação do dono.
Reconcilie a configuração local através do seu diário de posse, preservando conflitos e backups
adotados. Verifique a identidade do lançamento de novo.

## Status do lançamento

O lançamento 0.13.1 qualifica o Claude Code CLI no macOS e no Linux; contra a 0.13.0 ele só muda o
texto da página inicial. O Codex CLI não está em seu contrato: ele é admitido assim que uma rodada
de qualificação com script concordar com uma conduzida manualmente, então a 0.11.1 continua sendo o
último lançamento que o qualifica. As superfícies do VS Code e o Codex Desktop são prévias não
qualificadas. A integração architecture-viewer também é uma prévia para uma implementação
instalada separadamente, sem visualizador empacotado ou alegação de aprovação de distribuição. O
lançamento é identificado pelo commit exato que carrega a tag imutável `v0.13.1`. Nunca contorne o
preflight de lançamento.
