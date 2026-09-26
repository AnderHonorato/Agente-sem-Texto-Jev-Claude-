# Visualizadores de arquitetura intercambiáveis

A implementação do visualizador, o runtime do agente e o provedor de modelo são escolhas
independentes. A integração de visualizador de arquitetura resolve o adaptador embutido de uma
distribuição por padrão. Um adaptador personalizado é uma seleção explícita do usuário. A
instalação e a sincronização nunca iniciam um visualizador.

Esta distribuição atualmente não tem nenhum adaptador de visualizador embutido. A inspeção relata
que ele está indisponível; o seletor não substitui por um visualizador personalizado. Um adaptador
embutido usa o mesmo contrato abaixo, instalado em `integrations/architecture-viewer/builtin.json`
com um id explícito.

## Selecione uma implementação

Registre um descritor JSON com id, capability, contract_version, argv, e configurações opcionais:

~~~json
{
  "id": "upstream-uml-viewer",
  "capability": "architecture-viewer",
  "contract_version": 1,
  "argv": ["/absolute/path/to/python3", "/absolute/path/to/harness/integrations/architecture-viewer/upstream.py"],
  "settings": {
    "viewer_executable": "/absolute/path/to/uml-viewer",
    "state_root": "/absolute/path/to/private-viewer-state",
    "allowed_roots": ["/absolute/path/to/an-additional-approved-root"]
  }
}
~~~

Use um candidato uml-viewer standalone instalado que exponha o protocolo 1. Java pertence a esse
visualizador opcional, não ao harness. Versões existentes sem o cliente público são incompatíveis.
Nenhuma fonte upstream ou dependência é empacotada aqui.

~~~sh
citizen integrations register --file adapter.json
citizen config set integrations.architecture-viewer.adapter upstream-uml-viewer
citizen config set integrations.architecture-viewer.implementation custom
citizen integrations show architecture-viewer --json
citizen integrations doctor architecture-viewer
citizen config set integrations.architecture-viewer.implementation builtin
~~~

O registro preserva a seleção atual. `show` inspeciona a configuração e a disponibilidade do
executável sem execução; `doctor` chama explicitamente a operação `describe` do adaptador. Nenhum
dos dois resultados qualifica um runtime nativo ou estabelece paridade de modelo ao vivo.

A precedência é padrão de distribuição, configuração de usuário, depois sobrescrita de invocação.
A configuração de projeto continua sendo só de postura: um repositório não pode nomear um
adaptador executável. Selecionar um executável externo autoriza execução local comum; descritores
não são um sandbox. `argv` é um array de argumentos literal, nunca um comando de shell.
Descritores e registros de sessão fixados armazenam configurações, então as configurações não
devem conter credenciais; adaptadores leem segredos do ambiente ou de um cofre de segredos do
sistema operacional quando necessário.

## Invoque e continue

O procedimento autoritativo é a skill architecture-viewer, compartilhada por todas as ligações de
runtime. Cada comando aceita um arquivo JSON de entrada de operação. Para o adaptador upstream:

~~~json
{
  "project_root": "/absolute/path/to/project",
  "source_roots": ["/absolute/path/to/project/src"],
  "document": {
    "path": "/absolute/path/to/snapshot.json",
    "sha256": "the SHA-256 of those exact file bytes"
  },
  "required_capabilities": ["open", "replace-document", "status", "close"]
}
~~~

O profile e toda raiz de fonte, métrica ou saída devem resolver dentro de `project_root`. Um
usuário pode pré-autorizar outro diretório existente em `settings.allowed_roots` do adaptador. A
resolução rejeita `..`, caminhos ausentes, e symlinks que escapam dessas raízes antes de o
adaptador ler o profile ou invocar o visualizador.

~~~sh
citizen viewer validate --input open.json
citizen viewer open --input open.json --implementation custom --adapter upstream-uml-viewer
citizen viewer status --session UUID
citizen viewer replace-document --session UUID --input replacement.json --request-id REQUEST_UUID
citizen viewer close --session UUID
~~~

A entrada de substituição inclui `document` e um `expected_revision` não negativo, vindo do último
reconhecimento. Publique um novo snapshot imutável antes de submeter. O cliente público upstream
possui a verificação de digest, os conflitos de revisão, os recibos, as novas tentativas e o
cancelamento; o harness não reproduz o coordenador de sessão dele.

Uma referência aberta fixa o executável do adaptador, as configurações e a identidade opaca de
sessão. Mudar padrões ou registros não consegue redirecionar status, atualização ou fechamento. Um
timeout depois de uma mutação é indeterminado: inspecione a sessão registrada e o recibo upstream
antes de tentar de novo com a requisição idêntica. Nunca reproduza automaticamente uma geração nem
reabra uma sessão incerta.

Operações de sessão persistem seu ID de requisição antes do despacho; erros indeterminados de CLI
incluem esse ID para uma nova tentativa idêntica. Reconhecimentos conhecidos sobrevivem a erros
locais de escrita de observação, que aparecem separadamente como `persistence_warning`. Se `open`
retornar `reference_persisted: false`, mantenha seu reconhecimento completo e repare o
armazenamento local antes de confiar nessa referência. Registros fixados contêm metadados mínimos
de continuação e têm um teto de 4 MiB, independentemente do limite de 1 MiB em cada requisição e
resposta de adaptador.

