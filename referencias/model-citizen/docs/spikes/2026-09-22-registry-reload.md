# Spike: uma sessão em execução pode aprender que consegue resolver os workers de banda?

> **Resultado: manter o portão conservador, e atualizá-lo a partir de um sinal que existe.** O
> Claude Code recarrega seu registro de agentes no meio de uma sessão interativa e nunca em uma
> headless, e registra ambos os casos na transcrição como um anexo `agent_listing_delta`. Esse
> registro é uma afirmação positiva, por sessão, do que esta sessão consegue resolver agora, então
> o hook de spawn pode levantar seu portão sem adivinhar em que tipo de sessão está.

## Pergunta

Um hook de spawn redireciona um subagente sem nome para um worker de banda somente quando o
registro de início de sessão nomeia esse worker, porque um `subagent_type` que a sessão em
execução não consegue resolver faz o spawn falhar de imediato. Existe um sinal que um hook consiga
ler que diga que uma sessão iniciada antes de `harness sync` instalar os workers agora consegue
resolvê-los — ou nenhum existe, deixando o portão permanente?

## Clientes

Claude Code 2.1.278 para as sondagens headless; o cliente se autoatualizou para 2.1.280 durante as
interativas, no macOS. O Codex CLI 0.155.0-alpha.9.2 não foi exercitado, pelo motivo em "Não
executado". Oito sessões ao todo.

## Experimento

Cada sondagem iniciou uma sessão, criou uma definição de agente **depois** de ela estar em
execução, esperou, e pediu à sessão para fazer spawn desse tipo. O corpo da definição retornava um
token que não aparecia em nenhum lugar do prompt, então uma resposta prova que um subagente rodou,
em vez de o modelo principal parafraseando um arquivo.

| Sondagem | Sessão | Onde a definição foi criada | Resultado |
| --- | --- | --- | --- |
| A | `claude -p` | `.claude/agents/` do projeto, diretório criado no mesmo turno | `Agent type … not found` |
| B | `claude -p` | `.claude/agents/` do projeto, diretório existia no início, espera de 15 s | `Agent type … not found` |
| D | `claude -p --input-format stream-json`, dois turnos em um processo | `.claude/agents/` do projeto, criado no turno 1, spawn no turno 2 | `Agent type … not found` |
| E/F | interativa (via pty) | `.claude/agents/` do projeto, diretório existia no início, espera de 30 s | spawn ocorreu, token retornado |
| G | interativa | `~/.claude/agents/`, adicionado como **symlink**, que é a forma que `harness sync` escreve | spawn ocorreu, token retornado |
| I/J | interativa | `~/.claude/agents/`, arquivo simples | spawn ocorreu, token retornado |

As sondagens H e I também instalaram um hook `SessionStart` e um `FileChanged` via `--settings`,
para ver o que um hook recebe.

## Medido

- **O registro de fato recarrega, mas só em uma sessão interativa.** Toda sondagem headless falhou
  com o mesmo erro, que enumera o registro como carregado no início do processo. A falha da
  sondagem A é a exceção documentada: o observador só cobre diretórios `agents` que já existiam
  quando a sessão começou.
- **A transcrição registra isso.** Toda sessão escreve um registro `attachment` do tipo
  `agent_listing_delta` com `isInitial: true` e uma lista `addedTypes` contendo o registro no
  início. A sondagem interativa escreveu um **segundo** registro — `isInitial: false`,
  `addedTypes: ["probe-iota"]`, `removedTypes: []` — depois que a definição apareceu, anexado ao
  turno do usuário antes da chamada `Agent` do assistente. Nenhuma sessão headless escreveu um
  segundo registro. O sinal e a capacidade se alinham exatamente, então um leitor não precisa
  adivinhar entre interativo e headless.
- **`FileChanged` dispara nos dois tipos de sessão.** Um hook `SessionStart` retornando
  `watchPaths` para um caminho de worker, mais um hook `FileChanged`, recebeu
  `{"event": "add", "file_path": …}` tanto na sondagem headless quanto na interativa. Ele relata
  que um arquivo apareceu, não que um registro recarregou, então não é seguro por si só: agir
  sobre ele em uma sessão headless transformaria um spawn que funciona em um que falha.
- **`SessionStart` carrega `model` interativamente e o omite no modo headless** nessas execuções.
  A referência de hooks diz que o campo nem sempre é incluído, então é uma correlação, não um
  portão.
- **A documentação do fornecedor concorda com as medições interativas** e afirma os três casos que
  ainda exigem reinício: um diretório `agents` criado depois de a sessão começar, um diretório
  adicionado com `--add-dir`, e uma sessão iniciada com `--disable-slash-commands`. Ela não
  menciona sessões headless; a medição acima é a evidência para esses casos.

## Veredito — manter, com uma atualização, que entrou junto com este registro

O portão conservador permanece como o piso, e o registro de sessão ganhou uma segunda fonte na
mesma mudança: `posture.transcript_agents` lê os anexos `agent_listing_delta` na própria
transcrição da sessão, sobre uma cauda limitada, e `routable()` no hook de spawn roteia para um
worker que o registro antecede quando um delta posterior o nomeia. Só contam os próprios registros
de anexo desta sessão, `addedTypes` e `removedTypes` são aplicados na ordem em que foram escritos,
uma listagem `isInitial` substitui tudo antes dela, e o que a cauda encontrou é mantido no registro
de sessão para que o roteamento sobreviva ao delta saindo de uma leitura limitada. Rodado contra as
transcrições que essas sondagens deixaram, o leitor responde `["probe-iota"]` para a sessão
interativa que recarregou e `None` para a headless que não conseguiu.

O invariante se mantém: o conjunto é a própria afirmação do runtime sobre si mesmo, então só pode
nomear um tipo que a sessão carregou. Uma sessão que nunca recarrega produz apenas o registro
inicial, que é o que o registro de início de sessão já continha. Um delta que chega no meio de um
turno só é anexado no próximo turno do usuário, então o roteamento retoma um turno mais tarde do
que poderia — conservador na direção segura.

## O que o código faz com isso, e o que ainda não faz

- Uma transcrição ausente, uma cauda ilegível e uma listagem que caiu fora da cauda são todas lidas
  como desconhecidas, o que não roteia nada: o registro de sessão decide esses casos, exatamente
  como antes.
- O aviso "inicie uma nova sessão para rotear spawns sem nome" ainda é o que uma sessão que não
  recarregou escuta.
- O hook de precificação pergunta à mesma função com a mesma transcrição, então um spawn nunca é
  precificado por uma banda e roteado para outra.
- Nada é construído sobre `FileChanged` ou sobre o campo `model` de `SessionStart`; ambos foram
  medidos e ambos são mais fracos que o delta.
- Deixado em aberto: o delta é anexado no próximo turno do usuário, então uma sessão que recarrega
  no meio de um turno retoma o roteamento um turno mais tarde do que poderia. Conservador na
  direção segura, e nenhum código consegue encurtar isso.

## Não executado

- **Codex.** O portão existe apenas nos hooks do Claude Code, e o Codex não tem hook de spawn que
  pudesse consumir um sinal de recarga; suas projeções de papel são arquivos sob o próprio
  diretório `agents` do cliente. Se esse cliente os relê no meio da sessão é uma pergunta para a
  execução que dá ao Codex um portão equivalente.
- **Uma definição editada**, em oposição a uma adicionada. O portão trata de tipos que uma sessão
  não consegue resolver de forma alguma, então um corpo alterado ficou fora do escopo.
