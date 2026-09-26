# Sandboxing

As configurações nativas de sandbox são específicas de cada runtime. Os exemplos de configuração
do Claude abaixo não configuram o Codex. Consulte [controles de runtime](runtime-controls.md) e
[compatibilidade](compatibility.md) para as lacunas de aplicação antes de confiar em um limite de
papel ou permissão.

Os modos de permissão respondem "isto pode rodar?". Essa é a pergunta errada para um agente
deixado sozinho: quando um loop está sem supervisão, não há ninguém para responder. O isolamento
responde a uma pergunta diferente — "o que isto pode alcançar uma vez que já está rodando?" — e o
sistema operacional aplica a resposta em todo processo filho, seja qual for a decisão do modelo
sobre o que executar.

Isso faz dele uma postura, não uma regra. Quanto isolamento você quer depende do que está rodando
e de quem o escreveu, e as duas configurações úteis ficam bem distantes uma da outra.

## As duas formas

- **O sandbox embutido.** Um bloco `sandbox` em `~/.claude/settings.json` cerca os comandos Bash
  no nível do sistema operacional: escritas confinadas ao diretório de trabalho, rede negada
  exceto por uma lista de permissões, caminhos e variáveis de credenciais negados por completo.
  Toda ferramenta continua funcionando, então é barato o bastante para deixar ligado no trabalho
  diário.
- **Um container.** O agente roda dentro dele, com apenas o worktree montado por bind e a
  configuração do host montada somente leitura. Um limite mais rígido, comprado com ferramental
  mais grosseiro: sem rede significa sem ferramentas web, sem MCP pela rede, sem instalação de
  pacotes e sem API de modelo, a menos que você permita esse host específico. Certo para loops
  que rodam enquanto você dorme e para qualquer coisa que analise entrada não confiável.

A skill `sandbox` traz as chaves exatas, os padrões entre aspas, a linha de `docker run` e os
modos de falha de cada uma. Nenhuma das duas formas isola branches; `worktree-per-agent` faz isso,
e as duas se combinam.

## Por que o harness não escreve nada disso

`sandbox.*` não é uma chave possuída nem uma chave de postura. É configuração em nível de usuário
com um raio de impacto real: uma sincronização que ampliasse `allowedDomains` ou removesse uma
entrada `denyRead` desfaria silenciosamente um limite de segurança que o usuário definiu, e uma
sincronização que estreitasse uma delas quebraria os builds do usuário sem nenhum erro rastreável
por ninguém. `OWNERSHIP.json` já cobre esse caso por padrão — "Tudo que não estiver listado como
possuído é deixado exatamente como encontrado" — então essas chaves continuam suas.

Configure-as você mesmo, no seu próprio arquivo de configurações ou por sessão com `--settings`. A
skill existe para dizer quais chaves escrever; ela não as escreve por você.
