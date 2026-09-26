# Servidores de Remote Control

Esta página descreve uma funcionalidade de adaptador do Claude Code para macOS. O Codex não tem
equivalente.

O `/remote-control` do Claude Code compartilha uma sessão em execução com o aplicativo móvel e o
claude.ai/code. Iniciar uma *nova* sessão pelo celular precisa do `claude remote-control` rodando
como um servidor na pasta, e um servidor serve uma pasta. `citizen remote-control` mantém um
servidor por pasta configurada vivo sob o launchd, então as pastas ficam alcançáveis depois de uma
reinicialização sem nenhum terminal aberto.

Sirva cada raiz de workspace a partir de sua própria entrada. Um host roda com sua pasta como
diretório de trabalho, então toda sessão que ele inicia carrega o `CLAUDE.md`, as skills e os
hooks daquela pasta; um host para um diretório pai de vários repositórios não carrega nenhum
deles.

## Configurar

Adicione as pastas à configuração de usuário, depois instale:

```json
"remote_control": {
  "folders": [
    "~/repos/project-one",
    {"path": "~/repos/notes", "spawn": "same-dir", "env": {"EXAMPLE_FLAG": "1"}}
  ],
  "spawn": "worktree",
  "permission_mode": "default",
  "keep_awake": false
}
```

```sh
citizen remote-control install [--dry-run]   # um agente launchd por pasta; retira agentes de pastas removidas
citizen remote-control status                # estado do launchd e caminho de log por pasta
citizen remote-control uninstall             # descarrega e remove todo agente
```

- As entradas de **`folders`** são um caminho, ou um objeto com um `path` e, opcionalmente, seu
  próprio `spawn`, que sobrescreve o do bloco, e `env`, nomes de string para valores de string
  adicionados ao ambiente launchd daquele host. O rótulo launchd é derivado só do caminho, então
  trocar uma entrada entre as duas formas mantém seu agente.
- **`spawn`** é passado para `--spawn`. `worktree` dá a cada sessão iniciada pelo celular sua
  própria worktree git, então duas sessões nunca compartilham um checkout; `same-dir` e `session`
  são os outros modos do Claude Code. Uma pasta que não é um repositório git precisa de
  `same-dir`.
- **`permission_mode`** é passado para `--permission-mode` e se aplica a toda sessão que o
  servidor inicia. O servidor é alcançável a partir de qualquer dispositivo logado na sua conta,
  então escolha-o como escolheria para uma sessão sem supervisão.
- **`keep_awake`** envolve o servidor com `caffeinate -is`. Isso segura o sono ocioso, e o sono do
  sistema com energia AC. Nada mantém um laptop acordado com a tampa fechada.

Rode `install` de novo depois de mudar o bloco. Um agente cuja definição não mudou é deixado em
execução, porque recarregá-lo cortaria as sessões que seu servidor está carregando.

O host roda sem `--no-create-session-in-dir`. O Claude Code 2.1.280 lê o ponteiro de ponte da
pasta, e assim reaproveita o ambiente em um relançamento, apenas enquanto `createSessionInDir`
está ligado; com a flag, toda reinicialização registrava um ambiente novo. O custo é a única
sessão que cada host pré-cria em sua pasta, que é reaproveitada entre reinicializações enquanto o
ponteiro está fresco.

Um host que reaproveitou um ambiente ao iniciar mantém suas sessões e seu ambiente quando é parado
com `SIGTERM`. Um que não reaproveitou — o primeiro host depois de uma atualização, ou depois que
um ponteiro expirou — arquiva toda sessão e desregistra seu ambiente ao `SIGTERM`. Então um agente
alterado cujo host está em execução é *adotado* em vez de substituído: `install` lê o ambiente do
log do host, escreve o ponteiro da pasta para ele sem nenhum pid, envia `SIGKILL` ao processo
`claude`, que pula o caminho de encerramento, e depois recarrega o agente, cujo novo host
reaproveita o ambiente. `--dry-run` nomeia o ambiente que adotaria.

Reinicie um host somente com `citizen remote-control install`, nunca com `launchctl kickstart -k`:
isso envia `SIGTERM`, e um host que não reaproveitou seu ambiente arquiva suas sessões nisso.

## Mantendo sessões através de uma reinicialização: `heal`