Referências e observações são dados privados sob o diretório de estado do harness. Coloque seus
caminhos, identidades de fonte/documento e a última revisão reconhecida nos campos de artefatos e
verificação de um handoff de tarefa neutro. Eles não transferem aprovações nem permissões nativas.
A desinstalação preserva a configuração do usuário, os registros de adaptador, as referências e as
instalações de visualizador externo.

## Contrato de adaptador 1

Um adaptador lê um objeto JSON limitado na stdin e escreve um resultado JSON na stdout, saindo em
seguida. As chaves de requisição obrigatórias são `contract_version`, `request_id` (UUID
canônico), `operation`, `implementation` (id registrado), `settings`, e `input`. O resultado
repete as quatro primeiras chaves, adiciona `status` (ok, error, ou indeterminate), e fornece
`result` (objeto) ou `error` (objeto com `code`). O sucesso exige saída zero. Entradas e saídas têm
um teto de 1 MiB; chamadas têm um prazo.

As operações obrigatórias são `describe`, `validate`, `open`, `replace-document`, `status`, e
`close`. `describe` relata capacidades como um array de nomes. `open` retorna `result.session` como
um objeto opaco não vazio, mais a identidade de documento do visualizador, epoch/revision/digest e
capacidades reais. Operações de sessão recebem esse objeto em `input.session`. Resultados falhos
não podem inventar um reconhecimento. Capacidades obrigatórias não suportadas falham antes de
`open`.

As operações opcionais `request-regeneration`, `claim-regeneration`, `complete-generation` e
`cancel-generation` exigem a capacidade `regeneration-request`. Elas usam `consumer`,
`regeneration_id` e `claim_id` quando aplicável. `cancel` recebe `target_request_id` e exige a
capacidade `cancel`. Uma requisição registra a intenção do dono autorizado atual do workflow;
nunca autoriza edições de fonte nem inicia um agente. Trabalho incompleto, expirado ou obsoleto
permanece explícito.

O adaptador upstream chama apenas a CLI pública instalada de describe/validate/open/status/control.
Ele envia envelopes JSON para esse cliente e emite arquivos de projeção EDN. Não analisa EDN, não
importa namespaces privados de visualizador, não calcula layout nem possui as revisões de
documento.

## Profile de diagrama de arquitetura 1

O profile é deliberadamente mais estreito que um snapshot de revisão. Os campos de envelope
obrigatórios são `profile: architecture-diagram`, `schema_version: 1`, e `document_id`. Os arrays
`nodes`, `relations` e `packages` podem estar vazios. `title` é opcional. Campos obrigatórios
desconhecidos são rejeitados; objetos opcionais carregam dados explicitamente omissíveis e toda
omissão é relatada.

- Nós têm `id`, `kind` e `label`; opcionalmente `package_id`, `source`, `metrics` e `optional`. Os
  tipos suportados são class, module, interface, abstract, enum e external.
- Pacotes têm `id` e `label`. Filiação de pacote aninhada não é suportada e é rejeitada.
- Relações têm `id`, `from`, `to` e `kind`, com `label` opcional. Os tipos suportados são
  association, dependency, aggregation, composition, inheritance e implements.
- Localizadores de fonte têm um caminho relativo ao repositório, uma linha positiva opcional e um
  namespace Clojure. A navegação por namespace usa as raízes de fonte autorizadas. A navegação
  genérica por caminho/linha não é anunciada; o localizador sobrevive no artefato de mapeamento com
  um diagnóstico de omissão.
- Métricas são coverage (0–1), cc, crap, killed e survived. Cada uma é um objeto com
  disponibilidade e, somente quando medido, valor. Observações ausentes/não suportadas/falhas
  permanecem ausentes na renderização. Valores de contagem não finitos, negativos e fracionários
  são rejeitados.

O mapeamento versão 1 gera hash das identidades exatas de nó e pacote em IDs de palavra-chave EDN
estáveis, preservando distinções de maiúsculas/minúsculas e identidade através de mudanças de
rótulo. IDs de relação mapeiam para seus extremos/tipo/índice projetados. A filiação de pacote é
direta; namespace é um localizador de fonte, não uma hierarquia inventada. Artefatos de mapeamento
preservam os localizadores de fonte originais. Métricas de autoria mantêm suas unidades; métricas
ausentes nunca viram zeros. Evidência, intenção e aceitação de revisão permanecem no snapshot mais
rico original e não são inferidas do diagrama.

## Limites de verificação

Testes unitários e de contrato de processo rodam sem nenhuma conta de modelo. A descoberta nativa
de skill e a interação real com o visualizador exigem testes separados em cada runtime. A
conformidade entre visualizadores compara identidades e resultados reconhecidos, não pixels ou
conjuntos de funcionalidades idênticos. A paridade do Grok apoiado em xAI exige adicionalmente
acesso de inferência autenticado; testes offline não conseguem estabelecê-la.

Rode a verificação opcional de candidato instalado com Java disponível e um desktop gráfico:

~~~sh
python3 scripts/viewer_acceptance.py --viewer /absolute/path/to/uml-viewer --evidence /tmp/viewer-result.json
~~~

Ela abre uma janela real em estado isolado, testa substituição, nova tentativa idêntica, revisão
obsoleta, continuação fixada depois de mudanças de configuração, e fechamento. Ela não muda a
configuração ao vivo nem qualifica um runtime de agente. A suíte unitária comum nem inicia um
visualizador nem chama um modelo.
