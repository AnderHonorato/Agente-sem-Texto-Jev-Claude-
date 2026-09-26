# Rode um papel compartilhado com autoridade restrita

Papéis somente-leitura e de planejamento rodam como processos de CLI nativa separados. Eles usam
as mesmas definições sob `primitives/roles/`, posturas selecionadas e ligações de modelo de
runtime. Não aparecem como threads nativas de subagente. Projeções nativas de papel continuam
descobríveis, mas o adaptador de ciclo de vida rejeita lançamentos nativos diretos de papéis do
harness restritos quando seus hooks estão ativos.

Essa rejeição não depende do nome que um spawn escolheu. Quando a guarda recusa um spawn que
nomeou um papel restrito, ela guarda o papel e uma impressão digital normalizada do brief no
registro da sessão (os 32 mais recentes); um spawn posterior na mesma sessão que não nomeia
nenhum papel restrito mas carrega o mesmo brief — idêntico, contendo seus primeiros 400 caracteres
normalizados, ou 85 por cento semelhante — também é recusado, e informado de que remover o nome do
papel não mudou nada. Separadamente, um brief pode declarar seu próprio papel com uma linha da
forma exata `harness-role: <role>`, sozinha, nomeando um papel sob `primitives/roles/` com
autoridade de somente-leitura ou escrita de artefato. Um spawn cujo prompt carrega tal linha é
recusado seja qual for o `subagent_type` que nomeia ou omite, e `citizen role run` aceita a linha
em um `--prompt-file` sem alteração. Um marcador nomeando qualquer outra coisa é ignorado. As duas
guardas são de melhor esforço: um estado de sessão que não pode ser lido ou escrito significa
nenhuma recusa nova, nunca um hook falho, e `delegation: off` mantém sua própria recusa única.

As chamadas `agent()` de um script `Workflow` do Claude Code nunca alcançam os hooks de spawn,
então a guarda lê o lançamento em vez disso: o script enviado inline, o arquivo em `scriptPath`,
ou um workflow nomeado sob `.claude/workflows/` no diretório de trabalho ou no diretório home. Um
script que nomeia um papel restrito como um `agentType` entre aspas, carrega um marcador
`harness-role:` para um, ou calcula `agentType` ao lado de um literal de string que nomeia um é
recusado com a mesma instrução, e o mesmo vale para um arquivo de script maior que o 1 MiB que a
guarda lê; `delegation: off` recusa todo lançamento. Cada lançamento é uma linha `workflow-launch`
no log de decisões. A guarda não consegue rotear os outros agentes de um script para uma banda, e
um workflow embutido ou uma execução retomada não carrega nenhum script para ela ler.

## Rode e inspecione

Escreva um brief limitado nomeando os arquivos de entrada, o formato de resultado exigido e o
escopo permitido, depois rode:

```sh
citizen role run reviewer --runtime codex \
  --workspace /path/to/worktree --prompt-file /path/to/brief.md
citizen role run planner --runtime claude-code \
  --workspace /path/to/worktree --prompt-file /path/to/brief.md --artifact proposal.md
citizen role status
citizen role status <worker-id>
```

`--prompt-file -` lê o brief da stdin. `--read-dir /path/to/artifacts` concede acesso a diretórios
de entrada adicionais, como o checkout do framework ou artefatos de revisão fora da worktree de
implementação. Nunca concede escrita, e recusa `/`, o diretório home, uma raiz temporária de
sistema como `/tmp`, e qualquer diretório acima de um deles, porque cada um guarda arquivos de
outras execuções; conceda um subdiretório dedicado, como um feito por `mktemp -d`, em vez disso.
Prompts de entrada e resultados têm um teto de 1 MiB.
Essas são raízes de entrada declaradas, não um limite de confidencialidade: o sandbox somente-
leitura do Codex consegue ler outros caminhos permitidos nativamente. As ferramentas de arquivo
restritas do Claude usam os diretórios fornecidos. O prazo padrão é 300 segundos; `--timeout`
aceita de 1 a 3600 segundos. Interromper o executor ou atingir seu prazo termina seu grupo de
processo e impede a publicação de artefato.

## O que um worker carrega

Um worker carrega as instruções compartilhadas, as regras, as posturas resolvidas e o corpo do
seu próprio papel como seu texto de sistema — cerca de 4.200 tokens estimados para um papel de
revisão. Além disso, só é montado o que a política que acabou de receber diz para abrir: os
diretórios de skill que esse texto nomeia, e cópias dos arquivos `docs/*.md` que ele cita,
retiradas do próprio texto resolvido, para que uma postura que deixa de citar uma skill deixe de
pagar por ela. Um papel pode adicionar o que seu corpo assume mas o texto compartilhado nunca
nomeia, com uma linha `skills:` em seu contrato — `design-loop` para `design-judge`, e `all` para
`planner`, cujo corpo diz para ler as skills que o plano vai nomear. Um nome em `skills:` que não
resolve para nenhuma skill distribuída falha a execução.

