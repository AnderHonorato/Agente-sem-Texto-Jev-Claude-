---
name: plan-authoring
description: Write or revise a plan file, proposal, design doc or handoff the user reviews before approving work; carries the Review Card contract and the addendum rules. Use before writing anything into .agent-harness/plans/, and for any markdown deliverable whose job is to get a go/no-go. (Escreva ou revise um arquivo de plano, proposta, doc de design ou handoff que o usuário revisa antes de aprovar o trabalho; carrega o contrato do Review Card e as regras do adendo. Use antes de escrever qualquer coisa em .agent-harness/plans/, e para qualquer entregável markdown cujo trabalho é obter um sinal verde ou vermelho.)
---

O gatilho vive na postura (stance) `plan-ceremony`. Este é o contrato.

## Por que isto existe

Um plano tem duas audiências e elas não são o mesmo leitor.

- **O revisor revisa a abordagem.** Design de sistema, passos, e as decisões que são dele — em
  uma tela, antes de ler qualquer outra coisa.
- **O agente implementador o executa.** Caminhos, sequenciamento, casos extremos, evidência.

Um documento escrito para os dois produz o arquivo de 884 linhas no qual o revisor se perde.
Então um plano é um arquivo com uma costura rígida: um **Review Card** acima do primeiro `---`,
um **Adendo** abaixo dele.

**Teste de falha:** se o revisor precisa rolar para saber o que está sendo construído, o plano
falhou, por melhor que seja o trabalho por trás dele.

## O Review Card

Tudo acima do primeiro `---`. **Alvo de 50 linhas de fonte, teto rígido de 70**, diagrama
incluído. A única coisa permitida ultrapassar 70 é um bloco completo de `## Decisões para o
revisor` — três linhas cada, cinco no máximo. Nunca corte uma decisão real para bater um
orçamento.

Não uma introdução ao plano — o plano inteiro na altitude de revisão.

Estas seções, nesta ordem. Não as renomeie, não adicione a elas, não dobre uma dentro de outra.

1. **`# <titulo>`** — 1 linha. O que será construído, como um sintagma nominal. Não uma frase.
2. **Blockquote de veredito** — no máximo 4 linhas. Duas frases, o que isto constrói e o
   mecanismo, depois uma linha de metadados: Esforço · Risco · Raio de impacto.
3. **`## Em resumo`** — 7 marcadores. Resultado · Abordagem · Toca · Novas dependências · Fora do
   escopo · Teste de saída · a única questão em aberto.
4. **`## Design do sistema`** — no máximo 15 linhas. Um diagrama, sem prosa acima dele, uma
   legenda abaixo.
5. **`## Passos`** — no máximo 8. Numerados, duas linhas cada: o quê e onde, depois o teste de
   saída.
6. **`## Decisões para o revisor`** — no máximo 5. Pergunta, recomendação com sua razão,
   alternativa. Uma linha cada.
7. **`## Riscos`** — no máximo 3 marcadores. Uma linha cada: o gatilho, e o que fazemos quando
   ele dispara.

`TEMPLATE.md` neste diretório é o esqueleto. `EXAMPLE.md` é um plano longo real reduzido ao seu
card.

## Um plano não contém tabelas markdown. Em lugar nenhum.

Nem no card, nem no adendo. Uma tabela markdown renderiza como uma grade com bordas cuja primeira
coluna é fixada estreita, então na largura de leitura toda célula mais longa que uma oração quebra
numa coluna alta e desalinhada. Essa é a densidade que um plano existe para evitar, e ela não é
melhor abaixo da régua do que acima dela.

- **`## Em resumo`** — sete marcadores `- **Rótulo** — valor`.
- **`## Passos`** — uma lista numerada, duas linhas por passo.
- **Qualquer pareamento ou mapeamento** — um marcador por linha, com os termos pareados em
  negrito juntos: `- **antigo/caminho.ts → novo/caminho.ts** — o que muda.`
