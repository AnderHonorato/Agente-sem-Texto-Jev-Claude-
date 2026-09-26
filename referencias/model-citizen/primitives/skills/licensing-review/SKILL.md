---
name: licensing-review
description: Verify a third-party library, asset, model, font, dataset or copied snippet is safe to ship under the project's licensing stance, and record it. Use before adding or upgrading any dependency, before downloading any asset, and before a release.
---

As proibições sempre ativas vivem na postura `licensing` selecionada. Resolva sua fonte
compartilhada com `citizen stances --json`; projeções de runtime carregam a mesma política. Este é
o procedimento.

## Antes de adotar ou atualizar

1. **Leia a licença autoritativa**, não o texto de marketplace ou o selo do README. Verifique a
   versão exata que você está pegando.
2. **Inspecione o pacote real**, incluindo dependências transitivas e quaisquer texturas, dados,
   fontes ou código empacotado licenciados separadamente dentro dele.
3. **Para licenciamento duplo**, registre qual opção qualificadora você está tomando. Onde os
   termos são combinados em vez de alternativos, todos devem estar em conformidade.
4. **Verifique autoria e proveniência.** A alegação de quem fez o upload não estabelece posse.
   Rejeite rips de jogo, cópias sem licença, e qualquer coisa com direitos faltando, conflitantes
   ou suspeitos.
5. **Reverifique na atualização.** Os termos mudam entre versões. Fixe um piso contra o qual você
   realmente rodou.
6. **Nenhuma nova dependência de terceiros sem uma razão que o revisor aceitará.** Num repositório
   compartilhado isso significa uma issue ou uma nota no PR; num repositório solo significa uma
   frase no commit.

Se nada compatível se encaixa, adapte uma base compatível ou crie trabalho original. Não enfraqueça
a política para usar um download. Disponibilidade no catálogo não é liberação de asset.

## Registre isso

Todo componente incorporado vai no manifesto de terceiros do projeto com:

- URL de origem
- Criador ou detentor de direitos
- Versão exata, ou hash do asset
- Identificador de licença, e o texto da licença preservado
- Modificações feitas
- Atribuição exigida

## Avisos que realmente são entregues

- Mantenha `THIRD_PARTY_NOTICES` e qualquer tela de créditos atualizados.
- Preserve texto de copyright, licença e isenção de responsabilidade. Inclua conteúdo de NOTICE
  exigido e links de licença. Identifique modificações onde a licença exigir.
- **Um aviso apenas no repositório é insuficiente se os destinatários não o recebem.** Verifique
  que os avisos estão na distribuição real antes do lançamento.
- Mantenha isso automaticamente. Não passe trabalho rotineiro de conformidade para o usuário.

## CC BY especificamente

Preserve os direitos licenciados do destinatário. Revise EULA e empacotamento DRM, e não aplique
restrições adicionais àquele conteúdo. Se a distribuição pretendida não puder cumprir dentro desta
política, escolha outro asset. Nunca alegue que uma única linha de crédito satisfaz toda licença.

## No lançamento

Verifique que todo componente de terceiros entregue tem uma licença qualificadora registrada e que
os avisos estão presentes no artefato construído. Relate itens não resolvidos claramente. Não
apague trabalho existente para resolver um achado, e não alegue que uma auditoria aconteceu quando
não aconteceu.
