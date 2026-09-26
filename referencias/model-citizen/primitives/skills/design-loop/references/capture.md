# Capturando o estado atual

**Verifique se o comando de captura funciona antes da rodada 1.** Um loop que descobre na rodada 3
que estava julgando uma página em branco ou uma imagem desatualizada queimou toda rodada anterior.

Cada captura deve ser da **coisa real rodando**, no mesmo enquadramento e viewport que o alvo. Mudar
o enquadramento entre rodadas torna as pontuações sem sentido.

## Encontre primeiro o caminho próprio do projeto

Procure uma forma existente de rodar e capturar antes de construir uma:

- Uma skill de projeto cobrindo lançamento ou renderização
- A skill nativa `run` do Claude Code, que lança o app e pode tirar screenshot dele
- Scripts existentes de render ou galeria no repositório

Use o que existe. Um script avulso que duplica o renderizador do repositório vai divergir dele.

## Por superfície

| Superfície | Caminho |
| --- | --- |
| **Web / doc HTML** | Screenshot de navegador headless num viewport fixo. Capture cada breakpoint exigido e ambos os temas como imagens separadas. |
| **iOS / Mac app** | Screenshot do simulador, ou o utilitário de screenshot do SO contra um build rodando. Dispositivo e fator de escala fixos. |
| **Blender** | `get_viewport_screenshot` do MCP do Blender, ou um render com script. Leia as instruções do servidor MCP antes de escrever o script. |
| **Renderizador ou ferramenta de mock do projeto** | Os próprios scripts de captura do repositório, se ele os tiver. Rotule a saída como **Mock** ou **Renderer** para que uma imagem conceitual nunca seja confundida com a superfície entregue. |
| **Jogo no zoom de jogabilidade** | Capture nos níveis de zoom reais que o jogador usa, não apenas no enquadramento hero. O eixo de legibilidade depende disso. |

## Lacunas conhecidas

**Um projeto web sem ferramental de screenshot não pode rodar este loop ainda.** Montar uma
captura de navegador headless é um pré-requisito e é trabalho real — levante isso em vez de forjar
uma captura a partir de uma galeria de componentes ou uma maquete estática.

## Regras de captura

- **Uma captura por rodada, salva como `.design-loop/round-<n>.png`.** Mantenha todas; o juiz
  precisa da anterior e você precisa da série para detectar estagnação.
- **Superfícies multi-imagem** — breakpoints, temas, níveis de zoom — passe o conjunto completo
  para o juiz a cada rodada. Não alterne qual você mostra; isso esconde regressões.
- **Nunca substitua uma captura ao vivo** por uma maquete, uma galeria de componentes ou um render
  anterior. O valor inteiro do loop é que ele mede o artefato real.
- **Corrija quebras antes de capturar**, não depois. Falhas de carregamento de asset, orientação
  errada e fontes faltando produzem uma captura que desperdiça uma rodada de juiz em lacunas que
  você já conhece.
