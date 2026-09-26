# Concisão de comentários e documentação, no código e nos docs

- **Explique uma decisão uma vez,** no docstring onde a coisa é definida ou na página de
  documentação voltada ao usuário. Todo outro arquivo recebe um ponteiro, não uma reafirmação; um
  segundo doc se vincula ao primeiro.
- **Não narre o que o código já diz.** Um comentário explica um *porquê* não óbvio.
- **Docstrings seguem o estilo ao redor** — leia uma função vizinha primeiro. Não os adicione para
  um linter que não está rodando; adicione onde um usuário da API pública precisar deles.
- **Código, testes e docs entregues se sustentam sozinhos para um estranho.** Sem docs de
  planejamento, outros repositórios, números de tickets internos ou notas de avaliação; números
  públicos de issue e PR estão liberados.
- **Descrições de PR começam com o quê e o porquê** em marcadores mais o link da issue; preencha
  toda seção do template, não apague nenhuma, mantenha cada uma curta. Exemplos: `harness-authoring`.
