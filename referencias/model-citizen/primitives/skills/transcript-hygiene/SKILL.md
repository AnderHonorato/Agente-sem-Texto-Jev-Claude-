---
name: transcript-hygiene
description: Bound what subagents return and what tool output enters the transcript; load when briefing a subagent or reading large output.
---

# Higiene de transcrição

As linhas operacionais vivem na regra residente `primitives/rules/transcript-hygiene.md`. Esta
skill carrega o raciocínio por trás delas, os números em contexto, e os exemplos.

O usuário lê a transcrição, não só a mensagem final. **Resumos de raciocínio são desejados e
ficam** — eles são recolhidos e abertos deliberadamente. Tudo mais na rolagem é custo que ele não
pediu, e os piores ofensores são saída de ferramenta e relatórios de subagente retransmitidos, não
prosa.

## Leia de forma restrita

- **Nunca dê `cat` num arquivo inteiro para responder a uma pergunta pontual.** `sed -n
  '40,80p'`, `head -40`, ou `grep -n` com o padrão. Leia o arquivo inteiro apenas quando você vai
  realmente usar o arquivo inteiro.
- **Nunca encadeie `cat A && cat B && cat C`** para se orientar. Oriente-se com `grep -n '^#'`
  para cabeçalhos, `wc -l` para tamanho, depois leia a parte que importa.
- **Filtre todo `find` e `ls`.** Um repositório com um diretório `renders/`, `data/` ou `target/`
  vai imprimir centenas de nomes de arquivo gerados. Delimite o glob ou canalize para `head`.
- **Um comando imprimindo mais de ~100 linhas precisa de uma razão** que você poderia declarar em
  voz alta.

## Delimite o que um subagente devolve

`delegation.md` diz para limitar o retorno. Estes são os números.

- **Agente de coleta: 400 palavras.** Resumo de pesquisa: **600**. Revisão adversarial: apenas
  achados, sem reafirmar o que leu.
- **O detalhe vai para um arquivo, não para o retorno.** Instrua-o a escrever a versão longa no
  scratchpad e retornar o veredito, os achados que mudam uma decisão, e o caminho. Mesma divisão
  que um plano: card na mensagem, adendo no disco.
- **Um limite de palavras não é um orçamento para gastar.** Peça o que muda a resposta, e nada
  mais.

## Nunca reimprima a saída de um subagente

- **Sintetize, nunca retransmita.** Um achado que importa pertence à sua própria resposta, em
  suas próprias palavras, carregando a fonte. Um achado que não importa não aparece de forma
  alguma.
- **Nunca cole o relatório** — nem como citação, nem como um bloco "aqui está o que o agente de
  pesquisa encontrou", nem levemente editado. O harness já renderiza a linha própria do agente.
- **Nunca ecoe o briefing que você enviou.** O usuário não tem razão para ler um prompt que não
  escreveu.
- **Sem narração de chegada.** Nem "ambas as threads de pesquisa voltaram", nem "os agentes
  retornaram". Molde a resposta pela postura (stance) `voice`; o leitor não precisa da
  maquinaria.

## A descrição da ferramenta é o registro de ação

Numa visão de foco, chamadas de ferramenta, resultados e raciocínio se recolhem em linhas
expansíveis de uma linha, e a linha que o usuário vê é a `description` que você passou. É o
registro, não um rótulo para seu próprio benefício.

- **Escreva-a para um leitor que nunca abre a linha.** "Verificar se o card do plano cabe no
  teto", não "rodar awk no arquivo do plano".
- **Sem flags, sem caminhos, sem texto de comando.** Eles não estão lendo o comando; é para isso
  que serve expandir.
- **Uma ação clara em palavras simples**, cinco a dez para comandos rotineiros, mais longa apenas
  quando um relance não diria o que ela faz.

Texto que você escreve entre chamadas de ferramenta permanece visível numa visão de foco. Uma
nota de uma linha antes de um lote é bem-vinda; narrar cada chamada não é.

## A única exceção

Retransmissão literal é correta quando o texto exato *é* o achado: uma mensagem de erro, uma
cláusula de licença, uma linha de decisão citada, uma asserção falhando. Cite a linha, não o
relatório ao redor dela.
