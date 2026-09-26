---
name: sandbox
description: Fence an autonomous or long-running agent loop: the built-in sandbox with network off, or a container with the worktree mounted. Use before any unattended loop, before `execute` autonomy on an unfamiliar repo, and whenever a task pulls untrusted input.
---

# Cerque o loop

Um modo de permissão decide se uma chamada roda. Um sandbox decide o que um comando pode alcançar
uma vez que está rodando, e o SO impõe isso em todo processo filho. Um loop não supervisionado
precisa do segundo tipo: ninguém está no prompt para responder pelo primeiro.

## Escopo de runtime

A configuração e o exemplo de container abaixo são específicos do Claude Code. Não copie essas
configurações para o Codex. Para o Codex, use seu sandbox nativo e controles de aprovação como
documentado em [a referência de configuração](https://learn.chatgpt.com/docs/config-file/config-reference).
Um sandbox somente-leitura restringe escritas no sistema de arquivos; a política de aprovação é um
controle separado. Hooks nativos não substituem o confinamento do SO. Padrões personalizados de
papel do Codex podem ser substituídos pelas permissões do turno do pai; veja
`docs/runtime-controls.md` antes de delegar trabalho que exige uma fronteira rígida. A
qualificação de cliente permanece no catálogo de compatibilidade.

## O sandbox do Claude Code

Ele "roda no macOS, Linux e WSL2. Windows nativo não é suportado"; Linux e WSL2 precisam de
`bubblewrap` e `socat` instalados primeiro. Coloque isto em `~/.claude/settings.json` para cobrir
todo projeto; o painel `/sandbox` escreve `enabled` em `.claude/settings.local.json` para um
projeto.

```json
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "allowUnsandboxedCommands": false,
    "network": { "allowedDomains": [], "strictAllowlist": true },
    "filesystem": { "denyRead": ["~/.ssh", "~/.aws", "~/.config/gh"] }
  }
}
```

`strictAllowlist` sobre um `allowedDomains` vazio é rede desligada: o Claude Code então "nega a
comandos em sandbox o acesso a qualquer host fora da lista de permissões em vez de perguntar".
Apenas as configurações de usuário, gerenciadas e `--settings` a definem; o próprio arquivo de um
repositório não pode. As entradas de negação são estruturais — a política de leitura padrão cobre
o disco inteiro, e "este padrão ainda permite ler arquivos de credencial como
`~/.aws/credentials` e `~/.ssh/`." Adicione entradas em `sandbox.credentials.envVars` com `"mode":
"deny"` para desabilitar tokens para comandos em sandbox também. `failIfUnavailable` torna uma
dependência faltando uma parada dura em vez de um fallback silencioso sem sandbox, e
`allowUnsandboxedCommands: false` remove a via de escape de retentar-fora. Subagentes herdam o
sandbox da sessão; comandos que você digita no prompt `!` não.

Para uma sessão, sem escrever nenhum arquivo: `claude --settings '{"sandbox":{"enabled":true}}'`.
Confirme com `/sandbox`: a aba **Config** mostra as configurações resolvidas, e uma aba
**Dependencies** aparecendo significa que um pacote está faltando. Um prompt intitulado "Bash
command (unsandboxed)" é o sinal de que um comando saiu da fronteira. Chaves e padrões:
https://code.claude.com/docs/en/sandboxing

## Um container

Fronteira mais dura, ferramental mais grosseiro. Monte a worktree e nada mais, permaneça não-root,
e deixe o container ser o isolamento — não aninhe o sandbox nativo dentro dele.

```bash
docker run --rm -it --network none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" -w /work \
  -v "$HOME/.claude:/config:ro" -e CLAUDE_CONFIG_DIR=/config -e ANTHROPIC_API_KEY \
  <image-with-the-cli> claude --dangerously-skip-permissions -p "<the loop prompt>"
```

`podman` substitui sem mudanças. O que quebra, em ordem: `--network none` corta também a API do
modelo, então como está escrito isso roda apenas contra um modelo local — para um loop que precisa
alcançar a API, permita aquele único host e nada mais e a forma se mantém. Depois busca e fetch
web, todo servidor MCP alcançado pela rede, e toda instalação de pacote; um mount de config
somente-leitura bloqueia estado de sessão e escritas de credencial, então a autenticação chega por
variável de ambiente. Perder tudo isso é o objetivo quando a tarefa faz parsing de entrada que
você não escreveu: um caminho que o loop não tem não pode ser convencido a abrir.

## Qual escolher

Sandbox nativo para trabalho diário: uma mudança de configuração, toda ferramenta continua
funcionando, o SO ainda impõe a fronteira. Container para um loop que roda enquanto você dorme,
um repositório cujos scripts de build você não leu, ou qualquer coisa lidando com conteúdo não
confiável. Nenhum dos dois isola branches — rode dentro de uma worktree também, conforme a skill
`worktree-per-agent`.