Um servidor que perde a rede por dez minutos desiste, arquiva toda sessão que estava carregando e
desregistra seu ambiente; o launchd então o inicia de novo como um ambiente *novo* que não adota
nada, e os chats abertos no seu celular se vão. O Claude Code consegue readotar o ambiente antigo
— ele pede ao servidor para reaproveitar o id no
`~/.claude/projects/<slug>/bridge-pointer.json` da pasta — mas apenas enquanto esse arquivo é mais
novo que seu TTL de quatro horas e nomeia um pid que não está mais rodando, e um servidor que
iniciou sem um ponteiro nunca escreve um. `citizen remote-control heal` fecha essa lacuna: uma vez
por minuto ele lê o id de ambiente ao vivo de cada agente em execução a partir do seu log e
reescreve o ponteiro da pasta com ele, então um relançamento pede o ambiente em que as sessões de
fato estão. `--dry-run` relata sem escrever, `--once` é a passagem única que o agente
`com.agent-harness.remote-control-heal` roda, e `--preserve-worktrees` faz um commit WIP em toda
worktree `bridge-cse_*` suja primeiro, para que nada não enviado (push) possa ser apagado por uma
limpeza. Ações são anexadas a
`~/.local/state/agent-harness/remote-control/heal.log`, e `status` relata a última.
Heal não resgata um ambiente que o caminho de desistência já desregistrou: o reaproveitamento é
recusado assim que o ambiente se foi, e o mesmo vale para o endpoint de reconexão de ponte.

## Parando um host antes de ele desistir

A desistência de dez minutos é fixa no código do Claude Code e seu caminho é destrutivo, então a
correção é nunca chegar lá. Cada passagem lê o log do host em busca da sequência final de linhas
`Connection error, retrying in 2m (541s elapsed)` — o host imprime sua própria idade de orçamento
de erro, então é lida em vez de cronometrada — e aos nove minutos envia um único `SIGTERM` ao
processo `claude` do host, o filho quando `keep_awake` o envolve em `caffeinate`. O `KeepAlive` do
launchd o inicia de novo dentro do intervalo de estrangulamento, e ele se registra pedindo para
reaproveitar o ambiente no ponteiro que o heal acabou de atualizar. A parada dispara uma vez por
processo de host: o host relançado tem um novo pid e ganha a sua própria. Uma linha
`Detected system sleep (Ns gap), resetting error budget`, e uma linha `Reconnected after Ns`, ambas
encerram a execução, porque o host reinicia seu orçamento ali também.

Se o host desistiu antes de o supervisor chegar até ele, seu log nomeia as worktrees de sessão que
a limpeza apagou. Heal recria cada uma no seu caminho, anexando a branch quando ela sobreviveu e
ramificando da branch padrão quando não sobreviveu, então uma sessão retomada por um contrato
posterior tem seu diretório. Uma worktree que o host `kept … · uncommitted changes` é deixada
intacta, e toda linha é agida sobre uma vez.

## Reconectando sessões: `heal`

Depois de sua passagem por pasta, heal lê as sessões da conta uma vez e, para cada uma ainda
`active` com uma ponte `disconnected` em um ambiente que este Mac guarda — qualquer ambiente que
um log de host nomeie, mais o do ponteiro de cada pasta configurada — chama
`POST /v1/environments/<env>/bridge/reconnect`, que devolve a sessão à fila do seu ambiente para o
host retomar. Cada tentativa é uma linha `reconnect <session> on <env>: <status>` no log de heal,
uma sessão é tentada no máximo uma vez a cada dez minutos, `--dry-run` não envia nada, e um token
ausente ou uma chamada falha nunca interrompem a passagem. Uma sessão arquivada não é tocada:
desarquivar exige mais do que o token de login, então continua sendo um passo manual.

## Sessões que se perderam mesmo assim: `status`

`citizen remote-control status` pergunta à conta quais sessões ainda estão `active` com uma ponte
`disconnected` em um ambiente que este Mac registrou, e imprime o comando de reconexão para cada
uma, para qualquer sessão que o heal não conseguiu reconectar. Ele não as executa. Um host
`claude remote-control --session-id <id>` registra o ambiente perdido uma *segunda* vez, como um
ambiente de sessão única, e o cliente então roteia chats novos para ele — recuperar cinco sessões
dessa forma deixa cinco ambientes soltos competindo por trabalho novo, e na 2.1.278 cada host se
liga à sessão que o anterior foi solicitado, em vez do seu próprio `--session-id`. Então a
recuperação continua sendo um ato deliberado, um de cada vez: rode o comando a partir de um
diretório não usado, deixe a sessão responder, e pare esse host.

