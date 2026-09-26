# Atribuição

Registrado conforme a postura (stance) `licensing` escolhida
(`~/.claude/rules/harness-stances/licensing.md`) e o procedimento `licensing-review`. Esta skill é
uma ferramenta de desenvolvimento e não é entregue em nenhum produto; o registro é mantido porque a
política se aplica a material copiado independentemente do destino.

| Campo | Valor |
| --- | --- |
| **Fonte** | https://github.com/achimala/dream-loop |
| **Criador** | Anshu Chimala |
| **Versão** | Estado do repositório no intervalo de commits terminando em 09/09/2026 (revisado em 15/09/2026) |
| **Licença** | MIT — permite uso comercial, modificação e redistribuição, exige que o aviso de copyright e permissão seja preservado |
| **Texto da licença** | Reproduzido abaixo |
| **O que foi retirado** | A estrutura do loop (alvo travado → construir → capturar → juiz independente → corrigir → sair), o juiz de contexto novo com uma rubrica pontuada e handoff do veredito anterior, o critério de saída por estagnação, e a restrição "nomeie a causa e a correção, não o sintoma" no feedback do juiz |
| **O que não foi retirado** | Nenhum código. `scripts/fal-batch.mjs`, `scripts/preview-server.py` e `references/fal.md` foram deliberadamente excluídos |

## Modificações

- **Rubricas reescritas.** As pontuações originais são Composição / Iluminação / Materiais /
  Detalhes, apenas para 3D. A nossa adiciona uma rubrica de UI, e substitui o eixo 3D "Detalhes"
  por **legibilidade no zoom do jogo**.
- **Gates obrigatórios adicionados.** Acessibilidade, aderência a tokens de design, orçamento de
  runtime, escala do mundo real e licenciamento de assets são pass/fail e bloqueiam a saída em
  qualquer pontuação. O original não tem equivalente.
- **Objetivo mudado.** O original tem como alvo a identidade de pixel — *"não deve haver um único
  pixel diferente"*. O nosso trata o alvo como uma referência que perde para o sistema de design,
  para a escala do mundo real e para acessibilidade onde eles conflitam.
- **Obtenção de assets removida por completo.** O original ranqueia download da internet em
  primeiro lugar e imagem-para-3D em segundo, sem checagem de licença, e instrui explicitamente o
  agente a sobrescrever uma restrição de não-baixar do usuário. Ambos são incompatíveis com a
  postura `licensing` escolhida e qualquer regra de asset com escopo de caminho que um projeto
  carregue; a obtenção defere a essas regras em vez disso.
- **Orçamento de rodadas e escalonamento adicionados**, alinhados à regra permanente de
  escalonamento de loop autônomo.
- **Seleção de workflow baseada em tier removida.** O original bifurca entre o tier de assinatura
  ChatGPT Plus vs Pro e inclui um modo de orquestração específico do Codex. O nosso bifurca por
  superfície.

## Licença MIT

```
MIT License

Copyright (c) 2026 Anshu Chimala

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
