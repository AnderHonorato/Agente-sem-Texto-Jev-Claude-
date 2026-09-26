# Model Citizen

Um harness alinhado ao usuário, agnóstico de provedor de modelo, com primitivos personalizados
compartilhados e preferências pessoais que podem ser trocadas. `bin/harness` projeta uma única
autoridade de política para o Claude Code e para o Codex. As regras globais sob as quais um agente
roda neste repositório vêm do próprio harness, então este arquivo carrega só o que é verdade sobre
este repositório.

## Comandos

```sh
bin/harness lint                          # strings pessoais e padrões de segredo; precisa estar limpo
python3 -m unittest discover tests        # lógica de merge, link, configuração e lint
bin/harness sync --dry-run                # o que um sync faria a partir deste checkout
bin/harness doctor                        # versões, logins, links, desvios
```

**Saída esperada numa árvore limpa:** `lint: 0 finding(s) in …` e `OK` do unittest sem
nenhum teste pulado. Os testes rodam sob o Python 3.9 do sistema e sob um Python atual; mantenha o
código livre de sintaxe mais nova que 3.9.

## Portão (Gate)

```sh
python3 bin/harness lint
python3 -m unittest discover -s tests
```

O hook `stop-gate` roda esse bloco quando a árvore mudou desde sua última execução verde,
bloqueia o turno enquanto estiver vermelho, e libera depois de oito bloqueios consecutivos. Ele só roda
depois que este checkout for confiável: aceite a caixa de diálogo de pasta do Claude Code ou rode `bin/harness trust .`.

## Planejamento com o BMad

BMad Method 6.12.0 com projeções BMM, Claude Code e Codex, e ajustes de compatibilidade, é o
sistema de planejamento público do repositório. Seu corpus de autoria fica em `_bmad-output`; não redirecione
para outro repositório. O comando completo de instalação fixada e o limite de controle de versão estão em
`docs/bmad.md`. Rode workflows de planejamento a partir do checkout compartilhado e implementação a partir de uma worktree gerenciada.

Toda etapa do ciclo de vida do software é roteada para sua skill do BMad, e todo PR mantém o corpus atualizado: a issue guarda
um resumo, seu arquivo de história carrega o design. O mapa de roteamento, a regra de atualização e o contrato do
arquivo de história estão em `docs/bmad-governance.md`, que todo workflow do BMad carrega.

## Como o checkout é usado

- **Este checkout está ao vivo.** `harness sync` cria links simbólicos de `claude/rules`, cada `claude/skills/*`,
  `claude/hooks` e o estilo de saída para dentro de `~/.claude`. Uma edição aqui já vale na próxima
  sessão sem nenhum passo a mais; uma regra pela metade também vale. Trabalhe numa worktree ramificada
  a partir de `main`, então o checkout ao vivo só carrega conteúdo já mesclado.
- **Toda mudança entra por um pull request.** O conjunto de regras do `main` exige checks `lint` e
  `test` verdes num branch atualizado e um squash merge; não existe push direto.
- **Uma issue de entrega por PR, um PR por issue de entrega.** Crie ou selecione uma issue dedicada
  antes de mudar arquivos, incluindo docs — registre com `scripts/bmad_issue_sync.py new`, ou
  `reserve` uma já existente, porque `issue-ownership` também reprova um PR cuja issue não tenha um ID do BMad
  em `_bmad-output/issue-map.json`. Adicione `Closes #N` ao PR. Divida trabalho entregue separadamente
  em issues filhas; referências contextuais não estabelecem posse. Reaproveitar só é permitido
  quando um PR anterior foi fechado sem ser mesclado. O check `issue-ownership` aplica
  links de fechamento atuais do GitHub; verifique a posse de novo imediatamente antes de mesclar.
- **Mudanças de código** (`bin/harness`, `claude/hooks/*.py`, `tests/`) carregam um teste junto com toda
  mudança. Mudanças de conteúdo (regras, preferências, texto de skill, docs) são controladas pelo lint e pela revisão.
- Nada pessoal, nada específico de projeto, nada com licença copyleft. O lint aplica o primeiro ponto;
  a revisão aplica o resto.

## Revisão do CodeRabbit e merge

O CodeRabbit revisa pull requests para `main`, como `.coderabbit.yaml` configura. Em todo pull
request, trabalhe a revisão dele no passo 6 do `/build` e sem perguntar antes: envie correções para o
branch, responda nas threads dele e as resolva, e peça cada nova passada com
`@coderabbitai review`, já que um push nunca inicia uma sozinho. Peça a primeira passada da mesma forma quando a
revisão automática pula o pull request, como acontece com rascunhos, títulos `chore(release)` e Dependabot.
Uma passada terminou quando o status de commit `CodeRabbit` lê `success: Review completed`, de sete a
onze minutos depois de começar, então reserve quinze. O status `Review skipped` que ele posta em todo push
não é uma passada, e nem é a revisão vazia que cada resposta de thread dele cria. Comentários no
corpo da revisão, fora do diff ou marcados como nitpicks, também são achados: corrija-os, ou responda-os num
comentário de pull request.

**Estas condições são o sinal verde que o `/land` pede.** Mescle um pull request de um branch
deste repositório, nunca de um fork, sem perguntar, assim que as três seguintes valerem:

