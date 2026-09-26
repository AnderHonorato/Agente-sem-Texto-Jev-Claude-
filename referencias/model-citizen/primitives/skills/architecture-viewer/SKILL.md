---
name: architecture-viewer
description: Open or update an architecture diagram with the selected builtin or custom viewer, preserving a neutral session handoff. Use when asked to inspect architecture interactively or continue an existing diagram session.
---

# Visualizador de arquitetura

1. Inspecione a seleção com `citizen integrations show architecture-viewer --json`. Use uma
   sobrescrita explícita de invocação apenas quando solicitado. Relate implementações
   indisponíveis; nunca mude a seleção silenciosamente nem instale uma alternativa.
2. Rode `citizen integrations doctor architecture-viewer` para obter as capacidades reais do
   adaptador selecionado. Capacidades obrigatórias faltando são erros, não evidência de que um
   visualizador diferente foi selecionado.
3. Prepare um snapshot imutável e autorizado. Para o adaptador upstream use `architecture-diagram`
   perfil 1, uma raiz de projeto explícita, raízes opcionais de fonte/métricas, e o SHA-256 dos
   bytes exatos do perfil. Mantenha o perfil e as raízes dentro daquele projeto a menos que o
   usuário tenha pré-autorizado uma raiz de adaptador adicional. Preserve observações faltantes;
   relate omissões de projeção.
4. Valide com `citizen viewer validate --input INPUT_JSON`, depois invoque `citizen viewer open
   --input INPUT_JSON`. Registre o `session_reference` retornado, o adaptador, a identidade do
   documento, a revisão, o digest e os caminhos reais de capacidades e mapeamento/evidência.
5. Para uma atualização, consulte `citizen viewer status --session REFERENCE`, prepare uma nova
   entrada imutável, depois use `citizen viewer replace-document --session REFERENCE --input
   REPLACEMENT_JSON --request-id REQUEST_UUID`. Inclua a `expected_revision` observada. Apenas um
   resultado de sucesso reconhecido significa que o visualizador aceitou o documento.
6. Preserve o ID da requisição ao inspecionar resultados incertos. Um timeout não é cancelamento.
   Conflitos, épocas obsoletas, reivindicações expiradas e geração indeterminada exigem
   reconciliação explícita; não reabra ou reproduza automaticamente trabalho que altera a fonte.
7. Um pedido de regeneração pertence ao dono autorizado atual do workflow. Reivindique-o apenas com
   a identidade de consumidor configurada e a capacidade exigida, capture a identidade da fonte,
   rode os gates normais de mudança de fonte, e publique com a revisão reivindicada. Seleção e
   visualização não autorizam edições. Um visualizador desanexado continua útil para visualização.
8. Coloque as referências de sessão e evidência no handoff de tarefa compartilhado. Continue
   usando a sessão fixada entre runtimes, estabelecendo permissões nativas de novo. Encerre com
   `citizen viewer close --session REFERENCE` quando o usuário terminar.

A configuração completa, o envelope do adaptador, o mapeamento de perfil e as limitações estão
documentados em `docs/viewer-integrations.md` no checkout do harness. Vínculos de runtime
compartilham este procedimento; a seleção de visualizador é independente da seleção de
modelo/provedor.
