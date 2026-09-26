# Modos

Um modo é um pacote de seleção nomeado: um arquivo que define muitas unidades de uma vez, para que
o harness possa ser colocado em uma forma conhecida sem definir cada unidade manualmente. Qualquer
chave que você mesmo digitou continua vencendo. O documento de seleção em que um modo é escrito
está descrito em [preferences.md](preferences.md#the-selection-document).

## Selecionando um modo

```sh
citizen config set mode minimal     # toda sessão, a partir de ~/.config/agent-harness/config.json
citizen sync
HARNESS_MODE=minimal claude          # uma sessão, sem mudar a seleção armazenada
```

Um arquivo de projeto ou sessão também pode nomear um `mode`; a camada mais alta que nomeia um é a
que vale. `citizen selection` imprime `mode=<name> (<layer>)`, relata cada unidade que o modo
definiu com a origem `mode:<name>`, e lista toda chave de modo que uma camada superior sobrescreveu
como `shadowed`. Não ter modo é o mesmo que selecionar `full`.

## Precedência

Do menor para o maior; cada camada sobrescreve as anteriores:

1. `default`: as variantes de postura embutidas, e `on` para todo switch.
2. `init`: uma postura que `citizen init` escreveu como padrão, que você aceitou com Enter.
3. `mode:<name>`: o modo selecionado.
4. `user`: toda outra chave em `config.json`, as que você digitou.
5. `project`, depois 6. `session`: os arquivos que `HARNESS_PROJECT_CONFIG` e
   `HARNESS_SESSION_CONFIG` nomeiam, depois `HARNESS_MODE` e `HARNESS_STANCE_*`.

A camada `init` é como um modo passa a valer depois de um `citizen init` padrão. `config.json`
registra as posturas que o init escolheu para você, com o valor que escreveu, sob
`init_defaults`. Uma postura conta como do init apenas enquanto ainda mantém esse valor:
`citizen config set stances.NAME`, ou editar o valor em `config.json`, a torna sua, acima de
qualquer modo. Uma configuração escrita antes de modos existirem não tem `init_defaults`, então
toda postura nela conta como digitada: apague uma postura de `stances`, ou de ambas as listas,
para deixar um modo defini-la.

## Modos distribuídos

### `full`

Tudo que o harness distribui, em seus padrões. Não muda nada.

### `minimal`

Aplicação sem cerimônia. Todo hook permanece ligado, e as posturas `cost`, `delegation` e
`autonomy` mantêm seus valores. Ele muda:

- Posturas: `licensing` desligada, `build-vs-buy` desligada, `commits` desligada,
  `plan-ceremony` leve, `testing` desligada, `voice` desligada.
- Workflows: `build` desligado, `close-out` desligado, `handoff` desligado, `land` desligado,
  `plan` desligado, `research` desligado, `review` desligado.

`sync` projeta ambos: cada postura linka sua variante escolhida, e um workflow que está `off` não
tem comando instalado.

## Escrevendo um modo

Um modo é `modes/<name>.json` em `primitives/` ou em uma raiz listada em `primitive_roots`:

```json
{"schema_version": 1,
 "description": "What this mode is for, in one sentence.",
 "stances": {"testing": "pragmatic"},
 "rules": {"decisions-and-plans": "off"}}
```

Além de `schema_version` e `description`, ele só pode carregar tipos de seleção: nenhum `mode`,
`sources`, identidade, permissões ou outra chave possuída pelo usuário. Cada unidade que nomeia
deve estar instalada. Um nome que duas raízes definem é recusado. `citizen config set mode`,
`citizen selection` e `citizen sync` recusam um modo que quebre uma dessas regras antes de
qualquer escrita; um hook roda sem ele. Um modo pode desligar um hook central (`brief-guard`,
`grade-bash`, `neutralize-tool-output` ou `stop-gate`) somente quando `config.json` define
`core_switches_acknowledged` como `true`, como qualquer camada pode fazer. Com isso definido, o
modo se aplica com esse hook central desligado. Sem isso, esses três comandos recusam o modo, e um
hook aplica o restante do modo com esse hook central ainda ligado.
