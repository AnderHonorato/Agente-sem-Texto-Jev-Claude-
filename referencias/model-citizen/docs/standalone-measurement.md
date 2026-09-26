# Medindo sem o harness

O relatório de medição lê um único arquivo: o ledger de sessão em
`~/.local/state/agent-harness/usage.jsonl`, escrito pelo hook `usage-log`. Nada em
`bin/harness usage` precisa de um primitivo projetado, um arquivo de configurações mesclado ou um
runtime sincronizado, então o relatório é útil para quem quer os números e não a forma de
trabalhar.

## Quando o harness inteiro é a resposta

- Você quer as regras que o relatório pontua. `--rules` conta acertos de detector contra
  `claude/hooks/rule-detectors.py`, e um detector só significa algo quando a regra à qual ele se
  refere está de fato carregada na sessão. Contagens de acerto sem o texto que medem são uma
  fração de nada. Veja [usage.md](usage.md#which-rules-fired).
- Você quer agrupamentos por postura. `--by stance` lê o mapa `dimension: variant` que a CLI
  resolve, então um checkout sem configuração tem uma variante por dimensão e um grupo por
  relatório.
- Você já está rodando `citizen sync`. Nesse caso o hook já está instalado e o ledger se preenche
  sem nenhum passo a mais.

## Quando o relatório sozinho é a resposta

- Você quer gasto por repositório, modelo, papel ou dia, e roda o Claude Code ou o Codex como
  vêm de fábrica. Instale o hook `usage-log`, deixe tudo o resto como está, e leia
  [usage.md](usage.md) para o que cada agrupamento significa.
- Você está avaliando a medição antes de adotar os primitivos. O ledger é local, não guarda texto
  de mensagem, e remover o hook interrompe a coleta.
- Você está alimentando um backend de observabilidade. `citizen usage export` reproduz o ledger;
  veja [telemetry.md](telemetry.md).

## O caminho empacotado

Instalar o hook manualmente a partir deste repositório é a única rota hoje. Um pacote standalone
que carregue o hook, os detectores e o relatório sem o resto do harness está planejado na
[issue #453](https://github.com/JakeSelby/agent-harness/issues/453). Até que isso aconteça, um
leitor standalone copia dois arquivos deste checkout e fixa a versão de onde vieram.
