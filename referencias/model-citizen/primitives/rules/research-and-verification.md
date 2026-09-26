# Pesquisa e verificação

- **A busca na web tem um teto por sessão — 200 chamadas no Claude Code — e é compartilhada por
  todo subagente.** Estime cerca de 10 agentes com 20 buscas, ou 6 com 30, e escalone execuções
  maiores em várias sessões. Depois de um fan-out, verifique a contagem de cada subagente e rode de
  novo as dimensões que ficaram sem cota numa sessão nova.
- **Prove que um filtro morde:** envie um valor que nunca pode dar match e confirme que o resultado
  fica vazio.
- **Faça uma checagem pontual de um registro retornado** contra o campo pelo qual você filtrou
  antes de confiar no conjunto.
- **Um erro por item engolido é desconhecido, não ausente.** Conte falhas separadamente de
  resultados vazios.
- **Reverifique a especificação atual** antes de presumir que uma solução alternativa documentada
  ainda é necessária.
- **Prefira fontes primárias.** Rastreie toda regra em que você se apoia até uma fonte citável;
  quando o cabeçalho e o corpo de um arquivo discordam, encontre o código ou a especificação que
  decide. Veja `api-verification`.