- **Qualquer coisa com uma coluna "porquê"** — dobre o porquê dentro da frase. Uma tabela de três
  colunas é quase sempre uma lista de marcadores com um travessão dentro.
- **Não use linhas nuas de rótulo em negrito**, em nenhum destes casos: muitos previews de
  markdown colapsam linhas consecutivas com quebra suave num único parágrafo. O marcador de lista
  é o que garante a quebra.

O hook validador rejeita qualquer linha começando com `|` num arquivo de plano.

## Não há seção de Contexto no card

O defeito mais comum: todo plano abre com `## Context` e três parágrafos de background.
Background é material de adendo. As duas frases do veredito carregam o porquê — e se elas não
conseguem, o plano ainda não está compreendido o suficiente para ser escrito.

## Nunca no card, sempre no adendo

- Regras de trabalho, restrições de governança, as próprias instruções operacionais do agente
- Tabelas de evidência, logs de verificação, o que foi checado e o que não pôde ser
- Registros de ID, tabelas de alocação, inventários de arquivo, matrizes de toque
- Narrativas por agente ou por handoff
- Registros de gate além do único gate que realmente bloqueia
- Alternativas além da única linha de cada uma já em Decisões
- Qualquer reafirmação do pedido

## O diagrama

O card é revisado num painel de modo plano e numa barra lateral de chat, e ambos mostram uma
cerca mermaid como fonte crua. O diagrama do card é, portanto, texto puro, que renderiza em
qualquer lugar.

- **Um desenho de caixas e setas numa cerca `text`** — `├─▶`, `└─▶`, `──▶`, um `┄┄▶` pontilhado
  para um link fraco ou por polling. Teto de 12 nós. Se precisa de mais, o diagrama está na
  altitude errada — desenhe o subsistema sendo mudado, não o mundo inteiro.
- Mantenha toda linha abaixo de 80 colunas; uma linha quebrada quebra o desenho.
- Rotule as arestas com o que se move, não com verbos: `api ── episódio criptografado ──▶ web`.
- Marque o delta para que o leitor veja o que é novo: prefixe cada nó novo ou alterado com `*`, e
  nomeie o marcador na legenda.
- **Mermaid pertence abaixo do `---`,** e em docs que são lidos no GitHub — um `sequenceDiagram`
  quando ordenação entre processos é o assunto real. Nunca no card.
- Obrigatório quando a mudança atravessa mais de um componente. Omita apenas para edições de
  arquivo único.

## Passos

Uma lista numerada — estes são genuinamente ordenados — com duas linhas por passo:

```markdown
3. **[Fazer o bake do mapa de sombra](#step-3--bake-the-shadow-map)** — `tools/bake/shadow.py`, arquivo novo.
   *Exit:* `terrain_map_8192` escreve em menos de 3 minutos e ambos os shaders o amostram uma vez.
```

- **Linha um** é o que acontece e onde, com o título vinculado à sua âncora de adendo quando tem
  detalhe. **Linha dois** é o teste de saída, sempre liderado por `*Exit:*`.
- **Todo passo carrega um teste de saída real** — um comando, um render, uma asserção que passa.
  "Implementado" não é um teste de saída.
- Ordem de execução, e o passo 1 é a coisa mais barata que poderia invalidar o resto.
- Além de oito passos, agrupe sob cabeçalhos `### Fase`, no máximo três.
- Um plano nomeia as skills que vai rodar e a ordem em que rodam.

## Spikes dentro de um plano

Quando um passo é um experimento em vez de uma construção, escreva-o como um spike: a pergunta
que responde, o experimento mais barato que a responde, o critério de saída como um número, e a
máquina em que o orçamento foi medido. Leia o critério de saída contra números medidos, nunca
contra impressões.

## Decisões para o revisor

Numeradas, respondíveis no chat por número ("1 A, 2 sua recomendação"). Três linhas cada:

