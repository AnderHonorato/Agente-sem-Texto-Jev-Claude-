---
name: upstream-contribution
description: Contribute from a fork to a repository you do not own without burning maintainer trust. Use when the working repo has an `upstream` remote, when the user says "open a PR against <someone else's repo>", or before the first commit in any repo the user is a guest in.
---

# Contribuição upstream

**Este repositório não é seu.** Ele pertence a seus mantenedores, com sua própria fila, suas
próprias convenções e sua própria história de boas intenções não mescladas. Aja como um convidado.

## Remotes

`origin` é **o seu fork**. `upstream` é o projeto, e sua URL de push está definida como
`no_push`:

```bash
git remote set-url --push upstream no_push
git remote -v          # origin = fork, upstream = projeto (no_push)
```

O remote que você digita por reflexo é aquele seguro para dar push. **Nunca faça commit no
`main` local** — mantenha-o um espelho limpo do upstream para que rebases continuem triviais:

```bash
git fetch upstream && git checkout main && git reset --hard upstream/main
```

## Issue antes de código

Para qualquer coisa maior que uma correção de bug ou uma correção de documentação, **abra uma
issue e espere a resposta de um mantenedor antes de escrever a implementação.** A maioria dos
projetos tem um cemitério de grandes PRs não solicitados. Volume de código não é o que faz
mesclar; acordo prévio é.

Use os templates de issue do repositório. Se o trabalho é especulativo, diga isso.

## Escopo de branch e PR

- Nomes de branch: `<numero-da-issue>-descricao-breve` quando existe uma issue, senão
  `<area>-descricao-breve`.
- **Uma preocupação por PR.** Todo arquivo no diff se rastreia até a issue declarada. Divida um
  PR grande demais antes de pedir revisão, não depois.
- **Nunca mude um padrão silenciosamente.** O projeto roda dentro da produção de outras pessoas.
  Comportamento novo chega como um novo parâmetro cujo padrão preserva exatamente o comportamento
  de hoje.
- **Nunca junte uma refatoração com uma correção.** Uma issue aberta de "deixar mais DRY" não é
  uma licença para arrumar código que você por acaso estava perto.
- **Uma mudança de tipo de retorno é uma mudança de quebra**, incluindo trocar um tipo de
  terceiros pelo seu próprio. Diga isso honestamente no PR; errar isso é como a confiança se
  perde.
- Mudanças abrangentes (docs, type hints, lint) vão uma família de módulos por PR. Uma varredura
  de cinquenta arquivos é impossível de revisar e vai ficar parada.

## Antes de abrir o PR

Rode os próprios gates do projeto exatamente como o CI os roda; a regra `verification.md` se
aplica com força extra aqui. Preencha as seções do template de PR e não apague nenhuma. Use os
rótulos que o ferramental de release do projeto lê; não brigue com rótulos automáticos.

## Onde o guia de contribuição realmente vive

`CONTRIBUTING.md` é frequentemente um esboço. Trate o arquivo de workflow de CI, a configuração
de lint, o template de PR e um módulo existente do mesmo tipo como as fontes de verdade dentro do
repositório. Se o guia real está atrás de um site que bloqueia fetches, um humano o abre; não
adivinhe seu conteúdo.

## Comunidade

Se o projeto tem um chat ou uma call regular de contribuidores, perguntar ali é mais barato que
um PR rejeitado.
