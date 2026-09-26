# Rubrica de UI

Para apps web, apps iOS/Mac, landing pages, dashboards e documentos HTML autônomos.

## Eixos pontuados — 10 no total

### Hierarquia e composição (0-3)

O olho pousa na coisa mais importante primeiro, e viaja na ordem pretendida? Julgue o ritmo de
espaçamento (existe uma escala consistente, ou valores arbitrários), alinhamento (as bordas
realmente se alinham, incluindo alinhamento óptico), densidade (está apertado ou está flutuando em
espaço morto), e agrupamento (o espaço em branco comunica relação).

Buscando: um elemento primário claro, camadas secundária e terciária deliberadas, e nada
competindo pelo mesmo posto.

### Tipografia e cor (0-3)

Coerência da escala tipográfica — uma escala real, não sete tamanhos arbitrários. Peso e tamanho
fazendo o trabalho de hierarquia em vez de só a cor. Comprimento de linha numa faixa legível e
entrelinha que combina com o tamanho.

Disciplina de paleta — um conjunto pequeno e comprometido, não valores avulsos acumulados. Cor
carregando significado consistentemente. Contraste suficiente entre primeiro plano, fundo e
destaque de modo que o gate de contraste passe pelo próprio mérito em vez de ajustar um valor no
final.

### Superfície e profundidade (0-2)

Elevação, bordas, raios de canto e sombras aplicados como um sistema coerente. Toda superfície numa
dada profundidade deve parecer estar naquela profundidade. Sombras devem combinar com uma única
fonte de luz implícita e ser suaves o bastante para não lerem como um retângulo escuro.

Perdendo pontos: camadas confusas, bordas e sombras ambas fazendo o mesmo trabalho, raios que
variam sem razão, gradientes que bandeiam.

### Detalhe e estado (0-2)

Passe um pente fino por tudo. Alinhamento óptico de ícones e peso de traço consistente. Sem bordas
de meio pixel, sem quebra de linha desalinhada, sem palavras órfãs, sem descendentes cortados.

Depois os estados que carregam qualidade real de produto: **hover, foco, ativo, desabilitado,
vazio, carregando, erro**. Um design que só parece bom no seu estado feliz e totalmente populado
não está terminado. Estados vazios e de erro são onde a maioria das UIs visivelmente desmorona.

## Gates obrigatórios — pass/fail, não pontuados

- **Contraste atende WCAG AA.** 4,5:1 para texto do corpo, 3:1 para texto grande e bordas
  significativas de UI. Meça isso; não estime a olho. Isso nunca é trocado por estética.
- **Foco é visível** em todo elemento interativo, e a ordem de teclado é sensata.
- **Tokens e primitivos de design são usados**, não valores ad-hoc. Seja qual for o pacote de
  tokens e a biblioteca de primitivos do projeto, use-os. Uma tela bonita construída com valores
  hex fixos no código e números mágicos falha este gate.
- **Responsivo nos breakpoints alvo**, sem rolagem horizontal e sem sobreposição na largura
  suportada mais estreita.
- **Ambos os temas corretos**, onde a superfície suporta claro e escuro.
- **Extremos de conteúdo não a quebram** — a string realista mais longa, lista vazia, um item,
  muitos.

## Notas

O alvo não supera o sistema de design em hierarquia. Quando uma maquete gerada quer algo que os
tokens não oferecem, **o sistema vence**; registre o conflito em vez de bifurcar a paleta.

Para documentos HTML destinados a lerem como irmãos dos entregues anteriormente, combinar com a
família existente é, por si só, um gate. Estilização nova que parece boa isoladamente mas quebra o
conjunto falhou.
