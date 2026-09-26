# Higiene de segredos, onde quer que arquivos sejam rastreados

- **Nunca coloque tokens, senhas, chaves de API ou segredos em qualquer arquivo que seja
  commitado no controle de versão** — arquivos de regra, docs, código-fonte, config, comentários,
  docstrings, mensagens de commit e artefatos de planejamento, todos igualmente.
- **Leia credenciais do ambiente, nunca embutidas no código.** CLIs de nuvem as resolvem a partir
  de um perfil ou de um cofre de segredos; use `--profile` ou uma variável de ambiente, nunca uma
  chave colada.
- **Ao encontrar um segredo no controle de versão, pare.** Não faça commit por cima; avise o
  usuário imediatamente para que a credencial seja rotacionada primeiro; depois remova-a, depois
  reescreva o histórico se justificado.
- **Adicione um arquivo com segredo ao `.gitignore` antes de criá-lo.** Um arquivo já rastreado
  continua rastreado quando seu diretório é ignorado depois — verifique `git ls-files`. Nunca dê
  `git add` num.
- Porquê, e os exemplos de shell: `docs/how-it-works.md`.
