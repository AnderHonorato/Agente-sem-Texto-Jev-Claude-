# Sincronização e desvio (drift)

`citizen sync` resolve os padrões compartilhados de usuário e os projeta nos diretórios de runtime
selecionados. O diário de posse (ownership journal) registra o conteúdo anterior e o aplicado; o
manifesto de links registra os destinos. Um lock de processo impede sincronização ou
desinstalação concorrentes. Escritas individuais usam substituição atômica. Isso é reconciliação
recuperável por arquivo, não uma transação atômica sobre todos os arquivos do cliente.

O Claude Code recebe regras compartilhadas linkadas, variantes de postura selecionadas, skills e
apresentação, projeções geradas de papel/comando, identidade pessoal e configurações mescladas. O
Codex recebe instruções compartilhadas e identidade, skills compartilhadas, skills de workflow
geradas e TOML de papel, hooks, e configurações TOML mescladas estruturalmente. Nenhum dos dois
runtimes exige a instalação do outro.

A sincronização respeita os tipos de switch do [documento de seleção](preferences.md#the-selection-document).
Uma regra, skill, workflow ou papel que as camadas do usuário definem como `off` fica ausente de
ambos os runtimes: nenhum link de regra e nenhuma seção no `AGENTS.md` do Codex, nenhum link de
skill em nenhum dos dois diretórios de skills, nenhum comando e nenhuma skill gerada do Codex,
nenhuma definição de agente em nenhum dos dois diretórios, e o hook de spawn nunca roteia para um
worker de banda `off`. Uma projeção que uma sincronização anterior fez é retirada na próxima, e
`harness diff` relata que um switch mudou desde a última sincronização. As regras do repositório
são linkadas um arquivo por vez no diretório real `~/.claude/rules/harness/`; o link de diretório
único criado por versões anteriores à 0.14.0 é migrado na próxima sincronização, com seus estados
anterior e aplicado registrados no manifesto de links, e a desinstalação remove o diretório assim
que seus links desaparecem. `harness selection` relata a contagem de linhas sempre carregadas da
seleção em vigor; o limite do lint continua contando o pior caso sobre toda seleção.

Toda raiz em `primitive_roots` também é projetada, depois da própria raiz deste repositório e na
ordem de configuração, com nomes ordenados dentro de cada raiz. As regras de uma raiz são linkadas
em `~/.claude/rules/harness-roots/<root>/` e renderizadas no `AGENTS.md` do Codex atrás de um
comentário que nomeia a raiz de onde vieram; suas skills são linkadas ao lado das do repositório em
ambos os runtimes. A verificação de colisão de nomes roda através do repositório e de toda raiz
antes de qualquer escrita, de modo que nenhuma raiz consegue sombrear outra silenciosamente. O
manifesto de links registra a raiz de onde cada link veio, o que é o que permite a `citizen diff`
nomear a raiz a corrigir e a `citizen uninstall` retirar exatamente o que adotou; uma regra que uma
raiz deixa de carregar tem seu link retirado na próxima sincronização. Uma raiz que a configuração
nomeia mas o disco não carrega é um aviso e um salto, não uma sincronização falha.

Diretórios personalizados usam `CLAUDE_CONFIG_DIR` e `CODEX_HOME`; o diretório compartilhado do
harness pode usar `HARNESS_HOME`. A confiança de hook nativa é separada do registro e da confiança
do gate de repositório do harness.

## Seleções de postura de projeto e sessão

A sincronização só projeta sua seleção em nível de usuário, então o texto de postura linkado é o
que sua última sincronização resolveu. Uma seleção de projeto (`HARNESS_PROJECT_CONFIG`) ou uma de
sessão (`HARNESS_STANCE_*`, `HARNESS_SESSION_CONFIG`, `HARNESS_MODE`) nunca redireciona esses links
globais. Em vez disso, o hook de início de sessão resolve a escada completa com
`citizen stances --json` e, para cada dimensão cuja variante difere da que o manifesto de
sincronização registra, adiciona o texto dessa variante ao contexto da sessão como uma linha
"Effective session stance" que substitui a variante linkada para aquela sessão. Os hooks leem a
mesma resolução em tempo de execução, então a prosa que você segue e os switches sobre os quais os
hooks agem concordam.
`citizen diff` compara os links contra sua seleção em nível de usuário, então uma seleção de
projeto ou sessão não é desvio (drift); ela avisa quando uma seleção de projeto ou sessão muda uma
postura resolvida.

A injeção custa contexto apenas quando uma seleção difere; uma sessão sem seleção, ou uma que
combina com as variantes sincronizadas, não paga nada. O que ela injeta é relido a cada turno,
como a camada sempre carregada, então compartilha o orçamento dessa camada: o limite de tokens que
`citizen lint` aplica, menos o que a sincronização já tornou sempre carregado (as instruções, as
regras que linkou e as variantes de postura linkadas). Cada dimensão diferente é sempre nomeada.
Seu texto é incluído em ordem de dimensão enquanto couber no que resta; uma variante que não cabe é
nomeada com o caminho do seu arquivo e uma instrução para lê-lo e segui-lo, de modo que uma
variante customizada longa se degrada para um ponteiro em vez de estourar o orçamento. O caso de
qualificação `custom-stance` observa nativamente tanto uma seleção de projeto quanto uma de
sessão.

Um caminho não gerenciado é um conflito, a menos que explicitamente adotado. Um link redirecionado
ou um valor gerenciado modificado pelo usuário é preservado e relatado. `citizen diff` detecta
artefatos ausentes, redirecionados ou modificados. A desinstalação restaura valores anteriores
somente enquanto o valor atual combina com o último valor aplicado; ela mantém conflitos e seus
registros de recuperação. Adições do usuário fora dos campos possuídos sobrevivem.

[Posse da instalação](runtime-installation.md) traz detalhes operacionais, e
[posse das configurações](settings-ownership.md) identifica os campos nativos. Rode a
sincronização de novo depois de adicionar skills ou papéis; visões de fonte geradas exigem
`citizen generate` primeiro. Caminhos legados do Claude permanecem como links de compatibilidade,
mas a autoria nova pertence sob `primitives/`.

O Windows nativo não é suportado. Clientes hospedados e hosts que ignoram symlink permanecem não
qualificados; não há modo de cópia suportado. Veja [compatibilidade](compatibility.md) para fatos
específicos de cliente.
