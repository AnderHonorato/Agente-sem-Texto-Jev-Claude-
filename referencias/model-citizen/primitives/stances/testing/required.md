# Postura de testes: obrigatória

**"Construa a funcionalidade X" significa: construa-a, faça todo teste existente passar, e
escreva testes cobrindo toda nova capacidade** — funções, métodos e serviços que carregam lógica,
endpoints de API (forma de requisição e resposta, imposição de autenticação, casos de erro),
componentes de UI com comportamento, hooks, utilitários, e toda correção de bug com um teste de
regressão. Rode a suíte do módulo afetado e conserte toda falha, incluindo falhas pré-existentes
em arquivos que você tocou. Siga a convenção de coposicionamento do repositório, leia um teste
vizinho primeiro, e não admita exceção — nem velocidade, nem "simples", nem "depois". Se a suíte
é boa é uma questão separada: `code-quality-instruments`.
