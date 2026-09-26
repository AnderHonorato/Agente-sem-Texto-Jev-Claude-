---
name: workflow-status
description: Show progress of background Workflow runs: who has returned, who is still working, how much output. Use when the user asks about workflow progress, says "/workflows doesn't work", asks "is the workflow done", "how's the workflow going", "check the workflow", or wants to inspect a multi-agent orchestration run. (Mostre o progresso de execuções de Workflow em segundo plano: quem retornou, quem ainda está trabalhando, quanto de saída. Use quando o usuário pergunta sobre o progresso do workflow, diz "/workflows não funciona", pergunta "o workflow terminou", "como está o workflow", "verifique o workflow", ou quer inspecionar uma execução de orquestração multi-agente.)
---

# Status do workflow

Para workers de papel isolados pertencentes ao harness, rode `citizen role status` ou `citizen
role status <worker-id>`. Relate status, runtime, papel e caminho do resultado a partir desses
registros. Eles são processos de CLI separados e não aparecem como threads nativas de subagente.

Este leitor inspeciona diários de workflow do Claude locais a partir de qualquer cliente com
acesso ao sistema de arquivos. Ele não inspeciona threads nativas de agente do Codex ou execuções
hospedadas. Para essas, use a visão nativa de agente do cliente; uma busca vazia no diário local
não significa que nenhum agente está rodando.

## Rode

```bash
python3 "{skill-root}/scripts/status.py"            # execução mais recente
python3 "{skill-root}/scripts/status.py" --all      # toda execução, mais nova primeiro
python3 "{skill-root}/scripts/status.py" --limit 3  # as últimas três
python3 "{skill-root}/scripts/status.py" --run wf_eed4141a   # uma execução específica
```

Relate a saída ao usuário em prosa — as contagens, o que ainda está em andamento, e mais ou menos
quão longe a execução está. Não cole a tabela crua a menos que peçam.

## O que ele lê, e o que não deve

O script lê:

- `~/.claude/projects/*/*/subagents/workflows/wf_*/journal.jsonl` — uma linha por início de
  agente e uma por resultado de agente. Este é o registro autoritativo do que já retornou.
- **apenas a primeira linha** de cada `agent-*.jsonl`, para recuperar uma identidade legível por
  humano (a opção `label` do workflow não é persistida, então o prompt de abertura do agente é o
  melhor nome disponível).
- o script persistido sob `workflows/scripts/`, para os títulos de fase declarados.

🛑 **Nunca leia a transcrição inteira de um `agent-*.jsonl`.** Elas rotineiramente chegam a
megabytes e vão transbordar a janela de contexto. O diário mais as primeiras linhas é sempre
suficiente para status. Se o usuário quer as descobertas reais de um agente, espere o workflow
terminar e leia seu resultado retornado, ou leia o arquivo que o workflow escreveu — não a
transcrição.

## Interpretando

- **`✓` vs `•`** — um agente cuja transcrição ficou quieta por mais de ~45 segundos quase
  certamente retornou; um que ainda está sendo escrito está trabalhando. A contagem de resultados
  do diário é o número autoritativo, e os dois podem brevemente discordar enquanto um resultado
  está sendo gravado.
- **`RUNNING` sem atividade recente** em todo agente geralmente significa que a execução está
  entre fases (uma barreira), ou que o pai está sintetizando.
- **Tamanho crescente de transcrição** é um bom sinal para um agente de pesquisa — significa uso
  real de ferramenta (buscando, pesquisando) em vez de responder de memória.
- Uma execução cujo diário mostra menos entradas `started` do que há arquivos `agent-*.jsonl`
  está no meio de um fan-out; mais agentes ainda estão sendo gerados.

## Quando uma execução terminou

A própria notificação de conclusão do workflow carrega o valor retornado, que é a coisa a
relatar. Esta skill é para o intervalo antes que isso chegue — ou para verificar uma execução de
uma sessão diferente, já que o diário persiste em disco.
