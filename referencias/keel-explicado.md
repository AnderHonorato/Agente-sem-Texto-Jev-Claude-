# O que é o Keel (e o "Jev" original)

> Este documento é um **resumo em português**, escrito à mão a partir do [repositório público do Keel](https://github.com/codejunkie99/keel) (licença MIT, de codejunkie99). Não é uma cópia do código-fonte: o Keel é um app nativo de macOS (Rust + GPUI) que só compila em Mac com Apple Silicon, então trazer o código Rust para este repositório não ajudaria o Ander a rodar nada — e traduzir os identificadores internos quebraria a compilação, já que muitos nomes vêm de bibliotecas externas (GPUI, ACP). Este arquivo serve como referência de arquitetura e inspiração para o [framework Jev](../ORQUESTRADOR.md) deste repositório.

## Em uma frase

Keel é um **ambiente de trabalho de código nativo do macOS** ("local-first") que roda os agentes de código que você já usa (Claude Code, Codex, Cursor, Grok, Hermes, pi) e decide, tarefa por tarefa, **qual agente/backend deve executar cada uma** — com um "host" que sempre confere essa escolha antes de aplicá-la.

## As três peças centrais

### 1. O seletor de decisão

Para cada tarefa nova (não fixada a um agente específico), um dos dois seletores escolhe a rota:

- **Laya** — roda localmente, usando Core ML (aprendizado de máquina embarcado no próprio Mac). É o modo padrão.
- **Jev** — hospedado por um serviço chamado TypeSafe. É opcional ("opt-in") e exige uma credencial local protegida.

Os dois só têm uma função: escolher um candidato elegível dentre as rotas preparadas pelo host, **ou se abster** (dizer "não sei decidir, segue o fluxo normal").

### 2. O host valida a escolha

Isso é o ponto mais importante do design: **nenhum seletor decide sozinho**. O programa principal ("host") sempre confere a escolha antes de aplicá-la. Uma escolha rejeitada, desatualizada ou expirada cai de volta para a rota comum (chamada de modo "Normal" — sem seletor nenhum, só o fluxo padrão do provedor de código escolhido).

### 3. O recibo de decisão

Toda decisão (escolhida por Laya, por Jev, ou uma abstenção) deixa um "recibo" limitado na transcrição da sessão: quais eram os candidatos, qual foi o resultado, como foi validado, se caiu para o modo normal (fallback), e qual foi o resultado observado depois. Isso existe para permitir auditoria e, no futuro, comparação entre decisões — os próprios mantenedores deixam claro no README que **"decisões automáticas de treinamento ainda não estão implementadas"**: hoje é só registro e comparação manual, não aprendizado automático.

## Os três modos, lado a lado

| Modo | Onde roda | Exige | O que acontece |
| --- | --- | --- | --- |
| **Laya** (padrão) | Localmente, via Core ML | Um "worker" e um checkpoint de modelo fixado | Escolhe entre candidatos preparados pelo host, ou se abstém |
| **Jev** (opcional) | Hospedado pela TypeSafe | Uma credencial local já protegida | Envia um pedido de decisão limitado direto para a TypeSafe |
| **Normal** | Nenhuma chamada de seletor | A configuração normal do seu provedor de código | Usa a rota comum do harness, sem decisão nenhuma |

Só um backend roda por decisão. E um detalhe importante que o próprio projeto destaca: **um seletor local não significa que o agente de código roda localmente** — cada provedor (Claude Code, Codex etc.) continua com sua própria autenticação e configuração de modelo, o Keel só decide qual deles chamar.

## O "grafo de agentes" (a parte mais visual)

Uma das funcionalidades mais recentes do Keel é o **grafo de agentes** (atalho <kbd>⇧⌘G</kbd>): uma visão que mostra, ao vivo, cada sessão ativa como um nó de "agente", os subagentes dela como nós filhos, e os arquivos que cada um lê ou escreve como nós de "contexto compartilhado". Dá para clicar num nó para direcionar ou parar aquele agente, e clicar duas vezes para abrir a sessão dele.

Essa é, na prática, a forma do Keel de mostrar visualmente algo parecido com o que o framework Jev deste repositório (`ORQUESTRADOR.md`) faz em texto: vários agentes trabalhando ao mesmo tempo, sem pisar no espaço um do outro.

## O que o Keel deixa claro que ele NÃO faz (limitações assumidas)

Isto está documentado às claras no próprio README do projeto, e vale reter porque mostra honestidade de escopo — um padrão bom para copiar em qualquer projeto:

- Os recibos de decisão dão suporte a avaliação, mas **treinamento automático não está implementado**.
- As checagens de build não comprovam sozinhas que os resultados de codificação melhoraram.
- Nem toda ferramenta ACP externa passa pelo Laya ou pelo Jev.
- `keel computer-use decide` só escolhe um ID de ação já preparado — ele não clica nem digita de verdade.
- Entrada de voz usa só o Dictation do macOS; não há voz em tempo real nativa do Codex nem sincronização em nuvem.
- Os pacotes do app são builds de desenvolvimento assinados "ad hoc" — distribuição pública ainda precisa de assinatura Developer ID e notarização da Apple.

## Por que isso não roda no seu PC/celular

O Keel é escrito em **Rust**, usando um framework de interface chamado **GPUI**, e exige **Apple Silicon com macOS 15 ou mais recente** — tanto para compilar quanto para rodar o modelo Laya localmente via Core ML (tecnologia de aprendizado de máquina exclusiva da Apple). Não existe build para Windows, Linux ou uso via navegador/celular. Por isso a ideia central foi trazida para este repositório como o **framework Jev em `.claude/agents/`** (que roda dentro do Claude Code, em qualquer sistema operacional, PC ou celular), em vez de copiar o app original.

## Créditos

Keel é um projeto de [codejunkie99](https://github.com/codejunkie99/keel), licenciado em MIT. Ele reaproveita uma interface derivada do projeto Avid e um componente embarcado do DeepSeek, e usa o [Laya](https://github.com/NandhaKishorM/laya) e o [runtime Core ML do Laya](https://github.com/mizorewww/laya-coreml) para inferência local. O framework e o artigo por trás do conceito "Jev" ficam num repositório separado, o [Jev Engineering](https://github.com/codejunkie99/jev-engineering).
