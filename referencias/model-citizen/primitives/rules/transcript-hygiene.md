# Higiene de transcrição

- **Leia de forma restrita.** Nunca dê `cat` num arquivo inteiro, nem encadeie `cat`s, para
  responder a uma pergunta pontual — recorra a `head`, `grep -n`, ou um intervalo de `sed`. Filtre
  todo `find` e `ls`; 100+ linhas precisa de uma justificativa.
- **Limite o retorno:** coleta 400 palavras, resumo de pesquisa 600, revisão adversarial apenas
  achados.
- **O detalhe vai para um arquivo, não para o retorno** — a versão longa para o scratchpad; o
  veredito, os achados que mudam decisão e o caminho voltam. Um limite de palavras não é um
  orçamento para gastar.
- **Sintetize, nunca retransmita.** Nunca cole o relatório de um subagente, ecoe o briefing que
  você enviou, ou narre que agentes retornaram. Molde a resposta pela postura (stance) `voice`; os
  resumos de raciocínio permanecem.
- **A `description` da ferramenta é o registro de ação:** uma ação clara em palavras simples, sem
  flags ou caminhos.
- **Cite literalmente apenas quando o texto exato *é* o achado** — um erro, uma cláusula de
  licença, uma asserção que falhou. Cite a linha, não o relatório. Exemplos: a skill de mesmo nome.
