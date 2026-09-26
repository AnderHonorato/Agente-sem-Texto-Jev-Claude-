# Estabelecendo o alvo

O alvo é o ponto principal de tudo. Um loop sem uma referência externa travada degenera no agente
avaliando o próprio gosto, que é exatamente a falha que esta skill existe para prevenir.

**Trave-o antes da rodada 1 e nunca o regenere no meio do loop.** Se o alvo acabar se revelando
errado, pare o loop, diga isso, combine um novo, e reinicie a contagem de rodadas.

## De onde um alvo vem, do melhor para o pior

### 1. O usuário forneceu um

Use-o diretamente. Uma maquete, um screenshot de que ele gosta, uma exportação do Figma, a tela de
um concorrente, um render aprovado anteriormente. Não "melhore" primeiro.

### 2. Um artefato aprovado já no repositório

Um render anterior abençoado, uma tela existente cuja barra de qualidade você está igualando, um
documento irmão cuja estilização o novo precisa combinar. Este é o padrão certo para **qualquer
coisa que precise ler como parte de um conjunto** — combinar com um sistema de design, ou um doc
HTML que precisa parecer irmão dos entregues antes dele.

Barato e autossuficiente, mas só consegue avançar em direção ao que já existe. Diga isso quando o
briefing está pedindo uma mudança de patamar genuína.

### 3. Uma prancha de direção feita por humano

Para uma mudança de patamar real, peça uma em vez de inventá-la. Uma prancha por classe de asset ou
tipo de tela define um teto muito mais alto do que qualquer frame gerado.

### 4. Gere um

Por último, e dependente do modo. Veja as restrições abaixo.

## Refinar em vez de divergir

Se a coisa já existe, **capture-a primeiro e alimente essa captura ao modelo de imagem como base**,
pedindo uma versão refinada seguindo a direção do usuário. Gerar apenas a partir do prompt produz
um alvo que diverge em vez de melhorar, e o loop então gasta toda rodada lutando para virar um
produto diferente.

## Fazendo o prompt para um alvo gerado

Peça um **screenshot alvo exato e realista** da coisa terminada. Não arte conceitual, não uma
imagem cinematográfica, não uma interpretação de artista, não um mood board. Você vai tentar
combinar de perto com ele, então precisa retratar algo construível.

Evite as palavras "arte conceitual", "artístico", "ilustração" e "pintura" no prompt.

## Restrições por modo

### ui

Gerar um alvo está bem. Uma maquete é uma referência que se olha e se descarta — nenhum pixel
gerado é entregue.

Mas o alvo não supera o sistema de design. Onde uma maquete gerada conflita com os tokens,
primitivos ou gates de acessibilidade do projeto, **o sistema vence e o alvo está errado naquele
ponto**. Anote o conflito em `notes.md` em vez de seguir silenciosamente um ou outro.

### scene

**Um frame gerado pode definir a direção. Ele nunca pode ser uma fonte para geometria ou textura
entregue.** Prefira uma prancha de referência aprovada ou um render abençoado anterior como o alvo.

Duas razões, ambas relevantes:

- **Licenciamento.** Imagem gerada → imagem-para-3D → asset entregue é uma cadeia de derivação em
  termos não resolvidos. A postura `licensing` escolhida mantém material não resolvido fora da
  produção.
- **Correção.** Um modelo de imagem não respeita escala do mundo real, orçamento de LOD ou
  legibilidade no zoom jogável. Combinar com o frame dele produz uma foto hero linda que está
  errada no jogo.

Onde o alvo e a escala do mundo real discordam, **a escala vence**.