> **3. Bordas a partir de fitas de geometria, ou da textura de atributo?**
> *Recomendo* fitas — as linhas de fronteira reais já existem e ficam nítidas em todo zoom.
> *Alternativa* a técnica de gradiente, que precisamos de qualquer forma para mudanças de célula
> em runtime.

Com nada a decidir, escreva **Nenhuma — aprove para prosseguir**. Nunca invente decisões para
preencher a seção, e nunca deixe uma real enterrada no adendo.

## Revisões

Quando o plano muda depois de feedback, uma linha de blockquote diretamente sob o veredito:

> **Mudou nesta rodada.** Removido o spike de CDLOD · Gate 2 agora bloqueia a publicação · +1
> dia.

Três itens no máximo, uma linha. Apague a versão da rodada anterior — o card mostra apenas o
delta mais recente. O histórico completo de revisão vive no adendo.

## O adendo

Abaixo do primeiro `---`, sob `# Addendum`. Sem orçamento. Tudo que o agente implementador precisa
e o revisor não.

- Um cabeçalho `## Step N — <titulo>` por passo com detalhe, para que as linhas do card possam se
  ancorar a ele.
- Nada acima da régua é repetido abaixo dela. Se o adendo reafirma a abordagem, corte.
- Escrito para um agente sem contexto: caminhos exatos, comandos exatos, saída esperada.

## A mensagem de chat

O plano é entregue como dois artefatos. O arquivo é o documento; a mensagem de chat é o que o
revisor responde. Três formas, e nada improvisado.

**Primeira postagem, quando o plano está pronto.** Nesta ordem, nada mais:

1. **Linha de veredito** — uma ou duas frases, as mesmas do card.
2. **`## Em resumo`** — os sete marcadores, literalmente. Esta é a checagem "isto sequer é o
   escopo certo", e economiza abrir um plano que ia ser redirecionado de qualquer forma.
3. **`## Decisões`** — os blocos numerados, literalmente. O revisor responde por número no chat,
   então precisam ser legíveis onde ele digita.
4. **Um link markdown relativo ao workspace** para o arquivo do plano, com uma nota de como
   pré-visualizá-lo.
5. **A linha de fechamento**, apenas onde não há modo de plano, exatamente: *Responda **build**
   para prosseguir, ou continue refinando.* Sob o modo de plano a mensagem termina no link.

Deliberadamente excluído: o diagrama (o arquivo o guarda), os passos, os riscos, o adendo. Isso é
para o que o arquivo serve. Não os resuma também.

**Sob o modo de plano o arquivo já é a superfície de revisão.** O modo de plano designa o arquivo
de plano e o nomeia ele mesmo — um slug das suas palavras de abertura mais duas palavras
aleatórias, fixado antes de qualquer conteúdo existir — então você nem escolhe o nome nem o
renomeia enquanto planeja. Escreva o card ali, poste a mensagem, e chame `ExitPlanMode`: a
aprovação nativa é o gate, e pedir por um *build* digitado em cima disso é um segundo gate que
nada a jusante consegue ler. Uma vez aprovado, renomeie o arquivo para um slug de tópico — nunca
sobre um nome já em uso; use `-2` e diga isso — e passe ao `/build` esse caminho em vez de deixar
que seja procurado.

**Sem modo de plano, coloque o arquivo na tela antes de postar a mensagem.** Um link no chat é um
caminho, não uma renderização: em alguns clientes é clicável, em outros é texto morto, e um plano
escrito direto no disco nunca alcança uma visão nativa de plano, porque nada o registrou como tal.
O revisor é então convidado a aprovar um documento que não consegue ver. Então se o runtime pode
abrir um arquivo ao lado da conversa, abra o plano ali primeiro, e passe um caminho **absoluto** a
menos que você tenha confirmado que caminhos relativos resolvem; um caminho rejeitado é a falha
comum e ela é silenciosa. Se o runtime não pode, diga na mensagem como abrir o arquivo. O mesmo se
aplica em toda rodada de revisão, já que o revisor está lendo um arquivo alterado, não o que abriu
antes.