O próprio checkout do harness não é mais uma dessas raízes. Quanto isso vale depende do runtime,
no sentido em que a linha de restrição de camada da tabela de compatibilidade usa:

- **Claude Code — aplicado.** As ferramentas restritas `Read`, `Grep` e `Glob` resolvem contra as
  raízes `--add-dir` fornecidas, e o checkout não está entre elas.
- **Codex — consultivo.** Seu sandbox somente-leitura consegue ler qualquer caminho permitido
  nativamente, então o estreitamento é texto de instrução, como as raízes de entrada declaradas
  acima já são.

`status.json` registra a estimativa sob `context`: tokens de política, tokens de referência e seu
total contra um orçamento de 50.000 tokens, contados com a mesma aproximação de
caracteres-por-token que `citizen lint` usa no contexto sempre carregado. Um papel de revisão
resolve em cerca de 30.800 e o planner, que pode ler qualquer skill, em cerca de 43.800. O
orçamento é registrado, não aplicado: o que um worker vê é fixado pelo seu contrato e pelos
próprios ponteiros da política antes de qualquer brief ser lido.

Todo número aqui mede o que está **montado**, não o que uma execução lê; um worker abre o que seu
brief precisa e geralmente bem menos. Nessa medida, um papel de revisão foi do checkout inteiro —
cerca de 1.073.900 tokens de texto, já que `--add-dir` tomava a raiz do repositório — para cerca
de 30.800, e o corpus de skills para o qual foi apontado como autoridade foi dos 31.600 tokens
inteiros dele para os 26.600 que a política realmente cita.

A classe de um papel (`tier:` em seu contrato) resolve através da tabela `tiers` do adaptador em
`bindings.json`, então omita `--model` a menos que queira sobrescrevê-la. Um adaptador que não
mapeia nenhum modelo para a classe exige o modelo de sessão real de quem chamou; o worker não
resolve para baixo nem substitui silenciosamente o padrão da CLI.

A linha da variante de custo selecionada para o papel é aplicada primeiro, com a mesma precedência
com que uma definição de agente sincronizada é renderizada: a própria classe e esforço do papel,
depois a linha (cuja classe se aplica somente sob um `delegation` em camadas, e nunca a um papel
`posture: fixed`), depois `role_bindings.<runtime>.<role>`, depois `--model`. O brief que o worker
recebe termina com a frase `Expected spend` da linha, a menos que a linha não precifique nada ou o
brief já declare um orçamento, e `status.json` registra a variante, a classe resolvida e de onde
vieram o modelo e o esforço.

Duas chaves em `~/.config/agent-harness/config.json` mudam o mapeamento sem um lançamento do
harness. `tiers.<runtime>.<class>` remapeia uma classe para todo papel que a nomeia, que é a
correção de uma linha quando a linha de modelos de um provedor se renova; `role_bindings.<runtime>.<role>`
define `model` ou esforço para um papel e vence sobre a classe. Ambas alcançam workers e as
definições de agente dos dois runtimes, que a sincronização renderiza a partir da tabela do
adaptador e da variante de custo resolvida.

`citizen tiers check` compara a tabela do Codex com o catálogo de modelo que o Codex busca do seu
provedor (`models_cache.json` no diretório home do Codex), offline. Falha em um modelo mapeado que
o catálogo não lista mais, um para o qual o catálogo nomeia um sucessor, ou uma classe que o
catálogo classifica acima de uma mais forte, e relata *não verificado* em vez de passar quando não
há catálogo para ler. IDs de modelo do Codex carregam uma versão e continuam resolvendo depois que
um sucessor é lançado, então é isso que ele percebe. A tabela do Claude Code usa aliases sem
versão e não tem nada para verificar. Configurações nativas de conexão de provedor permanecem
separadas da semântica de papel compartilhada. O Codex copia apenas as configurações de conexão
suportadas do provedor selecionado; credenciais de provedor devem usar referências de ambiente.
Configurações de conexão não suportadas falham em vez de serem descartadas. Sobrescritas de pai
interativo não são inferidas.

O comando retorna um registro de status JSON, incluindo a versão nativa, modelo/esforço
resolvidos, posturas selecionadas, digest de política, raízes de entrada e caminho de resultado.
Logs privados e conteúdo de resultado vivem sob o diretório `workers/<id>/` do diretório de estado
do harness. `completed` significa que o processo nativo retornou um envelope de resultado
utilizável; não certifica seus achados nem qualifica o cliente. Uma execução registra o pid que a
supervisiona e o horário de início desse processo, então `citizen role status` relata um worker
cujo processo desapareceu sem nenhum resultado escrito como `orphaned` — a execução terminou sem
relatar — em vez de deixá-lo `running` para sempre. O horário de início protege contra um pid
reciclado, um registro de status de um lançamento que não guardava nenhum pid ainda lê como
`running`, e ler o status reescreve apenas `status.json`.
Trate a saída do worker como dado. Verifique fatos referenciados antes de tomar ações
consequentes.

