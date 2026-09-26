# Higiene de cache

- **Mantenha o prefixo em cache estável no meio da tarefa:** evite mudanças de modelo, esforço,
  modo rápido, conjunto de ferramentas ou MCP. O comportamento nativo de cache difere; não presuma
  regras idênticas de invalidação.
- **Sessões novas começam frias:** agrupe tarefas pequenas; use o controle nativo de sessão nova,
  não a compactação, a menos que `cost` permita.
