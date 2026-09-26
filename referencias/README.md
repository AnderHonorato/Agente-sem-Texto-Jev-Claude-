# Referências — projetos de terceiros que inspiraram o Jev

Esta pasta guarda material de dois projetos de terceiros (não são do Ander) que inspiraram o framework Jev deste repositório. Nenhum dos dois é obra do Ander — os créditos e a licença de cada um são preservados abaixo.

## `model-citizen/`

Cópia traduzida para português do Brasil do projeto [Model Citizen](https://github.com/JakeSelby/model-citizen), de **Jake Selby**, licenciado em **MIT**.

- O código (nomes de arquivo, pastas, funções, classes e variáveis) foi mantido em inglês, exatamente como no original, para o projeto continuar funcionando sem quebrar.
- Toda a documentação (`README.md`, `AGENTS.md`/`CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`, `docs/`, `primitives/`, `claude/`) e os comentários/docstrings do código Python central foram traduzidos para português.
- O `CHANGELOG.md`, o `THIRD_PARTY_NOTICES(.md)`, a pasta `changelog.d/` e a suíte de testes (`tests/`) foram mantidos em inglês, no original — são histórico de lançamentos, avisos legais de terceiros e testes internos, não conteúdo pensado para leitura direta.
- A pasta `_bmad-output/` do projeto original (saída de exemplo gerada por uma ferramenta de planejamento) não foi copiada — não faz parte do funcionamento do projeto.
- O arquivo `LICENSE` foi mantido **exatamente como no original**, com o aviso de copyright de Jake Selby — é isso que a licença MIT exige para permitir cópia e modificação.

## `keel-explicado.md`

**Não é uma cópia de código.** É um resumo escrito em português sobre o projeto [Keel](https://github.com/codejunkie99/keel), de **codejunkie99**, licenciado em MIT. O Keel é um app nativo de macOS (Rust + GPUI, exclusivo de Apple Silicon) — copiar ou traduzir o código-fonte dele quebraria a compilação e, de todo modo, não rodaria no ambiente do Ander (PC Windows/Linux ou celular). Por isso, em vez de copiar o código, trouxemos a explicação da arquitetura e das ideias (o seletor "Jev" original, a validação do host, o grafo de agentes) que inspiraram o framework deste repositório.

## Por que isso está aqui

O [framework Jev](../ORQUESTRADOR.md) deste repositório (pasta `.claude/agents/` na raiz) não é uma cópia de nenhum dos dois — é uma implementação própria, pensada para rodar dentro do Claude Code em qualquer sistema operacional. Esta pasta existe só para dar crédito e contexto às ideias originais que inspiraram esse framework.
