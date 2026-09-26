# Governança do repositório BMad

Este arquivo é a única fonte de política carregada pelas customizações de workflow BMad do
agent-harness. As instruções do repositório continuam valendo quando forem mais rígidas.

- **A autoridade é dividida entre a issue e seu arquivo de história.**
  - A issue do GitHub é a autoridade de entrega. Ela guarda o estado, a discussão, um texto em
    profundidade de resumo e a evidência de aceitação.
  - O arquivo de história da issue, `_bmad-output/implementation-artifacts/<BMad ID>.md`, é a
    autoridade de design. Ele guarda:
    - contexto e critérios de aceitação;
    - o design, com decisões e alternativas;
    - tarefas;
    - notas de desenvolvimento que citam suas fontes;
    - o registro do agente de desenvolvimento;
    - achados de revisão.
  - Mantenha a issue em profundidade de resumo e coloque a profundidade de design na história.
  - Crie a issue antes de alterar arquivos rastreados. Use uma issue de entrega por PR, e mantenha
    uma única questão em cada PR.
- Rode a implementação em uma worktree gerenciada. Rode os scripts instalados do BMad a partir do
  checkout compartilhado e passe a worktree de implementação como uma entrada explícita.
- Os artefatos públicos do BMad ficam sob `_bmad-output`; nunca redirecione os artefatos deste
  repositório para um repositório de planejamento privado ou central.
- Publique evidências e decisões sintetizadas, não conversas brutas, logs de ferramenta,
  exportações de memória, segredos, caminhos privados ou informação pessoal irrelevante.
- Rotule alegações como implementadas, validadas, propostas, históricas ou desconhecidas. Não trate
  configuração gerada, testes unitários verdes ou um lançamento anterior como prova de
  comportamento nativo de cliente atual.
- Todo item de trabalho gerenciado tem um único ID BMad tipado e imutável e um mapeamento
  bidirecional com o GitHub. Reparentar nunca muda o ID; um histórico reconstruído deve dizer que
  é reconstruído.
- O rótulo `type::*` exato é a projeção de tipo autoritativa do GitHub neste repositório. Tipos
  nativos de issue são gerenciados pela organização e indisponíveis para issues neste repositório
  de conta pessoal; relações nativas de sub-issue continuam sendo a projeção de hierarquia.
- Registre trabalho de mantenedor com
  `python3 scripts/bmad_issue_sync.py new --title T --kind KIND --body-file F [--parent N] [--milestone M]`
  a partir da worktree de implementação: isso rotula a issue e reserva seu ID em um único passo.
  Recuse iniciar ou continuar a implementação de uma issue ausente em
  `_bmad-output/issue-map.json`; reserve-a primeiro. O check obrigatório `issue-ownership` reprova
  um PR cuja issue de entrega não esteja mapeada, então a reserva vai nesse PR ou antes dele.
- Issues da comunidade podem entrar sem metadados do BMad. Durante a triagem do mantenedor, reserve
  um ID com `python3 scripts/bmad_issue_sync.py reserve --issue N --kind KIND [--parent N]`; faça
  merge do seu artefato, depois rode `plan` e `apply` antes de a posse da implementação começar.
- Preserve o histórico da issue e do repositório. Adicione emendas em vez de reescrever evidência
  datada, e não substitua a prosa original da issue ao manter os metadados de rastreabilidade.
- Antes da revisão, rode `python3 bin/harness lint`, `python3 -m unittest discover -s tests`, e
  `bin/harness generate --check`. Nunca contorne hooks.
- Issues e PRs comuns usam a voz nativa do repositório, sem rodapés gerados por framework. O README
  e a documentação de planejamento podem creditar o BMad explicitamente.

## Roteie toda operação pelo BMad

Antes de uma etapa do ciclo de vida do software, leia e siga a skill do BMad correspondente. Nunca
improvise um processo que uma skill já define.

| Quando você | Rode |
| --- | --- |
| Pesquisa uma pergunta da qual uma decisão depende | `bmad-deep-recon` |
| Muda quem o produto serve ou para que ele existe | `bmad-product-brief`, atualize a intenção |
| Adiciona, muda ou aposenta um requisito | `bmad-prd`, atualize a intenção |
| Muda um fluxo, saída ou padrão de texto voltado ao usuário | `bmad-ux`, atualize a intenção |
| Muda um invariante, um limite ou uma direção de dependência | `bmad-architecture`, atualize a intenção |
| Divide um escopo novo em trabalho | `bmad-create-epics-and-stories`, depois `scripts/bmad_issue_sync.py new` |
| Implementa um item de trabalho | `bmad-build`, com a história de entrega como sua especificação |
| Revisa uma mudança | `bmad-code-review` |
| Muda de direção no meio do caminho | `bmad-correct-course` |
| Fecha um épico | `bmad-retrospective` |
| Verifica prontidão ou status | `bmad-sprint-planning` |