A leitura tem um teto de cinquenta sessões e o endpoint não recebe parâmetro de ordenação, então a
página é verificada na chegada: precisa estar da mais nova para a mais antiga por `last_event_at`,
o campo pelo qual o servidor ordena. Uma página que não está assim é lida como
`not checked (page order unknown)` em vez de como uma conta sem nada perdido, e quando a conta
guarda mais sessões que uma página, a contagem diz `in the newest 50`.

O token do claude.ai é lido do chaveiro de login pela duração da chamada e nunca é impresso,
registrado em log ou escrito em nenhum lugar.

`citizen doctor` relata o mesmo terreno por pasta configurada: se o processo de host está vivo,
qual ambiente ele registrou, se o ponteiro nomeia esse ambiente e esse pid, há quanto tempo está
inalcançável, e quantas de suas sessões estão desconectadas.

## Arquivos que um agente te envia

No Claude Code 2.1.280, uma sessão que um host inicia não tem rota de upload própria, então um
arquivo que o agente envia com `SendUserFile` chega ao aplicativo como "not delivered: this session
is not on a project thread", e o aplicativo iOS mostra seu cartão acinzentado. Todo host que o
harness instala, portanto, define `CLAUDE_CODE_BRIEF_UPLOAD=1`, que suas sessões herdam: com isso
definido, o arquivo é enviado com a conta em que o host está logado, e o cartão abre. A variável
não é documentada, então uma atualização do cliente pode descartá-la. Defina-a como `""` no `env`
de uma pasta para desligar uploads para esse host. Um host só assimila a mudança quando `install`
reescreve seu agente da próxima vez.

Um arquivo que não é enviado é um que o aplicativo ainda pode pedir à sessão, e o Claude Code o
serve apenas de dentro do diretório em que a sessão começou, que é a worktree da sessão sob
`spawn: worktree`, ou um diretório adicionado à sessão. A maioria dos outros caminhos falha no
aplicativo com "Couldn't load this file". Relatórios, renderizações e capturas de tela são
rotineiramente escritos em outro lugar: um diretório temporário ou de rascunho, a worktree de uma
tarefa, ou o checkout principal visto a partir da worktree de uma sessão.

A política `stage-user-files` fecha essa lacuna em toda sessão de Remote Control em que os hooks
do harness rodam, seja um host aqui que a tenha iniciado ou não. Antes de `SendUserFile` rodar,
todo arquivo de fora do diretório de trabalho atual da sessão é copiado para
`.agent-harness/outbox/<digest>/<name>` ali, e a chamada envia a cópia em vez disso; um aviso
`stage-user-files: copied …` diz quando isso aconteceu. A outbox se ignora no git, então em um
repositório uma cópia nunca chega ao `git status`, a um commit ou ao lint, e uma cópia intocada
por duas semanas é removida na próxima vez que um arquivo é copiado. Uma chamada copia no máximo
64 MiB em cerca de quatro segundos; um arquivo além de qualquer um dos limites, ou um que não pode
ser copiado, é enviado de onde está, com um aviso.

O aplicativo ainda lê o arquivo da sessão quando você o abre, então um arquivo enviado de uma
sessão cuja worktree foi removida desde então não pode ser aberto depois.

## O que ele não vai fazer

- **Aceitar a confiança de workspace por você.** O servidor recusa uma pasta cuja caixa de diálogo
  de confiança nunca foi aceita, e o launchd reiniciaria essa recusa para sempre, então `install`
  recusa a pasta e sai com código não-zero com a correção. A confiança é por diretório exato: um
  repositório confiável não confia em suas worktrees, e a falha é um host que sai com
  `Error: Workspace not trusted. Please run \`claude\` in <path> first …` a cada minuto. Rode
  `claude` na pasta uma vez e aceite a caixa de diálogo. `citizen trust` é um portão diferente —
  ele permite que o hook stop-gate rode o gate de um repositório — e `install` o nomeia ao lado,
  porque uma pasta servida sem supervisão geralmente quer os dois.
- **Assumir uma pasta já servida a partir de um terminal.** O Claude Code permite um servidor por
  pasta por dispositivo. Pare o servidor de terminal; o agente tenta de novo a cada minuto.
- **Fazer login.** O servidor usa o login claude.ai da conta que rodou `install`. Uma chave de API
  ou uma credencial de provedor de nuvem não suporta o Remote Control.

Cada agente registra logs em `~/.local/state/agent-harness/remote-control/`. Leia o log primeiro
quando `status` mostrar um agente que está carregado mas inalcançável a partir do celular.
