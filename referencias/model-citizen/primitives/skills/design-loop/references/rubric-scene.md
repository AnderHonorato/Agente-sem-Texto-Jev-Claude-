# Rubrica de cena

Para cenas 3D, visões de jogo, assets renderizados e saída do Blender.

## Eixos pontuados — 10 no total

### Composição e escala (0-3)

Posição da câmera, enquadramento e distância focal. Legibilidade da silhueta — o preditor único
mais forte de se um asset lê bem. Proporção dentro de um asset e entre assets.

**A escala do mundo real é julgada aqui, não presumida.** Um veículo que é sutilmente grande demais
em relação a um prédio é uma falha de composição mesmo quando toda superfície parece correta.

### Iluminação e atmosfera (0-3)

Paleta de cores, exposição, suavidade e direção da sombra, contraste, oclusão de ambiente.
Reflexos, especulares, brilhos e bloom onde o alvo os tem. Profundidade atmosférica — névoa,
neblina, perspectiva aérea — fazendo a separação de distância.

Falha comum: a cena lê de forma uniformemente escura demais ou plana demais contra o alvo.
Verifique a exposição geral antes de perseguir materiais individuais.

### Materiais e textura (0-2)

Toda superfície deve ler como a substância que é. Variação de rugosidade, desgaste, dano de borda,
translucidez, umidade. Mapas normais e de rugosidade presentes onde importam.

Perdendo pontos: superfícies quadradas, plásticas, uniformemente lisas ou de cor plana — a menos
que o alvo faça isso deliberadamente também. Ruído procedural substituindo uma textura real é uma
falha, não um atalho.

### Legibilidade no zoom de jogo (0-2)

**O eixo que uma foto hero não vai te dar.** Julgue a cena nos níveis de zoom reais que o jogador
usa, não apenas no enquadramento que a favorece.

A silhueta ainda lê? O detalhe sobrevive, ou vira uma mistura confusa? Vira ruído e cintilação? Os
assets permanecem distinguíveis entre si num relance? Uma cena que pontua 8 nos primeiros três
eixos e 0 aqui não está pronta para entrega.

## Gates obrigatórios — pass/fail, não pontuados

- **Orçamento de runtime cumprido** na resolução e zoom alvo. Tempo de frame e chamadas de
  desenho medidos na cena composta, não estimados por asset.
- **Todo asset tem uma licença qualificadora registrada**, uma entrada no manifesto de terceiros e
  avisos entregues. Veja a postura `licensing` escolhida e qualquer regra de asset com escopo de
  caminho que o projeto carregue. Material não resolvido falha este gate e fica de fora.
- **Escala do mundo real preservada.** Onde o alvo e a escala discordam, a escala vence.
- **LOD presente** onde a classe exige, e transições de LOD não saltam visivelmente.
- **Estilo coerente com os assets existentes.** Assets importados são normalizados para a nossa
  direção em vez de misturar estilos. Um asset fotorrealista num conjunto estilizado é uma
  regressão, por melhor que seja.

## Notas

Otimize apenas depois que a pontuação superar a barra, então **rejulgue** — ganhos sem perdas
primeiro, depois mudanças com custo visual mínimo. Uma passada de otimização que baixa a pontuação
silenciosamente não teve sucesso.

Rotule a evidência como **Mock**, **Renderer**, ou **Both**. Um render offline bonito não prova
nada sobre o jogo. Obter um asset não é por si só um upgrade visual.