**Rodada de revisão, depois do feedback.** Muito mais curta — o revisor já conhece o plano:

1. **Uma linha nomeando o que mudou**, combinando com a linha **Mudou nesta rodada** do card.
2. **Apenas as decisões ainda em aberto**, renumeradas a partir de 1.
3. **O link, e a linha de fechamento apenas onde não há modo de plano.**

Nunca reposte Em resumo numa revisão. Se o escopo mudou o suficiente para precisar de releitura,
diga isso na linha de mudança e deixe o arquivo carregar.

**Sem decisões pendentes.** Veredito, Em resumo, o link, depois `ExitPlanMode` — ou *Responda
**build** para prosseguir* onde não há modo de plano.
Nunca invente decisões para preencher o bloco — um vazio é um sinal, não uma lacuna.

**Por que a mensagem é curta.** O hook valida arquivos, não mensagens. Nada impõe esta forma,
então ela precisa ficar pequena o suficiente para caber na memória de trabalho.

## Delegando

Use `citizen role run planner` com `--runtime`, o `--model` explícito da sessão, `--workspace`,
um briefing `--prompt-file` e `--artifact <new-plan.md>`. O worker isolado recebe o papel
compartilhado e as posturas resolvidas, e retorna conteúdo de plano; o harness o valida e publica.
Leia o artefato e poste a mensagem de revisão você mesmo. Planos existentes não são sobrescritos.
Rode o worker antes de entrar no modo de plano: ele escreve um artefato, e o modo de plano não
permite nenhuma escrita além do arquivo de plano designado — então dentro dele, copie o card do
worker em vez de delegar. Veja `docs/role-workers.md` para diretórios de entrada, status e
limites de qualificação nativa.

## Autoverificação antes de entregar

Rode isto, não estime a olho:

```bash
awk '/^---$/{exit} {n++} END{print n" card lines"}' <plan file>
```

- [ ] Card ≤ 70 linhas, ou ≤ 85 com um bloco completo de decisão
- [ ] Sem `## Context` acima da régua
- [ ] A primeira tela responde: o que está sendo construído, como, o que toca, o que preciso
  decidir
- [ ] Nenhum parágrafo acima da régua passa de três frases
- [ ] Todo passo tem um teste de saída real
- [ ] Decisões numeradas e respondíveis por número
- [ ] Nada acima da régua repetido abaixo dela

## Justificativa realocada das regras residentes

`voice-and-format.md` e `decisions-and-plans.md` foram cortadas até suas linhas operacionais
quando o contexto sempre carregado recebeu um teto. Estes são os parágrafos que costumavam
carregar, palavra por palavra.

### Voz e formato de saída

*Substituído em 24/09/2026 pela #811.* Os parágrafos que estavam aqui descreviam o template "O
que mudou" do estilo Scannable e as palavras de status como o contrato para retransmissões e
briefings de subagente. A postura `voice` agora é dona da forma da resposta e o hook
`brief-guard` acrescenta a forma de retorno do subagente; o texto anterior está no histórico de
git deste arquivo.

A variante `voice` selecionada rege a conversa principal. No Claude Code, `concise` e
`scannable` também definem um estilo de saída, que alcança apenas a conversa principal e seus
forks; outros subagentes rodam seu próprio prompt de sistema e não herdam nenhuma voz. Então um
relatório retransmitido é reescrito na forma da voz selecionada, um achado que não muda o que o
leitor faz é cortado, e todo briefing de subagente carrega sua forma de retorno.

Os arquivos de voz são escritos em prosa simples com poucos rótulos em negrito porque a
formatação de um prompt tende a se carregar para a resposta; veja a orientação de prompting da
Anthropic sobre controlar o formato de resposta
(https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices).

