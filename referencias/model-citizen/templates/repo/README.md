# Ponto de partida do repositório

O que um repositório precisa para que os agentes trabalhem bem nele, dado que as regras globais
já são carregadas a partir do harness.

1. Copie `AGENTS.md` para a raiz do repositório e preencha os espaços reservados. Apague as
   seções que não se aplicam; não repita as regras globais.
2. `ln -s AGENTS.md CLAUDE.md` para que o Claude Code e o Codex leiam o mesmo arquivo. No
   Windows, escreva `@AGENTS.md` como a única linha de `CLAUDE.md` em vez disso.
3. Para o Claude Code, copie `settings.json` para `.claude/settings.json` e substitua as regras
   de permissão pelos comandos exatos que os agentes rodam neste repositório.
4. Mantenha a orientação compartilhada do projeto em `AGENTS.md`; para regras específicas do
   Claude com escopo limitado, coloque-as em `.claude/rules/<topic>.md` com um glob `paths:` no
   frontmatter.
5. Rode o gate de qualidade uma vez numa árvore limpa e cole sua linha final em `AGENTS.md`,
   para que qualquer falha futura seja atribuível.
6. Instale o hook de commit, que recusa um assunto que não seja um Conventional Commit:

   ```sh
   install -m 755 hooks/commit-msg .git/hooks/commit-msg
   ```

   Ele lê a postura `commits`, então `off` e `as-you-go` deixam tudo passar, e ele avisa em vez
   de falhar quando `conventional-attributed` não encontra um trailer `Co-Authored-By:`. Um hook
   de git vê a mensagem final não importa o que a escreveu, o que um hook que analisa `git commit`
   pela linha de comando não faz.

As regras de recusa (deny) do Claude em `settings.json` se aplicam apenas a esse runtime.
Configure e qualifique as restrições nativas do Codex separadamente; uma instrução compartilhada
não é um limite de sistema de arquivos. Mantenha as entradas de segredos em todo repositório, e
reduza as entradas de diretório gerado ao que este repositório realmente gera, adicionando
qualquer uma que ele gere e que o template não liste.

Se o repositório já tem `.cursor/rules/` ou arquivos de instrução de outro agente, migre o
conteúdo genérico para o harness com a skill `harness-authoring` e deixe aqui apenas fatos do
repositório. Duas cópias de uma regra divergem com o tempo.
