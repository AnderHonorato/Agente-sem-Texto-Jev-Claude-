# Voz e formato de saída

- **Coloque a forma da saída em todo briefing de subagente**, já que um subagente não herda
  nenhuma voz; no Claude Code o hook `brief-guard` acrescenta uma quando um briefing não declara
  limite de retorno.
- **Entregáveis e postagens em nome do usuário honram primeiro qualquer perfil de voz pessoal**,
  depois usam a postura (stance) `voice` para o layout; nunca imite erros de digitação incidentais.
  Veja `plan-authoring`.
