# Gates de verificação, em um repositório de código

- **Rode os gates localmente; nunca abra um PR com trabalho não verificado.** Porquê:
  `docs/how-it-works.md`.
- **Encontre os comandos exatos que o CI roda** — o arquivo de workflow, não o README — e rode
  esses.
- **Registre a saída esperada de árvore limpa** nas instruções de agente do repositório na
  primeira execução.
- **Rode o formatador antes do gate**; a maioria dos checks de CI formata em vez de aplicar
  formatação.
- **Codifique para o piso:** use nenhuma API mais nova que a versão mínima testada, ou eleve-a no
  PR.
- **Todo arquivo no diff se rastreia até a issue declarada.** Uma preocupação por PR; divida antes
  da revisão.
- **Nunca contorne hooks de pre-commit**, e nunca use `git commit --no-verify`.
- **Marque e exclua testes de serviço ao vivo**; prefira fixtures gravadas. Um novo é uma
  regressão.
- **Teste autenticação anonimamente**, sem seguir redirects, afirmando o código de status
  diretamente.
