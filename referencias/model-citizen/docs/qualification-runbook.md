# Runbook de qualificação nativa

Como um operador roda `scripts/native_acceptance.py` contra um cliente real. O que precisa ser
provado, e o que o registro de evidência precisa conter, está em [o que é suportado](compatibility.md);
esta página é apenas a mecânica de uma execução.

## Antes de uma execução

- O checkout precisa estar limpo. Evidência nativa nomeia um commit de origem, e o executor recusa
  uma árvore suja em vez de registrar um commit que não descreve o que rodou.
- O cliente precisa estar instalado e logado para a conta que você pretende qualificar, e
  `<client> --version` precisa relatar uma versão que o executor consegue interpretar.
  [Hosts alvo](#target-hosts) diz de onde vem o cliente de cada alvo e como ele faz login.
- Rode `python3 scripts/smoke_tier.py --targets <ids>` primeiro, nomeando os alvos que a rodada vai
  rodar; sem `--targets` ele verifica todo alvo de CLI que este host consegue rodar e relata os
  outros como pulados. Ele não gasta nenhum turno de modelo, e os defeitos determinísticos que
  captura — um cliente fora do `PATH`, um login do Codex ou daemon do Docker ausente, uma
  credencial inalcançável, uma projeção desviada, um executor que interpreta mal uma transcrição —
  são os que de outra forma apareceriam no meio de uma rodada paga. É consultivo e nunca
  qualificação; veja [releasing](releasing.md#freeze-the-qualification-branch).
- Toda sondagem é um turno headless curto e custa dinheiro. Use o modelo mais barato que o cliente
  oferece; `--model` tem esse como padrão.

## Hosts alvo

Qual binário, login e host cada alvo obrigatório usa é o contrato em
[o que é suportado](compatibility.md#where-each-target-runs-and-what-it-needs). Estes são os
comandos que o estabelecem no Mac em que toda rodada rodou, em ordem, antes de qualquer coisa ser
paga.

1. **Codex no `PATH`.** Ligue o binário empacotado do aplicativo desktop do ChatGPT e leia sua
   versão, que o aplicativo avança sozinho:

   ```sh
   ln -sf /Applications/ChatGPT.app/Contents/Resources/codex ~/.local/bin/codex
   codex --version
   ```

2. **Login do Codex.** `codex login` com a conta ChatGPT sob a qual a rodada roda escreve
   `~/.codex/auth.json`. Uma rodada do Codex gasta o uso desse plano ChatGPT em vez de crédito de
   API, então confirme que o plano tem margem para a rodada, ou orce uma compra de uso, antes de
   começar em vez de encontrar o limite no meio de um caso.
3. **Credencial do Claude Code.** Exporte uma chave de API Anthropic, um perfil de nuvem, ou um
   token de assinatura de `claude setup-token`; o executor passa cada um pelo nome — veja
   [credenciais](#credentials).
4. **Daemon do Docker**, para qualquer um dos dois alvos Linux. Inicie o Docker Desktop e confirme
   que `docker info` responde, depois construa a imagem alvo uma vez por versão fixada de cliente:

   ```sh
   docker build -f scripts/linux-target.Dockerfile -t agent-harness-linux-target .
   ```

   Ela constrói nativamente como linux/arm64 em silício Apple, que é o que os registros Linux da
   0.11.x descrevem. Mude `CODEX_VERSION` e `CLAUDE_CODE_VERSION` com `--build-arg` quando uma
   rodada fixa clientes mais novos.
5. **Verifique antes de pagar.** A verificação `credentials` da camada de smoke lê os alvos que
   você nomeia e falha na hora, nomeando o alvo, quando um cliente está fora do `PATH`, o login do
   Codex está ausente ou o daemon do Docker não responde:

   ```sh
   python3 scripts/smoke_tier.py --only credentials \
       --targets claude-code-cli-macos,codex-cli-macos,claude-code-cli-linux,codex-cli-linux
   ```

   Um alvo Linux verifica só o daemon a partir do Mac; seu cliente e login são verificados pelo
   mesmo comando dentro do container.

Um alvo Linux nunca é rodado a partir do Mac. O executor recusa um alvo cuja plataforma não é a do
host, porque o registro carregaria o nome de uma plataforma sobre o resultado de outra, e
`scripts/qualification_round.py` relata tal alvo como não rodado aqui e o deixa fora da rodada em
vez de falhá-lo (#708). Em vez disso ele roda dentro do container, contra o clone congelado da
rodada montado somente-leitura e seu diretório de registros montado com escrita, ambos vindos do
[provisionamento](#provisioning-the-round). Em uma assinatura Claude, passe o token de
`claude setup-token` como `CLAUDE_CODE_OAUTH_TOKEN` (#672); esta é a sequência que produziu os
registros `claude-code-cli-linux` da 0.13.0:

```sh
docker run --rm -it -e CLAUDE_CODE_OAUTH_TOKEN \
    -v "$PWD/../round-v<version>/clone:/frozen:ro" \
    -v "$PWD/../round-v<version>/records:/records" \
    agent-harness-linux-target
# dentro do container
git -c safe.directory='*' clone -q /frozen harness && cd harness
python3 scripts/smoke_tier.py --only credentials --targets claude-code-cli-linux
python3 scripts/native_acceptance.py --client claude-code-cli-linux --model sonnet \
    --out /records/claude-code-cli-linux.json
```

`sonnet` é o modelo roteado da classe `standard` em `adapters/claude-code/bindings.json`; o
executor iniciado manualmente não tem nenhuma rodada para roteá-lo, então ele é nomeado, e o
registro lê `model_source: routing` porque combina. As formas de chave de API e perfil de nuvem, e
um alvo Codex:

```sh
docker run --rm -it -e ANTHROPIC_API_KEY \
    -v "$PWD/../round-v<version>/clone:/frozen:ro" \
    -v "$PWD/../round-v<version>/records:/records" \
    agent-harness-linux-target
# ou, para o Claude Code em um perfil de nuvem em vez de uma chave de API
docker run --rm -it \
    -e CLAUDE_CODE_USE_BEDROCK -e AWS_PROFILE -e AWS_REGION \
    -e AWS_CONFIG_FILE=/aws/config -e AWS_SHARED_CREDENTIALS_FILE=/aws/credentials \
    -v "$HOME/.aws:/aws:ro" \
    -v "$PWD/../round-v<version>/clone:/frozen:ro" \
    -v "$PWD/../round-v<version>/records:/records" \
    agent-harness-linux-target
# dentro do container
git -c safe.directory='*' clone -q /frozen harness && cd harness
codex login --device-auth
python3 scripts/smoke_tier.py --only credentials --targets codex-cli-linux,claude-code-cli-linux
python3 scripts/native_acceptance.py --client codex-cli-linux --model <cheapest> \
    --out /records/codex-cli-linux.json
```

O clone com escrita existe porque o executor recusa uma árvore que não consegue provar limpa, e a
sobrescrita `safe.directory` é necessária porque o mount pertence a outro usuário. `-e` nomeia cada
variável de credencial sem seu valor. A forma de perfil monta o diretório AWS somente-leitura em
um caminho que não é o home do usuário do container e aponta as variáveis de arquivo para lá,
porque o executor entrega ao seu diretório home descartável só esses ponteiros.
`codex login --device-auth` dá ao container sua própria sessão ChatGPT, então nenhum arquivo de
login do host é copiado para dentro dele; se as rodadas Linux da 0.11.x fizeram login dessa forma
ou usaram uma cópia do login do host não está registrado.

**O `CODEX_HOME` descartável do executor não carrega o login de sessão.** `adapters/codex/worker.py`
linka `auth.json` em um diretório home de worker isolado; o executor de aceitação não copia
nenhuma credencial e passa apenas as variáveis em [credenciais](#credentials), então um caso Codex
conduzido pelo executor não tem login, e todo registro Codex até hoje foi produzido manualmente em
vez de por este executor. Até que o executor linke o login da mesma forma que o worker faz, a
verificação de pré-condição acima prova que o login existe, não que o executor consegue usá-lo.

## Provisionando a rodada

Uma rodada precisa de um clone congelado do commit que qualifica e de algum lugar para guardar o
registro de cada alvo. Provisione os dois uma vez, fora do checkout:

```sh
python3 scripts/qualification_provision.py --out ../round-v<version>
```

O clone é tirado do próprio armazenamento de objetos deste repositório e é recusado a menos que a
árvore esteja limpa e o clone aterrisse no commit nomeado. Nenhum caso obrigatório roda um workflow
de framework, então nenhum caso precisa de mais nada. Em um lançamento minor, `--bmad` também
instala um checkout do framework BMad com o instalador fixado de [bmad](bmad.md) para a suíte de
integração opcional em [releasing](releasing.md#source-and-qualification), que é rodada
manualmente; é o único passo que alcança a rede, e `--print-env` imprime a exportação que o
operador dessa suíte precisa.

## Executando

```sh
python3 scripts/native_acceptance.py --client claude-code-cli-macos --dry-plan
python3 scripts/native_acceptance.py --client claude-code-cli-macos --cases cost-posture \
    --model haiku --out ../native-cost-posture.json
python3 scripts/qualification_round.py --round ../round-v<version> --plan
python3 scripts/qualification_round.py --round ../round-v<version> \
    --targets claude-code-cli-macos,claude-code-cli-linux
```

Uma rodada sem nenhum `--model` passa para cada alvo o modelo para o qual sua classe de execução
roteia, e cada registro de evidência e linha por caso o carrega como `model_run`, com o roteamento
do registro lendo `model_source: routing`; um `--model` de operador ainda vence, registrado como
`model_source: operator` ao lado do modelo roteado (#721). Em um Mac, o alvo Linux nesse exemplo é
relatado como não rodado aqui, e roda no container a partir de [hosts alvo](#target-hosts).

`--dry-plan` não lança nenhum cliente e nomeia, por caso, o que uma execução faria.
`--keep-home` deixa cada diretório home descartável no lugar para depuração; sem isso, todo
diretório home é removido ao final do seu caso. Escreva `--out` fora do checkout: o executor recusa
rodar contra uma árvore suja, e um arquivo de evidência é adicionado à árvore deliberadamente,
depois de revisão.

`scripts/qualification_round.py` conduz uma rodada provisionada: a camada de smoke uma vez, depois
o executor por alvo a partir do clone congelado, um registro cada. Uma camada de smoke que falha
ou expira para a rodada antes de qualquer alvo rodar, e `round.json` registra o resultado da
camada, por que a rodada parou e os alvos que não rodou; `--skip-smoke` registra a camada como
`skipped` e roda todo alvo. Passada a camada, ela não decide nada e não para por nada — uma rodada
coleta os defeitos de todo alvo antes de qualquer um deles ser corrigido, que é a regra em
[releasing](releasing.md#freeze-the-qualification-branch) — e ela sai com código não-zero a menos
que a camada tenha passado ou sido pulada e todo caso de todo alvo tenha passado. O registro
anterior de um alvo é movido para o lado antes de seu executor ser lançado, então um executor que
sai antes de escrever um relata todo caso como `unverified` em vez das aprovações da rodada
anterior, e um alvo que roda além do prazo da rodada é registrado e carregado adiante em vez de
levantado — os alvos depois dele ainda rodam.

## Qual classe executa, e qual classe lê

Uma rodada carrega duas classes de capacidade por alvo, não uma. A **classe de execução**,
`standard` por padrão, é o worker que roda os casos com script, lê seu JSON e escreve o arquivo de
achados. A **classe de avaliação**, `strong` por padrão e um piso em vez de uma preferência, é o
leitor que avalia as observações da rodada, o que [o que é suportado](compatibility.md) exige de um
revisor. As duas são escritas no registro de evidência como `tier_routing` e no `round.json` da
rodada, então o registro diz qual classe produziu uma observação e qual classe a leu.

```sh
python3 scripts/qualification_round.py --round ../round-v<version> \
    --execution-class light --execution-class codex-cli-macos=standard
```

Uma classe simples move todo alvo; `TARGET=CLASS` move o que nomeia, então um alvo Codex pode ser
executado em uma classe diferente de um Claude Code na mesma rodada. Argumentos posteriores
vencem.

As classes são resolvidas através do `adapters/<runtime>/bindings.json` do runtime alvo, a mesma
tabela que `citizen tiers` verifica; uma sobrescrita pessoal de `tiers.<runtime>` em uma
configuração de usuário não é aplicada, porque uma rodada roda a partir de um clone congelado.
Duas recusas, ambas antes de qualquer cliente ser lançado:

- Uma classe de avaliação mais fraca que `strong`. Uma classe mais barata pode executar os casos;
  ela não os avalia.
- Uma classe de execução barata que resolve para o próprio modelo da classe de avaliação — porque
  o adaptador mapeia as duas classes para um identificador, porque soletra um modelo de duas
  formas, ou porque não mapeia a classe barata de forma alguma e uma classe não mapeada resolve
  para cima. O executor então seria o único leitor da evidência que produziu. Os dois
  identificadores são comparados da mesma forma que o ledger de uso os compara, então um id com
  data e um alias simples do mesmo modelo são um modelo; a comparação erra pelo lado de recusar, e
  dois modelos que um operador quis dizer serem diferentes são escritos como dois ids nenhum dos
  quais é prefixo do outro.
- Uma classe de avaliação que o adaptador não mapeia enquanto a classe de execução está mapeada: o
  leitor herdaria seja qual for o modelo que a sessão por acaso está rodando, que não é nenhum
  leitor nomeado.

Uma classe de *execução* não mapeada ao lado de um avaliador mapeado — o que pedir uma classe mais
forte que a do avaliador faz — é divulgada em vez de suposta: esse worker herda o modelo da sessão
e o registro carrega a nota dizendo isso.

O roteamento é escrito no log durável por caso antes de o primeiro caso rodar e no `round.json`
antes da camada de smoke, então uma rodada morta ainda registra quais classes estavam rodando.
`--from-progress` recusa um log cujos casos foram executados sob um roteamento diferente em vez de
mesclá-los: um registro construído a partir de dois roteamentos não consegue dizer qual classe
produziu uma observação.

Uma rodada iniciada de novo com os mesmos argumentos no mesmo commit retoma a partir desse log: um
caso cuja última linha é `passed` ou `failed` não roda de novo, e o executor diz isso no stderr
para cada um. Uma falha é mantida para que sua evidência continue intacta; um caso `unverified`,
que não observou nada, e um caso que a interrupção cortou, ambos rodam de novo. O cabeçalho do log
carrega o commit de origem, versão do cliente e roteamento, então um veredito nunca pula um caso
para um candidato diferente. Uma retomada sem `--home-confirmed` em uma superfície que precisa
disso não mantém nenhum veredito, já que só conseguiria ler `unverified` de qualquer forma, então
todo caso roda de novo. Para tentar de novo um caso falho no mesmo commit, dê à rodada um log
`--progress` novo.

A economia que isso compra é a estimativa da issue, não uma medição: workers rodaram 0,7×–1,8× de
seu orçamento de 82K de saída, então quatro alvos custam 230K–590K tokens de saída por rodada, a
maior parte deles de autoria em vez de julgamento (#338). Não vale nada sem os casos com script
(#336): descartar a classe em um worker que ainda está conduzindo os casos manualmente compra
observações piores e mais tentativas.

## Superfícies de cliente

Cada superfície nomeia a variável de ambiente que move todo seu diretório de configuração, que é o
que torna possível um diretório home descartável: `CLAUDE_CONFIG_DIR` para o Claude Code,
`CODEX_HOME` para o Codex. A superfície do Codex é conduzida em modo headless com
`codex exec --json` e lida a partir dos arquivos de rollout sob seu diretório home, seguindo
`adapters/codex/worker.py` e [usage](usage.md#codex-rollouts).

**Nenhuma rodada Codex foi conduzida através deste executor.** Até que uma seja, sua leitura é
derivada desses arquivos em vez de observada, então todo veredito Codex é relatado `unverified`
com a observação mantida, exatamente como um caso não observado é. Na primeira rodada que roda um
alvo Codex, qualifique-o também manualmente, compare os dois, e passe `--home-confirmed` só quando
concordarem. Registre essa comparação com as observações da rodada.

## Credenciais

O executor não copia nenhuma credencial e não imprime nenhuma. Cada caso roda em um `HOME`
descartável que herda, **só pelo nome**, as variáveis de autenticação que esta máquina já usa — as
variáveis `ANTHROPIC_*`, `CLAUDE_CODE_OAUTH_TOKEN`, os switches de Bedrock e Vertex, `AWS_PROFILE`
e a região AWS, variáveis de arquivo de credenciais e sessão (`AWS_ACCESS_KEY_ID`,
`AWS_SESSION_TOKEN` e a variável de chave secreta ao lado delas), `GOOGLE_APPLICATION_CREDENTIALS`
e `OPENAI_API_KEY`. `AUTH_PASSTHROUGH` no executor é a lista completa. Um container que guarda suas
credenciais como variáveis de ambiente e não tem nenhum perfil para recorrer é qualificado
exportando-as para o wrapper que invoca o executor; nada mais alcança o cliente.

Um `claude login` interativo nunca alcança o diretório home descartável. Em uma assinatura Claude
sem chave de API, rode `claude setup-token` uma vez — ele emite um token de longa duração para
essa assinatura — e o exporte como `CLAUDE_CODE_OAUTH_TOKEN` no shell que invoca o executor, para
que a rodada gaste da assinatura em vez de crédito sob demanda. Exporte-o só para a rodada; nunca o
escreva em um arquivo.

Os ponteiros de arquivo AWS são reancorados no home real do operador, porque o `HOME` da sondagem é
descartável e um ponteiro não definido trava a busca do provedor. No macOS, cada diretório home
descartável ganha seu próprio chaveiro padrão primeiro, então um cliente que armazena um item não
levanta nenhuma caixa de diálogo do sistema.

## Lendo o resultado

Um caso é `passed` somente quando o executor observou o comportamento ele mesmo. Uma afirmação que
não se sustentou é `failed`; qualquer coisa que o executor não conseguiu observar — nenhuma
transcrição, um turno que não terminou, um modelo que recusou o turno por julgamento próprio — é
`unverified` com seu motivo, nunca uma aprovação. Toda observação é redigida quanto a caminhos de
home, nomes de host e formatos de credencial antes de ser escrita. O status de saída é 0 somente
quando todo caso selecionado passou.
