---
description: Answer a research question with parallel read-only gatherers and one synthesized digest.
argument-hint: <question>
---

# Research (pesquisa)

A pergunta: $ARGUMENTS

Carregue as skills `transcript-hygiene` e `api-verification` por completo antes de criar qualquer
subagente. Elas carregam os limites de retorno e o orçamento de busca compartilhado dos quais este
comando depende.

1. **Divida a pergunta em no máximo três dimensões independentes.** Independente significa que a
   resposta de um gatherer nunca muda o brief de outro. Menos é melhor. Se a pergunta é uma única
   cadeia dependente, responda-a inline e não crie nenhum subagente.
2. **Roteie cada dimensão por onde sua evidência vive.** Uma dimensão respondida a partir de
   arquivos ou de um repositório vai para um worker `gatherer` isolado — `citizen role run
   gatherer --workspace <repo> --prompt-file <brief>` — que é offline por design e tem apenas
   `Read`, `Grep` e `Glob`; conceda diretórios de entrada extras com `--read-dir`. Uma dimensão
   que precisa da web ao vivo vai para um worker de banda dentro da sessão (`worker-a` para uma
   busca ou um fetch, `worker-b` quando a constatação precisa ser ponderada), criado em paralelo
   em uma única mensagem. Nunca entregue uma dimensão de web a um `gatherer`: ele não tem
   ferramentas de web e devolverá o brief não iniciado. Todo brief, de qualquer forma, nomeia a
   pergunta exata daquela dimensão, os arquivos ou fontes de onde partir, um limite de retorno de
   400 palavras, a regra de que o detalhe vai para um arquivo de scratchpad enquanto só o veredito
   e as constatações que mudam decisão voltam, a fatia daquela dimensão no orçamento de busca da
   sessão, e o que o worker não deve decidir.
3. **Sintetize com suas próprias palavras.** Nunca cole, cite ou edite levemente um relatório. Uma
   constatação que não muda a resposta não aparece de jeito nenhum. Onde duas dimensões
   discordarem, arbitre você mesmo e diga qual fonte venceu e por quê.
4. **Verifique tudo que é fundamental** antes de confiar nisso: prove que um filtro está mordendo,
   confira pontualmente um registro retornado, conte erros engolidos separadamente de resultados
   vazios.

Reporte como um resumo: duas ou três frases de conclusão, depois até cinco constatações com os
números por trás delas e o que significam para o leitor. Quando workers rodaram, termine com os
caminhos dos arquivos de scratchpad que eles escreveram e os ids de worker que `citizen role
status` vai mostrar, um por linha. Um `gatherer` isolado não escreve nada por conta própria: salve
você mesmo o detalhe retornado por ele em um arquivo de scratchpad antes de sintetizar.
