---
description: Answer a research question with parallel read-only gatherers and one synthesized digest.
argument-hint: <question>
---

# Research

A pergunta: {{arguments}}

Carregue as skills `transcript-hygiene` e `api-verification` por completo antes de gerar
qualquer coisa. Elas carregam os tetos de retorno e o orçamento de busca compartilhado do qual
este comando depende.

1. **Divida a pergunta em no máximo três dimensões independentes.** Independente significa que a
   resposta de um coletor nunca muda o briefing de outro. Menos é melhor. Se a pergunta é uma
   cadeia dependente única, responda-a inline e não gere nada.
2. **Roteie cada dimensão por onde sua evidência vive.** Uma dimensão respondida a partir de
   arquivos ou um repositório vai para um worker `gatherer` isolado — `citizen role run gatherer
   --workspace <repo> --prompt-file <brief>` — que é offline por design e detém apenas `Read`,
   `Grep` e `Glob`; conceda diretórios de entrada extras com `--read-dir`. Uma dimensão que
   precisa da web ao vivo vai para um worker de banda em sessão em vez disso (`worker-a` para
   uma busca ou um fetch, `worker-b` quando o achado precisa ser ponderado), gerado em paralelo
   numa única mensagem. Nunca passe uma dimensão web para um `gatherer`: ele não tem ferramentas
   web e vai retornar o briefing não iniciado. Todo briefing, de qualquer forma, nomeia a pergunta
   exata para aquela dimensão, os arquivos ou fontes de onde começar, um teto de retorno de 400
   palavras, a regra de que o detalhe vai para um arquivo de scratchpad enquanto apenas o veredito
   e os achados que mudam decisão voltam, a cota daquela dimensão no orçamento de busca da sessão,
   e o que o worker não deve decidir.
3. **Sintetize em suas próprias palavras.** Nunca cole, cite ou edite levemente um relatório. Um
   achado que não muda a resposta não aparece de forma alguma. Onde duas dimensões discordam,
   arbitre você mesmo e diga qual fonte venceu e por quê.
4. **Verifique qualquer coisa relevante** antes de confiar nela: prove que um filtro morde, faça
   uma checagem pontual num registro retornado, conte erros engolidos separadamente de resultados
   vazios.

Relate como um resumo: duas ou três frases de conclusão, depois até cinco achados com os números
por trás deles e o que significam para o leitor. Quando workers rodaram, termine com os caminhos
de arquivo de scratchpad que eles escreveram e os ids de worker que `citizen role status` vai
mostrar, um por linha. Um `gatherer` isolado não escreve nada ele mesmo: salve o detalhe que ele
retornou num arquivo de scratchpad você mesmo antes de sintetizar.
