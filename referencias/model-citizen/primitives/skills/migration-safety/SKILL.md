---
name: migration-safety
description: Write, review or apply a database schema migration without destroying data. Use for any task that creates or modifies a migration file (Alembic, Prisma, Django, Rails, Flyway, raw SQL), and before applying one to a shared environment.
---

# Segurança de migração

## Trate todo ambiente como produção

Ambientes de staging e demo carregam dados reais mais frequentemente do que qualquer um admite, e
uma migração que destrói dados no staging demonstra que a mesma operação rodaria em produção. Não
existe exceção "é só staging". **Nunca escreva uma migração que possa destruir silenciosamente
dados existentes.**

## Operações destrutivas — pare e leve ao humano

Não gere estas autonomamente. Descreva o que você pretende e por quê, e espere confirmação antes
de escrever o arquivo:

- `DROP TABLE`, `DROP COLUMN`, `TRUNCATE` — destrói linhas ou valores permanentemente.
- `ALTER COLUMN … TYPE` com um cast com perda — o banco de dados reescreve a coluna; valores que
  não podem ser convertidos são perdidos.
- Remover `NOT NULL` e depois apagar a coluna — mesmo que acima.
- `DELETE FROM` dentro de uma migração — perda de dados sem recuperação a não ser por um backup.

## Padrões seguros

**Adicionando uma coluna.** Adicione-a anulável primeiro, mesmo se a intenção final for `NOT
NULL`. Preencha retroativamente numa migração separada ou passo de deploy. Adicione a restrição
apenas depois que o preenchimento retroativo for confirmado. Três migrações pequenas superam uma
que reescreve dados e adiciona uma restrição de uma vez.

**Renomeando uma coluna.** Nunca renomeie num único deploy. Expandir-contrair: adicione a nova
coluna anulável; escreva em ambas; preencha retroativamente a nova a partir da antiga; troque as
leituras; apague a coluna antiga num release posterior uma vez confirmada a segurança.

**Mudando um tipo.** Sem perda (`VARCHAR` → `TEXT`) pode prosseguir com uma nota no comentário da
migração. Com perda (`TEXT` → `INTEGER`, encolhendo um `VARCHAR`) para e pergunta.

**Removendo uma coluna.** Apenas depois de confirmar que nenhum código implantado a lê ou escreve,
e existe um backup ou a coluna é confirmada vazia. Arquive antes de apagar no caminho de downgrade:

```sql
CREATE SCHEMA IF NOT EXISTS archive;
CREATE TABLE IF NOT EXISTS archive.<table>_<revision>_downgrade AS
  SELECT id, <dropped_column> FROM <table>;
```

O arquivo é retido indefinidamente; ninguém o apaga sem aprovação explícita.

**Aditivo primeiro.** Adicionar uma coluna ou tabela é sempre mais seguro do que modificar uma. Se
o objetivo pode ser alcançado adicionando, adicione.

## Checklist antes de commitar um arquivo de migração

- `upgrade()` não contém `DROP TABLE`, `DROP COLUMN`, `TRUNCATE` ou `DELETE FROM` sem aprovação
  humana explícita registrada no PR.
- Toda nova coluna `NOT NULL` tem um valor padrão do servidor ou é adicionada anulável com um
  preenchimento retroativo separado.
- Você leu o arquivo gerado. Nunca confie apenas na saída de autogeração.
- `downgrade()` está implementado, ou é um no-op explícito com um comentário dizendo por que o
  rollback é impossível para esta mudança.

## Nunca edite uma migração já aplicada

Uma vez que uma migração foi aplicada a qualquer ambiente compartilhado, ela é imutável. Crie uma
nova migração para corrigir erros.

## Colapse migrações de trabalho em progresso antes da revisão

Se iterar numa mudança lógica produziu vários arquivos, colapse-os em um antes de abrir o PR —
apague e regenere, o que é seguro enquanto nada foi aplicado a um ambiente compartilhado. Isso é
diferente da sequência deliberada adicionar-anulável → preencher-retroativamente → restringir, que
permanece como migrações separadas por design.

## Depois de mesclar o branch principal num branch de feature

Branches de longa duração frequentemente produzem duas cabeças divergentes mesmo sem um conflito
de conteúdo. Verifique imediatamente depois de mesclar (`alembic heads`, ou o equivalente para a
ferramenta) e reconcilie com uma revisão de merge no-op antes de rodar testes ou fazer commit.
