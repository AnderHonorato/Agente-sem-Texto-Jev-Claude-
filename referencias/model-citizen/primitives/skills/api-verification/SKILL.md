---
name: api-verification
description: Prove a search, filter or API answer is real before relying on it, and budget web search across a fan-out. Use when querying an unfamiliar API, a filter returns suspiciously clean results, a per-item error may have been swallowed, or briefing research agents. (Prove que uma resposta de busca, filtro ou API é real antes de confiar nela, e orce a busca web num fan-out. Use ao consultar uma API desconhecida, quando um filtro retorna resultados suspeitosamente limpos, um erro por item pode ter sido engolido, ou ao instruir agentes de pesquisa.)
---

# Pesquisa e verificação de API

As linhas operacionais vivem na regra residente `primitives/rules/research-and-verification.md`.
Esta skill carrega o raciocínio, a aritmética por trás do orçamento de busca, e o que fazer depois
de um fan-out.

## Orçamento de busca

**A busca na web tem um teto por sessão e é compartilhada por todo subagente naquela sessão.** No
Claude Code o teto é 200 chamadas. Um fan-out de 18 agentes orientados para 35 buscas cada um o
esgota em minutos; os agentes posteriores rodam só com fetch.

Orce de acordo: cerca de 10 agentes com 20 buscas, ou 6 com 30. Para execuções maiores, escalone
ondas em sessões separadas, ou instrua os agentes a se apoiarem em buscar fontes primárias
conhecidas.

Depois de um fan-out, verifique a contagem de busca de cada subagente e rode de novo as dimensões
que ficaram sem cota e dependem de descoberta numa sessão nova. Agentes só-com-fetch estão bem para
páginas de licença e docs oficiais, mas ficam rasos para perguntas do tipo "o que foi lançado
recentemente".

## Prove que uma resposta de API é real

- **Parâmetros de query desconhecidos são silenciosamente ignorados pela maioria das APIs.** Prove
  que um filtro morde enviando um valor que nunca pode dar match e confirmando que o resultado fica
  vazio.
- **Faça uma checagem pontual de um registro retornado** contra o campo pelo qual você filtrou
  antes de confiar no conjunto.
- **Um erro por item engolido é desconhecido, não ausente.** Conte as falhas separadamente dos
  vazios.
- **Reverifique a especificação atual** antes de presumir que uma solução alternativa documentada
  ainda é necessária.

## Prefira fontes primárias

Prefira documentação escrita por humanos a resumos gerados por agente, e rastreie toda regra em que
você se apoia até uma fonte citável. Quando o cabeçalho de um arquivo e seu corpo discordam, nenhum
dos dois é a verdade fundamental: encontre o código ou a especificação que decide.