O Review Card do `/plan` do harness continua sendo a superfície de aprovação de um build. No
momento do build, destile seu adendo nas notas de Design e de Dev da história de entrega. Seja lá
o que produziu o plano, a história é o registro durável.

## Mantenha o corpus atualizado em toda mudança

Atualize o corpus no mesmo PR da mudança que o deixa desatualizado:

- **Trabalho novo.** Registre com `scripts/bmad_issue_sync.py new`, que registra a issue, reserva
  o ID e escreve um esqueleto de história tipado. Preencha as seções obrigatórias da história antes
  de o PR de entrega ser mesclado. O check `issue-ownership` reprova uma história de entrega tipada
  que ainda carregue placeholders.
- **Ao tocar um stub legado.** Rode `scripts/bmad_issue_sync.py upgrade --id <BMad ID>` e preencha
  o esqueleto no mesmo PR.
- **Implementação.**
  - Mantenha a história de entrega atualizada: marque as tarefas concluídas, adicione a lista de
    arquivos e referências nas notas de dev, e complete o registro do agente de desenvolvimento.
  - Registre cada achado de revisão e como foi resolvido.
  - Adicione uma linha de changelog para toda mudança material depois de a história ser escrita
    pela primeira vez.
- **Requisitos, invariantes ou fluxos alterados.**
  - Um requisito alterado emenda o PRD.
  - Um invariante alterado emenda a espinha da arquitetura, seja como uma regra emendada ou um AD
    novo.
  - Um fluxo voltado ao usuário alterado emenda a especificação de UX.
  - Cada emenda passa pela intenção de atualização da skill correspondente, com uma entrada de
    memlog.
- **O status do sprint é derivado.** Ele é gerado a partir de `issue-map.json` pela ferramenta de
  sincronização; nunca o edite manualmente.

## Reservas paralelas se mesclam por meio de um driver

Duas branches que cada uma reserva um ID BMad ambas acrescentam a `items` em
`_bmad-output/issue-map.json` e incrementam `next_ids`, então, sem ajuda, a segunda a ser mesclada
entra em conflito. `.gitattributes` roteia o mapa e o status de sprint derivado pelos merge drivers
em `scripts/bmad_merge_driver.py`:

- **O mapa** mescla item por item. O mapa da main é mantido, as novas entradas da branch são
  adicionadas no próprio formato JSON da ferramenta, e `next_ids` fica com o contador maior por
  tipo. Quando a main e a branch mapearam a mesma issue do GitHub sob IDs diferentes, a entrada da
  main vence e o driver nomeia o ID descartado; remova o arquivo de história desse ID da branch. Em
  um merge, a main é o lado que chega, já que você mescla a main na sua branch; em um rebase, é o
  lado upstream.
- **O status de sprint** é renderizado de novo a partir do mapa mesclado e dos arquivos de história
  mesclados, e essa renderização é o resultado do merge, então o próprio commit de merge carrega a
  regeneração. Ele precisa do commit que chega, que `git merge` e `git pull` nomeiam; em um rebase
  ou cherry-pick, ele relata um conflito em vez disso, e você roda
  `python3 scripts/bmad_issue_sync.py sprint-status`.
- **Qualquer coisa que ele não consiga resolver com exatidão é um conflito**: um lado ilegível, um
  campo que os dois lados mudaram de forma diferente, ou um ID reservado para duas issues. O
  último mantém as duas entradas, então as verificações de duplicidade da auditoria continuam
  falhando nele. Resolva manualmente, depois regenere o status de sprint.

`citizen worktree create` registra os dois drivers na configuração git do repositório toda vez que
roda, escrevendo apenas um valor diferente do que espera. Ele os registra apenas no repositório ao
qual o checkout do `citizen` em execução pertence, então outro repositório que distribua um script
de mesmo nome nunca tem seus merges roteados por ele. Para registrá-los em um checkout existente,
rode:

```sh
git config merge.bmad-issue-map.name "BMad issue map"
git config merge.bmad-issue-map.driver "python3 scripts/bmad_merge_driver.py map %O %A %B"
git config merge.bmad-sprint-status.name "BMad sprint status"
git config merge.bmad-sprint-status.driver "python3 scripts/bmad_merge_driver.py sprint-status %O %A %B"
```

A configuração do git é compartilhada por toda worktree de um repositório, então uma vez é
suficiente. Sem registro, o git mescla os dois arquivos como texto, como fazia antes.