1. **Nada espera pelo mantenedor:** nenhuma pergunta para ele está em aberto, nenhum padrão que você assumiu em nome dele
   espera confirmação, e o diff faz o que a issue pede e nada além disso.
2. **Está testado:** o bloco do Portão passou antes do seu último push, e todo check obrigatório está verde
   no commit de topo.
3. **A revisão foi trabalhada:** uma passada terminou depois da sua última mudança num arquivo que o CodeRabbit
   revisa, cada achado dele está corrigido ou respondido com o motivo, toda thread está resolvida,
   e nenhuma thread humana está aberta. Trazer `main` para dentro não exige nova passada.

Sem as três, relate o que falta com o link do pull request e espere. Um lançamento, uma tag e
`sync_about.py --apply` mantêm suas próprias aprovações.

## Issues, marcos e lançamentos

- **Toda issue carrega um rótulo `type::*`**, e o marco `v<próxima>` quando é destinada ao
  próximo lançamento. Crie esse marco quando a primeira issue for registrada contra ele.
- **Um pull request que adiciona ou muda uma capacidade visível ao usuário atualiza `product.json` no
  mesmo pull request**: uma nova linha de funcionalidade, ou uma entrada de `on_the_way` promovida para
  `capabilities`. Esse arquivo é a única fonte do texto da página inicial, da grade do README e da
  descrição "About" do GitHub. Trabalho planejado que vale a pena anunciar entra em `on_the_way`, com teto de cinco entradas, e
  cada entrada nomeia a issue, o cliente planejado ou o documento que representa. O check `landing-copy`
  reprova um pull request que muda `bin/`, `lib/`, `adapters/`, `primitives/` ou `policy/` sem
  `product.json`, a menos que o corpo carregue uma linha `Landing copy:` dizendo por que nenhuma é necessária.
- **Lançamentos são feitos por marco.** Mescle livremente; proponha um lançamento quando o marco esvaziar ou
  quando uma mudança visível ao usuário sem lançamento tiver sete dias. Uma correção de regressão lança na hora
  como um patch.
- **Numere pelo que mudou**, não por onde aterrissou no changelog: só correções é um patch;
  comportamento visível ao usuário adicionado ou mudado é um minor; `docs/compatibility-policy.md` decide um
  major. O que um lançamento precisa carregar antes de ser marcado com tag está na seção "Origem e qualificação"
  de `docs/releasing.md`, que também guarda os comandos de fechar-e-abrir o marco.
- **Depois de toda mesclagem, rode `/land`**, e depois de toda tag, trabalhe as cinco superfícies abaixo.

## Um lançamento não termina na tag

Um lançamento tem cinco superfícies, e cada uma envelhece por conta própria. Trabalhe-as nesta ordem e
relate cada uma como feita, pulada ou não verificada — nunca infira uma a partir de outra. O procedimento, os
comandos e o rollback estão em `docs/releasing.md`; esta lista existe para que nenhuma seja esquecida.

1. **Origem e evidência** — toda correção mesclada; registros nativos de qualificação e ciclo de vida para o
   commit congelado em `compatibility/evidence/`, o catálogo `qualified` com digests e limitações.
2. **Metadados do lançamento** — catálogo `released` e fixado, as entradas "Unreleased" do changelog
   dobradas para dentro da seção da versão, texto de status em `README.md`, `docs/compatibility.md` e
   `docs/releasing.md`.
3. **Tag e lançamento no GitHub** — `scripts/release_preflight.py` limpo num clone novo, depois a
   tag anotada `v<versão>`; confirme que o workflow de lançamento rodou, o lançamento está publicado e
   `scripts/advance_stable.py --check` encontra `stable` na tag.
4. **"About" do GitHub** — descrição, tópicos e homepage precisam ser iguais a `product.json`. Rode
   `python3 scripts/sync_about.py --check` a cada lançamento mesmo quando nada mudou, e diga isso.
5. **O desenvolvimento retoma** — a primeira mudança de código-fonte do runtime depois de um lançamento faz o catálogo
   relatar desvio por design; a próxima versão precisa de um candidato aberto antes de poder ser qualificada.

O passo 4 com `--apply` muda metadados públicos do repositório, então precisa da sua própria aprovação explícita
toda vez que é executado.

## Estrutura de pastas

- `primitives/` — a autoridade de autoria compartilhada. `policy/` — política de ciclo de vida compartilhada.
- `adapters/` — vínculos de runtime; `compatibility/` — evidência e status de qualificação nativa.
- `claude/` — projeções de compatibilidade e configurações nativas; o que é linkado para dentro de `~/.claude`: `CLAUDE.md`, `rules/`, `stances/`, `skills/`,
  `hooks/`, `output-styles/`, além de `settings.template.json` e `OWNERSHIP.json`.
- `bin/harness` — a CLI. `tests/` — seus testes unitários.
- `vscode/`, `codex/`, `templates/repo/` — as outras superfícies que o harness gerencia.
- `docs/` — como funciona; o único lugar onde nomes de procedência do projeto são permitidos.

## `AGENTS.md` e `CLAUDE.md` são um arquivo só

`CLAUDE.md` é um link simbólico para este arquivo. Edite `AGENTS.md`.