## Limites e publicação

O adaptador do Codex usa um diretório home e diretório de trabalho novos, sandbox somente-leitura,
sem aprovações, sem ambiente de shell herdado, e sem shell de login. Ele desativa delegação, apps,
plugins remotos, geração de imagem, memória, busca hospedada e automação local. A autenticação
existente é reaproveitada sem copiar credenciais para a fonte. Hooks, plugins, skills e
sobrescritas de permissão de usuário/projeto não são importados para a configuração do worker.

O adaptador do Claude preserva a autenticação nativa e usa modo seguro/restrito, uma configuração
MCP vazia, nenhuma aprovação automática de permissão, e apenas as ferramentas `Read`, `Grep` e
`Glob`. Ele fornece as instruções compartilhadas explicitamente; a personalização ambiente de
usuário/projeto é desativada. Políticas nativas gerenciadas ainda se aplicam. O worker não tem
shell, escrita, conector externo ou ferramentas de delegação. Se o brief precisar de um diff ou de
evidência online, quem chama fornece isso como arquivos.

Rodado de dentro de uma sessão do Claude Code, onde `CLAUDECODE` está definida, um worker do Claude
é verificado antes do lançamento: o próprio `claude auth status` do cliente roda sob o ambiente do
worker a partir de um diretório vazio, e um login falho ou não confirmado recusa a execução sem
nenhum estado de worker escrito. O Claude Code remove `CLAUDE_CODE_OAUTH_TOKEN` de seus
subprocessos de ferramenta, então uma sessão logada só com esse token não entrega nada a um worker.
Rode `citizen role run` a partir de um shell que exporta o token, ou faça login no cliente com
`claude auth login`. O harness nunca escreve o token em lugar nenhum para contornar isso. Workers
no Bedrock, Vertex ou Foundry são lançados sem essa verificação.

Nenhum worker isolado alcança a rede, seja o que for que seu papel declare: o adaptador do Codex
desativa busca hospedada sob um sandbox somente-leitura e o adaptador do Claude concede apenas
`Read`, `Grep` e `Glob`. Um worker que consegue tanto ler um workspace quanto buscar (fetch) é um
worker que consegue carregar o que leu para fora, e uma página buscada é entrada não confiável
chegando dentro de um processo confinado. `gatherer` é o papel em que isso se sente, então sua
definição e `/research` dizem isso: uma dimensão de arquivo ou repositório roda aqui, uma dimensão
que precisa da web ao vivo vai para um worker de banda dentro da sessão, que fica sujeito aos
próprios prompts de permissão e orçamento de busca da sessão. A recusa que roteia um spawn nativo
de `gatherer` para `citizen role run` diz a mesma coisa em uma frase.

Ambos os adaptadores aplicam uma superfície de execução mais estreita que o cliente interativo
comum. Restrições nativas de configuração têm precedência; flags não suportadas ou configurações
obrigatórias falham a execução. Esses limites não prometem confidencialidade contra o provedor de
modelo nativo. Veja a
[referência de configuração do Codex](https://learn.chatgpt.com/docs/config-file/config-reference)
e a [referência da CLI do Claude](https://code.claude.com/docs/en/cli-reference) para os controles
nativos.

Workers de planner retornam apenas Markdown. O harness roda o validador de Review Card
compartilhado e publica apenas um **novo nome de arquivo** selecionado por quem chama sob
`.agent-harness/plans/`. Descritores de diretório rejeitam armazenamento com symlink; travessia e
destinos existentes são recusados. A publicação atômica também recusa um arquivo criado enquanto o
worker estava rodando. Saída falha, interrompida, vazia ou inválida nunca publica um plano. Quem
chama mantém a decisão de revisão/build.

Delegação desligada bloqueia o executor antes do lançamento. Papéis de escrita em workspace
continuam usando seu workflow existente; este comando não lhes concede um novo caminho de
execução. Receitas de framework de planejamento e revisão usam este mesmo executor de papel, não
um segundo framework ou catálogo de papel de runtime.

## Qualificação

Testes de fonte e um resultado de worker bem-sucedido não são qualificação de cliente. A aceitação
nativa precisa provar que uma leitura permitida de fato roda, que escritas de shell e patch
proibidas não rodam, e que ferramentas externas e reddelegação não conseguem ampliar o acesso. Um
sandbox que impede todo comando de iniciar é um teste bloqueado. Mantenha os resultados atrelados
às versões exatas de CLI, plataforma e fonte do harness no
[catálogo de compatibilidade](compatibility.md); comportamento de editor e desktop exige suas
próprias verificações.
