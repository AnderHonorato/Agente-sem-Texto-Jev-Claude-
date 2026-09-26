# Política de segurança

## O que conta como problema de segurança aqui

Este repositório instala arquivos no seu diretório home e mescla chaves nas suas configurações do Claude Code
e do VS Code. Reporte de forma privada se você encontrar:

- `bin/harness` tocando, movendo ou apagando qualquer coisa fora dos caminhos registrados no seu
  manifesto, ou fora das chaves listadas em `claude/OWNERSHIP.json`.
- `claude/hooks/allow-readonly-bash.py` aprovando um comando que consegue escrever, apagar, exfiltrar
  ou executar conteúdo não confiável.
- Uma credencial, token ou hostname privado em qualquer lugar da árvore ou do seu histórico.
- Uma regra ou habilidade cujo texto poderia ser usado para fazer um agente contornar um portão de permissão.

## Versões suportadas

Só o `main` e o último lançamento com tag recebem correções.

## Como reportar

Use o relato privado de vulnerabilidade do GitHub para este repositório (a aba **Security** →
**Report a vulnerability**). Não abra uma issue pública para nada que possa ser explorado.
Você receberá uma confirmação em até uma semana e uma correção ou decisão em até trinta dias.

## Primeiras linhas de defesa já em vigor

`bin/harness lint` roda no CI, num hook de pre-commit no checkout, e manualmente. Ele não carrega
nenhuma lista de valores reais: ele bate com formatos de dado pessoal e padrões de segredo em toda a árvore,
sem nenhum arquivo isento, e lê os próprios termos do mantenedor a partir de um arquivo não versionado fora do
repositório. A varredura de segredos do GitHub com proteção de push está ativada. O hook de somente-leitura é
testado contra um corpus de comandos capazes de escrever (`tests/test_allow_readonly_bash.py`) e
nunca retorna uma negação, então um bug nele só consegue cair de volta no fluxo de permissão nativo normal.
`claude/hooks/grade-bash.py` é classificado da mesma forma: uma nota baixa falsa é um prompt perdido, nunca
pior que o fluxo de permissão nativo, e uma nota alta falsa custa um prompt extra ou, onde não existe
prompt, uma nova execução: com o marcador de confirmação em `bypassPermissions`, e no modo `auto` depois que o
usuário responde `approve <código>` como a mensagem inteira. Essa aprovação só é registrada a partir de um prompt
que não é nada além de tokens de aprovação, então texto que um agente consegue colocar num turno de notificação não consegue carregar
uma, e ela cobre uma execução de um comando numa sessão por trinta minutos. O repositório dela fica fechado para
as escritas de ferramenta do agente, e um comando Bash que o nomeia recebe nota 3.

Esse repositório é um interlock, não contenção. Qualquer processo rodando como o usuário consegue forjar qualquer estado
local, incluindo esse repositório e os arquivos de política de governança; um `python3 -c` que constrói o caminho em
tempo de execução não é classificado, e o hook não tenta classificar código arbitrário. O canal de aprovação
impede um agente cooperativo de rodar um comando irreversível por engano. Ele não segura um
hostil: esse é o trabalho do sandbox, e um agente em que você não confia pertence a um.
O portão de parada roda os próprios comandos `## Gate` de um repositório só numa pasta confiada através do
diálogo do Claude Code ou de `harness trust`, então um clone não consegue rodar código no primeiro Stop. A
postura de permissão `bypass` exige uma confirmação explícita no arquivo de configuração e é
documentada como inadequada para qualquer máquina que toque dados regulados.