**Arquivos de plano e outros entregáveis markdown** seguem as mesmas regras — a voz selecionada,
caminhos de arquivo como links markdown relativos ao workspace em vez de crases. Qualquer coisa
que o usuário lê para aprovar trabalho — plano, proposta, doc de design, handoff, resumo de
pesquisa — abre com o Review Card da skill `plan-authoring` quando a postura `plan-ceremony` é
`review-card`, com o detalhe abaixo da régua, e é entregue na forma de mensagem de chat daquela
skill.

**Editores nem sempre repintam um preview de markdown quando um arquivo é reescrito fora de
banda.** Ao iterar em algo que o usuário está pré-visualizando, diga a ele para fechar a aba de
preview, ou escreva a próxima versão sob um novo nome de arquivo.

**Postagens publicadas em nome do usuário.** Ao redigir comentários, tickets ou respostas de
revisão que saem em nome do usuário, mantenha-os em **cerca de três frases**. Sem floreios de
despedida deferentes: sem "sua decisão", sem "me avise". O raciocínio vive em docs e tickets
vinculados, não inline no comentário; vincule para profundidade. Estrutura mais longa está bem
para corpos de ticket com esboços de escopo; comentários ficam concisos.

Conciso não é sem formatação. Uma vez que um comentário carrega três ou mais itens paralelos —
decisões, achados — divida-os em marcadores liderados por negrito com linhas em branco entre
eles. Estrutura não é licença para inchar: vincule o artefato em vez de colocar o raciocínio
inline.

### Apresentando decisões

**Não use um widget de escolha para decisões substantivas.** Escreva o bloco de decisão no chat
como a mensagem final autônoma do seu turno: cada pergunta declarada sem ambiguidade, a avaliação
por trás dela, uma recomendação com raciocínio, e as alternativas com o caso honesto de cada uma.
Numere-as. O usuário responde no chat ("1 postar, 2 comentar, 3 issue").

Dois modos de falha, ambos reais. Um widget de escolha no mesmo turno engole a avaliação, porque
texto escrito antes de uma chamada de ferramenta não é exibido de forma confiável. Um widget de
escolha no próximo turno desperdiça uma ida e volta. Rótulos de widget de escolha também truncam e
não conseguem carregar evidência ou trade-offs.

Um widget de escolha é reservado para bifurcações triviais onde os rótulos das opções sozinhos
carregam significado completo.

Agrupe decisões relacionadas num único bloco.

*Emendado em 24/09/2026 pela #811:* o bloco ainda pode encerrar a mensagem, mas as duas primeiras
linhas da resposta dizem que uma decisão está esperando.

### Apontar para uma opção não é uma decisão

Durante revisões de design e de opções, o usuário dizendo "esta" ou colando uma imagem de uma
opção significa **coloque isso no doc e me mostre**. Não é aprovação para implementar. Trate
apontar-para-opção como escopo para o artefato de revisão. Construa apenas sobre um "construir"
ou "vá com N" explícito.

### Execução de plano pré-aprovado

Uma vez que o usuário aprovou explicitamente um plano de múltiplos passos na conversa atual, não
pergunte de novo a cada passo. Execute, registre, avance para o próximo.

**Aplica-se quando** ele disse sim, vá em frente, prossiga, aprovado ou equivalente para um plano
completo; nenhuma informação nova altera materialmente o plano; e a ação estava no plano aprovado.

**Traga de volta para confirmação se** um erro ou estado inesperado torna um passo inseguro
(conflito de merge, branch errado, diff destrutivo não no plano), um passo não estava no plano
original, ou o raio de impacto aumentou materialmente.

A cerimônia do plano em si — se um plano precisa de um Review Card e um gate de construção — é
definida pela postura `plan-ceremony`. Sua variante `review-card` carrega os quatro passos
numerados; sua variante `light` pede apenas uma mensagem curta de chat e um sinal verde explícito.
