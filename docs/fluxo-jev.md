# O fluxo Jev, passo a passo

Este documento explica em detalhe o que acontece quando você roda `/jev "seu pedido"` num projeto que tem este framework instalado. Para o prompt completo que o orquestrador segue, veja [`../ORQUESTRADOR.md`](../ORQUESTRADOR.md).

## Por que "Jev"?

O nome é inspirado no projeto [Keel](https://github.com/codejunkie99/keel), um app que roteia tarefas de código entre diferentes agentes de IA. Lá, "Jev" é o nome do seletor que decide **qual agente deve executar cada tarefa**, e um "host" valida essa escolha antes de aplicar. Aqui reaproveitamos a ideia central — uma camada de decisão que escolhe o agente certo para cada pedaço do trabalho e valida o resultado antes de aceitar — só que implementada como um conjunto de agentes e prompts dentro do próprio Claude Code, sem precisar de um app separado.

Também bebemos da ideia do [model-citizen](https://github.com/JakeSelby/model-citizen): papéis nomeados com escopo e orçamento de ferramentas bem definidos, revisão por um agente que nunca viu o código sendo escrito ("fresh-context review"), e um ciclo de entrega em fases.

## Diagrama do ciclo completo

```
                         ┌─────────────────────────┐
                         │   Pedido do usuário      │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │   FASE 1 — Debate de Plano          │
                    │                                     │
                    │  debatedor-arquitetura  ──propõe──▶ │
                    │  debatedor-riscos       ──ataca───▶ │
                    │  debatedor-simplicidade ──enxuga──▶ │
                    │                                     │
                    │   orquestrador consolida o plano    │
                    └─────────────────┬──────────────────┘
                                      │ plano aprovado
                    ┌─────────────────▼──────────────────┐
                    │  FASE 2 — Divisão sem Colisão       │
                    │  (escopo de pasta/arquivo exclusivo │
                    │   por especialista, sem sobreposição)│
                    └─────────────────┬──────────────────┘
                                      │
        ┌─────────────────────────────▼─────────────────────────────┐
        │  FASE 3 — Execução (paralelo quando não há dependência)   │
        │                                                            │
        │  especialista-frontend    especialista-logica-dados       │
        │  especialista-automacao   especialista-testes             │
        └─────────────────────────────┬─────────────────────────────┘
                                      │ entregáveis
                    ┌─────────────────▼──────────────────┐
                    │  FASE 4 — Crítica Cruzada           │
                    │                                     │
                    │  critico-experiencia  → frontend    │
                    │  critico-qualidade     → lógica/dados│
                    │  critico-seguranca     → automação  │
                    │                                     │
                    │   REPROVADO ──► volta ao especialista│
                    │   dono do escopo (Fase 3)            │
                    └─────────────────┬──────────────────┘
                                      │ todos APROVADO
                    ┌─────────────────▼──────────────────┐
                    │  FASE 5 — Validação Final           │
                    │  "projeto validado" + resumo         │
                    └─────────────────────────────────────┘
```

## A regra de ouro: escopo exclusivo

O ponto central para os agentes "não se esbarrarem" é a Fase 2: antes de qualquer especialista começar a trabalhar, o orquestrador já decidiu exatamente quais arquivos/pastas cada um vai tocar. Se dois especialistas precisarem do mesmo arquivo, eles nunca rodam ao mesmo tempo — um termina e entrega antes do outro começar.

## A regra de ouro da crítica: quem produz não avalia

Cada crítico audita um especialista específico e nunca o seu próprio trabalho. Um crítico nunca edita código — ele só aprova ou reprova com uma lista objetiva de problemas, e a correção volta para quem produziu o código originalmente.

## Quando o ciclo entra em loop

Se um crítico reprovar o mesmo especialista 3 vezes seguidas pelo mesmo motivo, o orquestrador para o loop automático e explica o impasse ao usuário — geralmente é sinal de que o plano da Fase 1 tinha uma ambiguidade que não foi resolvida, não que o especialista está "errando à toa".
