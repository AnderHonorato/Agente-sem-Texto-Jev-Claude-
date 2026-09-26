# Postura de commits: commit conforme avança

Para repositórios sem um gate de revisão — repositórios de planejamento, bases de conhecimento,
dotfiles — **faça commit incrementalmente** conforme unidades lógicas terminam, não uma vez no
final e não linha por linha, e **dê push depois de commitar** para que o trabalho seja durável.
**Conventional Commits** ainda se aplica. **Segure-se** em segredos, em conteúdo que o usuário
chamou de descartável, e no meio da edição de um arquivo dentro de um turno. **Repositórios de
aplicação com um gate de revisão são diferentes:** crie um branch, abra um PR, e deixe o gate
fazer o seu trabalho.
